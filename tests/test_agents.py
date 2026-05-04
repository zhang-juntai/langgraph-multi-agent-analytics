"""
Agent 功能测试
测试 DataProfiler 和 Debugger 的核心逻辑（不需要 LLM API）。
CodeGenerator 需要 LLM API，标记为集成测试。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestDataProfiler:
    """测试 DataProfiler Agent"""

    def test_profiler_without_data(self):
        """没有数据集时应返回友好提示"""
        from src.agents.data_profiler import data_profiler_node

        state = {"datasets": [], "messages": []}
        result = data_profiler_node(state)

        assert "error" in result
        assert any("上传" in m.content for m in result.get("messages", []))

    def test_profiler_with_data(self, sample_csv_path):
        """有数据集时应成功执行分析"""
        from src.agents.data_profiler import data_profiler_node

        state = {
            "datasets": [{
                "file_name": "sales_data.csv",
                "file_path": sample_csv_path,
                "num_rows": 240,
                "num_cols": 7,
                "columns": ["日期", "产品", "地区", "销量", "单价", "总金额", "客户评分"],
                "dtypes": {"日期": "object", "产品": "object", "地区": "object",
                          "销量": "int64", "单价": "int64", "总金额": "int64", "客户评分": "float64"},
                "preview": "...",
                "missing_info": {"客户评分": 24},
            }],
            "active_dataset_index": 0,
            "messages": [],
            "figures": [],
        }

        result = data_profiler_node(state)

        # 应该有消息返回
        assert "messages" in result
        assert len(result["messages"]) > 0

        # 消息中应包含分析结果
        content = result["messages"][0].content
        assert "数据探索分析" in content or "描述性统计" in content

    def test_profiler_generates_code(self, sample_csv_path):
        """应生成代码记录"""
        from src.agents.data_profiler import data_profiler_node

        state = {
            "datasets": [{
                "file_name": "sales_data.csv",
                "file_path": sample_csv_path,
                "num_rows": 240,
                "num_cols": 7,
                "columns": ["日期", "产品", "地区", "销量", "单价", "总金额", "客户评分"],
                "dtypes": {},
                "preview": "...",
                "missing_info": {},
            }],
            "active_dataset_index": 0,
            "messages": [],
            "figures": [],
        }

        result = data_profiler_node(state)
        assert "current_code" in result
        assert len(result["current_code"]) > 0


class TestDebugger:
    """测试 Debugger 的控制逻辑"""

    def test_should_retry_on_success(self):
        """成功时应返回 done"""
        from src.agents.debugger import should_retry

        state = {
            "code_result": {"success": True},
            "retry_count": 0,
        }
        assert should_retry(state) == "done"

    def test_should_retry_on_failure(self):
        """失败且未超限时应返回 retry"""
        from src.agents.debugger import should_retry

        state = {
            "code_result": {"success": False},
            "retry_count": 1,
        }
        assert should_retry(state) == "retry"

    def test_should_stop_on_max_retries(self):
        """超过最大重试次数时应返回 done"""
        from src.agents.debugger import should_retry, MAX_RETRIES

        state = {
            "code_result": {"success": False},
            "retry_count": MAX_RETRIES,
        }
        assert should_retry(state) == "done"

    def test_debugger_node_exceeds_max_retries(self):
        """超过重试次数时应降级"""
        from src.agents.debugger import debugger_node, MAX_RETRIES

        state = {
            "code_result": {"stderr": "some error", "success": False},
            "current_code": "broken code",
            "retry_count": MAX_RETRIES,
            "datasets": [],
            "messages": [],
        }

        result = debugger_node(state)
        # 应该包含友好的降级提示
        content = result["messages"][0].content
        assert "失败" in content or str(MAX_RETRIES) in content
        # retry_count 应重置
        assert result.get("retry_count", -1) == 0
