"""
沙箱工厂
根据配置选择沙箱执行器实现
"""
from __future__ import annotations

import logging
from typing import Callable, Protocol, runtime_checkable

from src.graph.state import CodeResult
from configs.settings import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class SandboxExecutor(Protocol):
    """沙箱执行器协议"""

    def execute(
        self,
        code: str,
        datasets: list[dict] | None = None,
        timeout: int | None = None,
    ) -> CodeResult:
        """执行代码并返回结果"""
        ...


def get_sandbox() -> Callable:
    """
    根据配置返回沙箱执行函数

    Returns:
        执行函数，签名为 execute_code(code, datasets, timeout) -> CodeResult
    """
    sandbox_type = settings.SANDBOX_TYPE

    if sandbox_type == "docker":
        logger.info("使用Docker沙箱执行器")
        from src.sandbox.docker_executor import execute_code
        return execute_code
    else:
        logger.info("使用subprocess沙箱执行器")
        from src.sandbox.executor import execute_code
        return execute_code


def get_sandbox_executor() -> SandboxExecutor:
    """
    获取沙箱执行器实例

    Returns:
        沙箱执行器对象
    """
    sandbox_type = settings.SANDBOX_TYPE

    if sandbox_type == "docker":
        from src.sandbox.docker_executor import DockerSandbox
        return DockerSandbox()
    else:
        # subprocess执行器是函数式接口，包装成对象
        from src.sandbox.executor import execute_code as subprocess_execute

        class SubprocessSandbox:
            def execute(
                self,
                code: str,
                datasets: list[dict] | None = None,
                timeout: int | None = None,
            ) -> CodeResult:
                return subprocess_execute(code, datasets, timeout)

        return SubprocessSandbox()


# 便捷函数
def execute_in_sandbox(
    code: str,
    datasets: list[dict] | None = None,
    timeout: int | None = None,
) -> CodeResult:
    """
    在配置的沙箱中执行代码

    Args:
        code: 要执行的Python代码
        datasets: 数据集列表
        timeout: 超时时间（秒）

    Returns:
        CodeResult 结构化结果
    """
    executor = get_sandbox()
    return executor(code, datasets, timeout)
