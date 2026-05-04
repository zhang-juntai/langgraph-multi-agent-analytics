"""
会话持久化测试
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.persistence.session_store import SessionStore


@pytest.fixture
def store(tmp_path):
    """创建临时数据库的 SessionStore"""
    return SessionStore(db_path=tmp_path / "test_sessions.db")


class TestSessionStore:
    """测试会话持久化"""

    def test_create_and_get_session(self, store):
        """创建会话后应能获取"""
        store.create_session("s1", "测试会话")
        session = store.get_session("s1")
        assert session is not None
        assert session["name"] == "测试会话"

    def test_list_sessions(self, store):
        """应能列出所有会话"""
        store.create_session("s1", "会话1")
        store.create_session("s2", "会话2")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_delete_session(self, store):
        """删除会话后不应再能获取"""
        store.create_session("s1", "临时会话")
        store.delete_session("s1")
        assert store.get_session("s1") is None

    def test_add_and_get_messages(self, store):
        """消息应能存储和检索"""
        store.create_session("s1", "聊天")
        store.add_message("s1", "user", "你好")
        store.add_message("s1", "assistant", "你好！有什么可以帮你的？")
        messages = store.get_messages("s1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_save_and_get_datasets(self, store):
        """数据集元信息应能存储和检索"""
        store.create_session("s1", "分析")
        datasets = [
            {"file_name": "data.csv", "num_rows": 100, "num_cols": 5},
        ]
        store.save_datasets("s1", datasets)
        loaded = store.get_datasets("s1")
        assert len(loaded) == 1
        assert loaded[0]["file_name"] == "data.csv"

    def test_save_artifact(self, store):
        """产物应能存储和检索"""
        store.create_session("s1", "分析")
        store.save_artifact("s1", "code", content="print('hello')")
        store.save_artifact("s1", "report", content="# 报告")
        store.save_artifact("s1", "figure", file_path="/tmp/fig.png")

        all_artifacts = store.get_artifacts("s1")
        assert len(all_artifacts) == 3

        code_artifacts = store.get_artifacts("s1", artifact_type="code")
        assert len(code_artifacts) == 1

    def test_update_session_name(self, store):
        """应能更新会话名称"""
        store.create_session("s1", "旧名")
        store.update_session_name("s1", "新名")
        session = store.get_session("s1")
        assert session["name"] == "新名"

    def test_cascade_delete(self, store):
        """删除会话应同时清理消息和数据集"""
        store.create_session("s1", "临时")
        store.add_message("s1", "user", "test")
        store.save_datasets("s1", [{"file_name": "a.csv"}])
        store.save_artifact("s1", "code", content="x=1")

        store.delete_session("s1")
        assert store.get_messages("s1") == []
        assert store.get_datasets("s1") == []
        assert store.get_artifacts("s1") == []
