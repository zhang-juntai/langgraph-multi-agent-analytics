"""
State 定义的基础测试
验证 TypedDict 的结构和类型约束。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.state import AnalysisState, DatasetMeta, CodeResult


class TestAnalysisState:
    """测试 AnalysisState 结构"""

    def test_state_creation(self):
        """应该能创建带有部分字段的 State"""
        state: AnalysisState = {
            "messages": [],
            "task_type": "chat",
            "datasets": [],
        }
        assert state["task_type"] == "chat"
        assert len(state["messages"]) == 0

    def test_dataset_meta_creation(self):
        """应该能创建 DatasetMeta"""
        meta: DatasetMeta = {
            "file_name": "test.csv",
            "file_path": "/tmp/test.csv",
            "num_rows": 100,
            "num_cols": 5,
            "columns": ["a", "b", "c", "d", "e"],
            "dtypes": {"a": "int64", "b": "float64", "c": "object", "d": "int64", "e": "float64"},
            "preview": "a b c d e\n1 2 x 3 4",
            "missing_info": {"c": 5},
        }
        assert meta["num_rows"] == 100
        assert len(meta["columns"]) == 5

    def test_code_result_creation(self):
        """应该能创建 CodeResult"""
        result: CodeResult = {
            "code": "print('hello')",
            "stdout": "hello\n",
            "stderr": "",
            "success": True,
            "figures": [],
            "dataframes": {},
        }
        assert result["success"] is True
        assert result["stdout"] == "hello\n"
