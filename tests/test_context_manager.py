"""
长会话上下文管理测试
"""
import sys
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, AIMessage

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.context_manager import (
    trim_messages,
    summarize_old_messages,
    build_optimized_context,
)


class TestTrimMessages:
    """测试消息截断"""

    def test_short_conversation_unchanged(self):
        """短对话不截断"""
        msgs = [HumanMessage(content=f"msg{i}") for i in range(5)]
        result = trim_messages(msgs, window_size=10)
        assert len(result) == 5

    def test_long_conversation_trimmed(self):
        """长对话截断到窗口大小+1"""
        msgs = [HumanMessage(content=f"消息{i}") for i in range(30)]
        result = trim_messages(msgs, window_size=5)
        # 第一条 + 最近5条
        assert len(result) <= 6
        assert result[0].content == "消息0"  # 保留第一条
        assert result[-1].content == "消息29"  # 保留最后一条


class TestSummarizeMessages:
    """测试消息摘要"""

    def test_short_no_summary(self):
        """短对话不产生摘要"""
        msgs = [HumanMessage(content="hello")]
        summary, recent = summarize_old_messages(msgs, window_size=10)
        assert summary == ""
        assert len(recent) == 1

    def test_long_produces_summary(self):
        """长对话产生摘要"""
        msgs = []
        for i in range(20):
            msgs.append(HumanMessage(content=f"用户问题 {i}: 请分析销售数据"))
            msgs.append(AIMessage(content=f"✅ 统计分析完成，第{i}轮结果"))

        summary, recent = summarize_old_messages(msgs, window_size=6)
        assert len(summary) > 0
        assert len(recent) == 6
        assert "用户" in summary or "分析" in summary


class TestBuildOptimizedContext:
    """测试完整上下文构建"""

    def test_basic_context(self):
        """基本上下文构建"""
        msgs = [HumanMessage(content="分析数据")]
        datasets = [{"file_name": "data.csv", "num_rows": 100, "num_cols": 5, "columns": ["a", "b"]}]

        ctx = build_optimized_context(msgs, datasets=datasets)
        assert "data.csv" in ctx["dataset_context"]
        assert len(ctx["recent_messages"]) == 1
        assert ctx["total_chars"] > 0
        assert ctx["estimated_tokens"] > 0

    def test_with_memory(self):
        """带记忆上下文"""
        msgs = [HumanMessage(content="hello")]
        ctx = build_optimized_context(
            msgs,
            memory_context="用户偏好蓝色配色",
        )
        assert ctx["memory_context"] == "用户偏好蓝色配色"
