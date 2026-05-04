"""
Visualizer Agent 测试
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.visualizer import visualizer_node, _build_dataset_info


class TestVisualizerNode:
    """测试 Visualizer Agent"""

    def test_no_datasets(self):
        """无数据集应返回错误提示"""
        state = {"messages": [], "datasets": []}
        result = visualizer_node(state)
        assert any("上传" in m.content for m in result["messages"])

    def test_build_dataset_info(self):
        """数据集描述构建"""
        state = {
            "datasets": [{
                "file_name": "test.csv",
                "num_rows": 100,
                "num_cols": 5,
                "columns": ["a", "b", "c", "d", "e"],
                "dtypes": {"a": "int64", "b": "float64"},
                "preview": "a,b,c\n1,2,3",
            }],
            "active_dataset_index": 0,
        }
        info = _build_dataset_info(state)
        assert "test.csv" in info
        assert "100" in info
        assert "a, b, c, d, e" in info

    def test_build_dataset_info_no_data(self):
        """空数据集返回提示"""
        state = {"datasets": []}
        info = _build_dataset_info(state)
        assert "暂无" in info


class TestVisualizerIntegration:
    """Visualizer 集成测试（需要 mock LLM）"""

    @patch("src.agents.visualizer.get_llm")
    def test_visualizer_generates_code(self, mock_get_llm, sample_csv_path):
        """Visualizer 应调用 LLM 并执行代码"""
        # Mock LLM 返回简单绘图代码
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="```python\nimport matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.title('test')\nplt.show()\n```"
        )
        mock_get_llm.return_value = mock_llm

        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="画一个折线图")],
            "datasets": [{
                "file_name": "sales_data.csv",
                "file_path": sample_csv_path,
                "num_rows": 240,
                "num_cols": 6,
                "columns": ["date", "product", "sales"],
                "dtypes": {"date": "object", "product": "object", "sales": "int64"},
                "preview": "date,product,sales\n2024-01-01,A,100",
            }],
            "active_dataset_index": 0,
            "figures": [],
        }
        result = visualizer_node(state)

        # 应有回复消息
        assert len(result["messages"]) > 0
        # LLM 应被调用
        assert mock_llm.invoke.called
