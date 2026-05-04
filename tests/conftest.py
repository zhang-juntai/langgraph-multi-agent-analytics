"""
测试配置和共享 fixtures
"""
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 Python 路径中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_csv_path():
    """返回示例 CSV 文件路径"""
    return str(ROOT / "data" / "sample" / "sales_data.csv")


@pytest.fixture
def sample_state():
    """返回一个基础的 AnalysisState"""
    return {
        "messages": [],
        "datasets": [],
    }
