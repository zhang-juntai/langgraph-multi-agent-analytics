"""
记忆系统测试
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.memory.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path):
    """创建临时数据库的 MemoryStore"""
    return MemoryStore(db_path=tmp_path / "test_memory.db")


class TestMemoryStore:
    """测试记忆系统"""

    def test_remember_and_recall(self, store):
        """存储后应能检索"""
        store.remember("preference", "chart_color", "蓝色系配色")
        results = store.recall(memory_type="preference")
        assert len(results) == 1
        assert results[0]["value"] == "蓝色系配色"

    def test_remember_upsert(self, store):
        """相同 key 应更新而非重复"""
        store.remember("preference", "chart_color", "蓝色")
        store.remember("preference", "chart_color", "红色")
        results = store.recall(memory_type="preference")
        assert len(results) == 1
        assert results[0]["value"] == "红色"

    def test_search(self, store):
        """模糊搜索应匹配 key/value/tags"""
        store.remember("knowledge", "sales_missing", "revenue 列有 5% 缺失", tags=["缺失值", "sales"])
        store.remember("knowledge", "date_format", "日期格式为 YYYY-MM-DD")

        results = store.search("缺失")
        assert len(results) == 1
        assert "revenue" in results[0]["value"]

        results = store.search("sales")
        assert len(results) == 1

    def test_forget(self, store):
        """删除记忆"""
        store.remember("preference", "temp", "临时记忆")
        store.forget(key="temp")
        results = store.recall(key="temp")
        assert len(results) == 0

    def test_importance_ordering(self, store):
        """高重要度记忆应排在前面"""
        store.remember("preference", "low", "低重要度", importance=1.0)
        store.remember("preference", "high", "高重要度", importance=10.0)
        results = store.recall(memory_type="preference")
        assert results[0]["key"] == "high"

    def test_context_for_llm(self, store):
        """应能生成 LLM 上下文"""
        store.remember("preference", "color", "蓝色配色")
        store.remember("knowledge", "data_info", "sales 数据有 240 行")
        context = store.get_context_for_llm()
        assert "蓝色" in context
        assert "240" in context

    def test_context_empty(self, store):
        """无记忆时返回空"""
        context = store.get_context_for_llm()
        assert context == ""

    def test_count(self, store):
        """计数应准确"""
        assert store.count == 0
        store.remember("preference", "a", "1")
        store.remember("knowledge", "b", "2")
        assert store.count == 2

    def test_tags_stored_and_returned(self, store):
        """标签应正确存储和返回"""
        store.remember("knowledge", "info", "test", tags=["tag1", "tag2"])
        results = store.recall(key="info")
        assert "tag1" in results[0]["tags"]
        assert "tag2" in results[0]["tags"]
