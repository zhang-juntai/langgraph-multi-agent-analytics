"""
Docker沙箱执行器
在Docker容器中安全执行LLM生成的Python代码

安全特性：
1. 容器隔离（独立namespace）
2. 内存限制（cgroups）
3. CPU限制（cgroups）
4. 无网络访问（--network none）
5. 只读文件系统（除了输出目录）
6. Seccomp系统调用过滤
7. 非root用户运行
8. 进程数限制
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from src.graph.state import CodeResult
from configs.settings import settings

logger = logging.getLogger(__name__)


def _resolve_dataset_path(ds: dict, index: int, materialized_files: list[str]) -> str:
    """Return a local path for a dataset, materializing db:// files when needed."""
    file_path = ds.get("file_path", "") or ""
    if file_path and not file_path.startswith("db://"):
        return file_path

    file_id = ds.get("file_storage_id")
    if file_path.startswith("db://"):
        file_id = file_path.removeprefix("db://")

    if not file_id:
        return file_path

    from src.storage.file_store import get_file_store

    store = get_file_store()
    content = store.get_file(file_id)
    if content is None:
        raise FileNotFoundError(f"Stored dataset not found: {file_id}")

    info = store.get_file_info(file_id) or {}
    filename = info.get("filename") or ds.get("file_name") or f"dataset_{index}.csv"
    suffix = Path(filename).suffix or ".csv"

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        suffix=suffix,
        prefix=f"docker_data_{file_id[:8]}_",
        dir=str(settings.DATA_DIR),
    )
    with os.fdopen(fd, "wb") as f:
        f.write(content)

    materialized_files.append(temp_path)
    return temp_path

# Docker SDK延迟导入
_docker_client = None


def get_docker_client():
    """获取Docker客户端（延迟初始化）"""
    global _docker_client
    if _docker_client is None:
        try:
            import docker
            _docker_client = docker.from_env()
        except ImportError:
            raise RuntimeError("请安装Docker SDK: pip install docker")
        except Exception as e:
            raise RuntimeError(f"无法连接Docker daemon: {e}")
    return _docker_client


# ============================================================
# 危险模式检测（保留作为第一道防线）
# ============================================================
DANGEROUS_PATTERNS = [
    "os.system",
    "subprocess",
    "shutil.rmtree",
    "__import__",
    "exec(",
    "eval(",
    "compile(",
    "open('/etc",
    "open('/proc",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "importlib",
    "ctypes",
    "socket.",
    "requests.",
    "urllib.",
    "http.client",
]


def _check_code_safety(code: str) -> list[str]:
    """
    检查代码中是否包含危险操作。
    返回检测到的危险模式列表（空列表 = 安全）。
    """
    warnings = []
    code_lower = code.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in code_lower:
            warnings.append(f"检测到危险操作: {pattern}")
    return warnings


