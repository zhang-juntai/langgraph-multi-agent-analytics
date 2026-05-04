"""
ReportWriter Agent 测试
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.report_writer import report_writer_node, _build_analysis_context


class TestReportWriterNode:
    """测试 ReportWriter Agent"""

    def test_no_datasets(self):
        """无数据集应返回错误提示"""
        state = {"messages": [], "datasets": []}
        result = report_writer_node(state)
        assert any("上传" in m.content or "暂无" in m.content for m in result["messages"])

    def test_build_analysis_context_empty(self):
        """空状态应返回提示文字"""
        state = {"datasets": [], "messages": []}
        ctx = _build_analysis_context(state)
        assert "暂无" in ctx

    def test_build_analysis_context_with_data(self):
        """有数据时应包含数据集信息"""
        from langchain_core.messages import AIMessage
        state = {
            "datasets": [{
                "file_name": "data.csv",
                "num_rows": 50,
                "num_cols": 3,
                "columns": ["x", "y", "z"],
                "missing_info": {"x": 0, "y": 2},
                "preview": "x,y,z\n1,2,3",
            }],
            "messages": [
                AIMessage(content="✅ 统计分析完成，均值为 3.5"),
            ],
            "current_code": "print(df.describe())",
            "code_result": {"stdout": "count  50"},
            "figures": ["/tmp/fig1.png"],
        }
        ctx = _build_analysis_context(state)
        assert "data.csv" in ctx
        assert "50" in ctx
        assert "统计" in ctx
        assert "describe" in ctx
        assert "1 张" in ctx or "图表" in ctx


class TestReportWriterIntegration:
    """ReportWriter 集成测试（需要 mock LLM）"""

    @patch("src.agents.report_writer.get_llm")
    def test_report_generation(self, mock_get_llm, sample_csv_path):
        """应调用 LLM 生成报告并保存文件"""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="# 数据分析报告\n\n## 摘要\n本次分析了销售数据...\n\n## 关键发现\n1. 发现 A\n2. 发现 B"
        )
        mock_get_llm.return_value = mock_llm

        from langchain_core.messages import HumanMessage

        state = {
            "messages": [HumanMessage(content="生成分析报告")],
            "datasets": [{
                "file_name": "sales_data.csv",
                "file_path": sample_csv_path,
                "num_rows": 240,
                "num_cols": 6,
                "columns": ["date", "product", "sales"],
                "dtypes": {},
                "preview": "date,product,sales",
            }],
            "figures": [],
        }
        result = report_writer_node(state)

        # 应有报告内容
        assert "report" in result
        assert "分析报告" in result["report"]

        # 应有回复消息
        assert len(result["messages"]) > 0
        assert "报告" in result["messages"][0].content

        # LLM 应被调用
        assert mock_llm.invoke.called
