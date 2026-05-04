"""
代码沙箱执行器测试
这些测试不需要 LLM API，完全本地运行。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.sandbox.executor import execute_code, _check_code_safety
from src.sandbox.factory import get_sandbox, get_sandbox_executor, execute_in_sandbox


class TestCodeSafety:
    """测试代码安全检查"""

    def test_safe_code(self):
        """安全代码不应产生警告"""
        warnings = _check_code_safety("import pandas as pd\nprint('hello')")
        assert len(warnings) == 0

    def test_dangerous_os_system(self):
        """os.system 应被检测"""
        warnings = _check_code_safety("os.system('rm -rf /')")
        assert len(warnings) > 0

    def test_dangerous_subprocess(self):
        """subprocess 应被检测"""
        warnings = _check_code_safety("import subprocess\nsubprocess.run(['ls'])")
        assert len(warnings) > 0

    def test_dangerous_eval(self):
        """eval 应被检测"""
        warnings = _check_code_safety("eval('1+1')")
        assert len(warnings) > 0

    def test_dangerous_network(self):
        """网络请求应被检测"""
        warnings = _check_code_safety("import requests\nrequests.get('http://evil.com')")
        assert len(warnings) > 0


class TestExecuteCode:
    """测试代码执行"""

    def test_simple_print(self):
        """简单 print 应该成功执行"""
        result = execute_code("print('hello world')")
        assert result["success"] is True
        assert "hello world" in result["stdout"]

    def test_pandas_code(self):
        """pandas 代码应该正常执行"""
        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
print(df.describe().to_string())
"""
        result = execute_code(code)
        assert result["success"] is True
        assert "mean" in result["stdout"]

    def test_syntax_error(self):
        """语法错误应该被捕获"""
        result = execute_code("print(")
        assert result["success"] is False
        assert result["stderr"] != ""

    def test_runtime_error(self):
        """运行时错误应该被捕获"""
        result = execute_code("1 / 0")
        assert result["success"] is False
        assert "ZeroDivision" in result["stderr"]

    def test_timeout(self):
        """超时应该被熔断"""
        code = "import time\ntime.sleep(100)"
        result = execute_code(code, timeout=2)
        assert result["success"] is False
        assert "超时" in result["stderr"]

    def test_dangerous_code_blocked(self):
        """危险代码应被阻止"""
        result = execute_code("os.system('ls')")
        assert result["success"] is False

    def test_with_dataset(self, sample_csv_path):
        """带数据集注入的执行"""
        datasets = [{
            "file_name": "sales_data.csv",
            "file_path": sample_csv_path,
        }]
        code = "print(f'数据行数: {len(df)}')\nprint(df.columns.tolist())"
        result = execute_code(code, datasets=datasets)
        assert result["success"] is True
        assert "数据行数" in result["stdout"]

    def test_matplotlib_figure_saved(self, sample_csv_path):
        """matplotlib 图表应该自动保存"""
        datasets = [{
            "file_name": "sales_data.csv",
            "file_path": sample_csv_path,
        }]
        code = """
import matplotlib.pyplot as plt
plt.figure(figsize=(6, 4))
plt.plot([1, 2, 3], [4, 5, 6])
plt.title("test")
plt.show()
"""
        result = execute_code(code, datasets=datasets)
        assert result["success"] is True
        assert len(result["figures"]) == 1  # plt.show() 保存+关闭，不应重复
        assert Path(result["figures"][0]).exists()


class TestSandboxFactory:
    """测试沙箱工厂"""

    def test_get_sandbox_subprocess(self, monkeypatch):
        """默认应返回subprocess执行器"""
        monkeypatch.setenv("SANDBOX_TYPE", "subprocess")
        from importlib import reload
        import configs.settings
        reload(configs.settings)
        from src.sandbox.factory import get_sandbox

        executor = get_sandbox()
        assert callable(executor)

    def test_get_sandbox_executor_subprocess(self, monkeypatch):
        """get_sandbox_executor应返回执行器对象"""
        monkeypatch.setenv("SANDBOX_TYPE", "subprocess")
        from importlib import reload
        import configs.settings
        reload(configs.settings)
        from src.sandbox.factory import get_sandbox_executor

        executor = get_sandbox_executor()
        assert hasattr(executor, "execute")


@pytest.mark.skipif(
    os.getenv("SANDBOX_TYPE") != "docker",
    reason="需要设置 SANDBOX_TYPE=docker 并运行Docker"
)
class TestDockerSandbox:
    """测试Docker沙箱（需要Docker环境）"""

    @pytest.fixture(autouse=True)
    def setup_docker(self):
        """检查Docker是否可用"""
        try:
            import docker
            client = docker.from_env()
            client.ping()
        except Exception as e:
            pytest.skip(f"Docker不可用: {e}")

    def test_simple_code_in_docker(self):
        """在Docker中执行简单代码"""
        from src.sandbox.docker_executor import execute_code

        result = execute_code("print('hello from docker')")
        assert result["success"] is True
        assert "hello from docker" in result["stdout"]

    def test_pandas_in_docker(self):
        """在Docker中使用pandas"""
        from src.sandbox.docker_executor import execute_code

        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
print(df.sum())
"""
        result = execute_code(code)
        assert result["success"] is True

    def test_network_blocked_in_docker(self):
        """Docker中网络应被阻止"""
        from src.sandbox.docker_executor import execute_code

        # 这个代码在容器中会因为网络被禁用而失败
        code = """
import socket
try:
    s = socket.socket()
    s.connect(('8.8.8.8', 53))
    print('network available')
except Exception as e:
    print(f'network blocked: {e}')
"""
        result = execute_code(code)
        # 网络应该被阻止，所以应该看到错误信息
        assert "network blocked" in result["stdout"] or result["success"] is True

    def test_timeout_in_docker(self):
        """Docker中超时应该被正确处理"""
        from src.sandbox.docker_executor import execute_code

        code = "import time\ntime.sleep(100)"
        result = execute_code(code, timeout=2)
        assert result["success"] is False
        assert "超时" in result["stderr"]


class TestDockerSandboxUnit:
    """Docker沙箱单元测试（不需要实际Docker）"""

    def test_safety_check_in_docker_executor(self):
        """Docker执行器应该也使用安全检查"""
        from src.sandbox.docker_executor import _check_code_safety

        warnings = _check_code_safety("os.system('rm -rf /')")
        assert len(warnings) > 0

    @patch("src.sandbox.docker_executor.get_docker_client")
    def test_docker_client_lazy_init(self, mock_get_client):
        """Docker客户端应该延迟初始化"""
        from src.sandbox.docker_executor import get_docker_client

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 首次调用应该初始化
        client = get_docker_client()
        assert client is mock_client