class DockerSandbox:
    """Docker容器沙箱执行器"""

    IMAGE_NAME = "multiagent-sandbox:latest"

    def __init__(self):
        self.client = get_docker_client()
        self._ensure_image()

    def _ensure_image(self):
        """确保沙箱镜像存在"""
        try:
            self.client.images.get(self.IMAGE_NAME)
            logger.info(f"沙箱镜像已存在: {self.IMAGE_NAME}")
        except Exception:
            logger.warning(f"沙箱镜像不存在，请先构建: docker build -f Dockerfile.sandbox -t {self.IMAGE_NAME} .")
            # 不自动构建，避免意外行为

    def execute(
        self,
        code: str,
        datasets: list[dict] | None = None,
        timeout: int | None = None,
        memory_mb: int | None = None,
        cpu_quota: float | None = None,
    ) -> CodeResult:
        """
        在Docker容器中执行Python代码

        Args:
            code: 要执行的Python代码
            datasets: 数据集列表 [{"name": "df1", "path": "/data/file.csv"}, ...]
            timeout: 超时时间（秒）
            memory_mb: 内存限制（MB）
            cpu_quota: CPU配额（1.0 = 1个CPU）

        Returns:
            CodeResult 结构化结果
        """
        # 使用配置默认值
        timeout = timeout or settings.SANDBOX_TIMEOUT
        memory_mb = memory_mb or settings.SANDBOX_MEMORY_MB
        cpu_quota = cpu_quota if cpu_quota is not None else settings.SANDBOX_CPU_QUOTA

        exec_id = uuid.uuid4().hex[:8]
        logger.info(f"Docker沙箱执行开始 [id={exec_id}, timeout={timeout}s, memory={memory_mb}MB, cpu={cpu_quota}]")

        # 1. 安全检查（第一道防线）
        safety_warnings = _check_code_safety(code)
        if safety_warnings:
            logger.warning(f"代码安全检查警告: {safety_warnings}")
            return CodeResult(
                code=code,
                stdout="",
                stderr="\n".join(safety_warnings),
                success=False,
                figures=[],
                dataframes={},
            )

        # 2. 准备数据卷挂载
        volumes = {}
        volumes = {}
        container_datasets = []
        materialized_files: list[str] = []

        if datasets:
            for i, ds in enumerate(datasets):
                file_path = _resolve_dataset_path(ds, i, materialized_files)
                file_name = ds.get("file_name", f"dataset_{i}")

                if file_path and Path(file_path).exists():
                    container_path = f"/sandbox/data/dataset_{i}{Path(file_path).suffix}"
                    # 宿主机路径 -> 容器内路径（只读挂载）
                    container_path = f"/sandbox/data/dataset_{i}{Path(file_path).suffix}"
                    volumes[file_path] = {
                        "bind": container_path,
                        "mode": "ro"  # 只读
                    }
                    container_datasets.append({
                        "name": Path(file_name).stem,
                        "path": container_path
                    })

        # 3. 创建临时目录用于输出
        output_dir = settings.OUTPUT_DIR / f"sandbox_{exec_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 挂载输出目录（读写）
        volumes[str(output_dir)] = {
            "bind": "/sandbox/outputs",
            "mode": "rw"
        }

        # 4. 准备输入数据
        input_data = {
            "code": code,
            "datasets": container_datasets,
            "timeout": timeout
        }

        # 5. 运行容器
        try:
            container = self.client.containers.run(
                self.IMAGE_NAME,
                input=json.dumps(input_data, ensure_ascii=False),
                detach=True,
                mem_limit=f"{memory_mb}m",
                memswap_limit=f"{memory_mb}m",  # 禁用swap
                cpu_quota=int(cpu_quota * 100000),
                cpu_period=100000,
                network_disabled=True,  # 无网络访问
                read_only=True,  # 只读文件系统（除了挂载的卷）
                volumes=volumes,
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                pids_limit=100,  # 限制进程数
                working_dir="/sandbox",
                environment={
                    "PYTHONUNBUFFERED": "1",
                    "MPLBACKEND": "Agg",
                },
                # 设置日志驱动
                log_config={"type": "json-file", "config": {"max-size": "10m"}},
            )

            # 6. 等待容器完成
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", -1)
            except Exception as e:
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    container.kill()
                    logger.warning(f"Docker沙箱执行超时 [id={exec_id}]")
                    return CodeResult(
                        code=code,
                        stdout="",
                        stderr=f"⏰ 代码执行超时（{timeout}秒），请优化代码效率或减少数据量。",
                        success=False,
                        figures=[],
                        dataframes={},
                    )
                raise

            # 7. 获取输出
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")

            # 8. 清理容器
            try:
                container.remove()
            except Exception:
                pass

            # 9. 解析结果
            return self._parse_result(
                code=code,
                logs=logs,
                exit_code=exit_code,
                output_dir=output_dir,
                exec_id=exec_id
            )

        except Exception as e:
            logger.error(f"Docker沙箱执行异常 [id={exec_id}]: {e}")
            return CodeResult(
                code=code,
                stdout="",
                stderr=f"沙箱执行异常: {str(e)}",
                success=False,
                figures=[],
                dataframes={},
            )
        finally:
            for temp_file in materialized_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

    def _parse_result(
        self,
        code: str,
        logs: str,
        exit_code: int,
        output_dir: Path,
        exec_id: str
    ) -> CodeResult:
        """解析容器输出结果"""
        try:
            # 尝试解析JSON输出
            result_data = json.loads(logs)
            success = result_data.get("success", False) and exit_code == 0
            stdout = result_data.get("stdout", "")
            stderr = result_data.get("stderr", "")
            figures = result_data.get("figures", [])

            # 将容器内路径转换为宿主机路径
            host_figures = []
            for fig_path in figures:
                # 容器内路径 /sandbox/outputs/fig_xxx.png
                # 映射到宿主机 output_dir/fig_xxx.png
                fig_name = Path(fig_path).name
                host_path = output_dir / fig_name
                if host_path.exists():
                    host_figures.append(str(host_path))

            logger.info(
                f"Docker沙箱执行完成 [id={exec_id}, success={success}, "
                f"figures={len(host_figures)}, stdout_len={len(stdout)}]"
            )

            return CodeResult(
                code=code,
                stdout=stdout,
                stderr=stderr,
                success=success,
                figures=host_figures,
                dataframes={},
            )

        except json.JSONDecodeError:
            # 如果不是JSON，直接返回原始输出
            success = exit_code == 0
            figures = self._extract_figures_from_output(logs, output_dir)

            return CodeResult(
                code=code,
                stdout=logs,
                stderr="" if success else "执行失败",
                success=success,
                figures=figures,
                dataframes={},
            )

    def _extract_figures_from_output(self, logs: str, output_dir: Path) -> list[str]:
        """从输出中提取图表路径"""
        figures = []
        for line in logs.split("\n"):
            if "[FIGURE_SAVED]" in line:
                fig_path = line.split("[FIGURE_SAVED]")[-1].strip()
                fig_name = Path(fig_path).name
                host_path = output_dir / fig_name
                if host_path.exists():
                    figures.append(str(host_path))
        return figures


def execute_code(
    code: str,
    datasets: list[dict] | None = None,
    timeout: int | None = None,
) -> CodeResult:
    """
    在Docker容器中执行Python代码（便捷函数）

    Args:
        code: 要执行的Python代码
        datasets: 数据集列表
        timeout: 超时时间（秒）

    Returns:
        CodeResult 结构化结果
    """
    sandbox = DockerSandbox()
    return sandbox.execute(code, datasets, timeout)
