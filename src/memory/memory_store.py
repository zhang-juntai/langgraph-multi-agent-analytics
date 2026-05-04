"""
记忆系统 — 跨会话知识积累
用 SQLite 存储用户分析偏好、常用操作、数据集特征等。

记忆类型：
- preference: 用户偏好（如"喜欢用蓝色配色"、"习惯看箱线图"）
- knowledge: 数据知识（如"sales_data 的 revenue 列有 5% 缺失值"）
- pattern: 常用操作模式（如"每次上传后先做描述统计"）

设计原则：
- 记忆由 Agent 在分析过程中自动提取和存储
- 支持语义搜索（基于关键字匹配，未来可升级为向量搜索）
- 记忆有 TTL（过期自动淡化）
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from configs.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = settings.PROJECT_ROOT / "data" / "memory.db"

# 记忆默认 TTL（天）
DEFAULT_TTL_DAYS = 30


class MemoryStore:
    """跨会话记忆存储"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    importance REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_memories_type
                    ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_key
                    ON memories(key);
            """)
            conn.commit()
        finally:
            conn.close()

    def remember(
        self,
        memory_type: str,
        key: str,
        value: str,
        tags: list[str] | None = None,
        importance: float = 1.0,
        ttl_days: int | None = DEFAULT_TTL_DAYS,
    ) -> int:
        """
        存储一条记忆。如果 key 已存在则更新。

        Args:
            memory_type: preference / knowledge / pattern
            key: 唯一标识（如 "color_preference"）
            value: 记忆内容
            tags: 标签列表（用于搜索）
            importance: 重要程度（0-10）
            ttl_days: 有效期（天），None 表示永不过期

        Returns:
            记忆 ID
        """
        now = datetime.now().isoformat()
        expires = None
        if ttl_days:
            expires = (datetime.now() + timedelta(days=ttl_days)).isoformat()

        tags_str = ",".join(tags) if tags else ""

        conn = self._get_conn()
        try:
            # Upsert: 如果 key 存在则更新
            existing = conn.execute(
                "SELECT id FROM memories WHERE memory_type = ? AND key = ?",
                (memory_type, key),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE memories SET value = ?, tags = ?, importance = ?, "
                    "updated_at = ?, expires_at = ? WHERE id = ?",
                    (value, tags_str, importance, now, expires, existing["id"]),
                )
                conn.commit()
                return existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO memories (memory_type, key, value, tags, importance, "
                    "created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (memory_type, key, value, tags_str, importance, now, now, expires),
                )
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def recall(self, memory_type: str = None, key: str = None) -> list[dict]:
        """
        检索记忆。

        Args:
            memory_type: 按类型过滤
            key: 按 key 精确查找

        Returns:
            记忆列表
        """
        conn = self._get_conn()
        try:
            query = "SELECT * FROM memories WHERE 1=1"
            params = []

            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type)
            if key:
                query += " AND key = ?"
                params.append(key)

            # 排除过期记忆
            now = datetime.now().isoformat()
            query += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(now)

            query += " ORDER BY importance DESC, updated_at DESC"

            rows = conn.execute(query, params).fetchall()

            results = []
            for r in rows:
                d = dict(r)
                d["tags"] = d["tags"].split(",") if d["tags"] else []
                results.append(d)

            # 更新访问计数
            for r in results:
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1 WHERE id = ?",
                    (r["id"],),
                )
            conn.commit()

            return results
        finally:
            conn.close()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        模糊搜索记忆（按 key、value、tags）

        Args:
            query: 搜索关键字
            limit: 最大返回数

        Returns:
            匹配的记忆列表
        """
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            pattern = f"%{query}%"
            rows = conn.execute(
                "SELECT * FROM memories "
                "WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?) "
                "AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY importance DESC, updated_at DESC "
                "LIMIT ?",
                (pattern, pattern, pattern, now, limit),
            ).fetchall()

            results = []
            for r in rows:
                d = dict(r)
                d["tags"] = d["tags"].split(",") if d["tags"] else []
                results.append(d)
            return results
        finally:
            conn.close()

    def forget(self, memory_id: int = None, key: str = None):
        """删除记忆"""
        conn = self._get_conn()
        try:
            if memory_id:
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            elif key:
                conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    def get_context_for_llm(self, max_items: int = 10) -> str:
        """
        生成适合注入 LLM 系统提示词的记忆上下文。
        按重要度和最近访问排序，取 top-N。
        """
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            rows = conn.execute(
                "SELECT memory_type, key, value FROM memories "
                "WHERE (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY importance DESC, access_count DESC, updated_at DESC "
                "LIMIT ?",
                (now, max_items),
            ).fetchall()

            if not rows:
                return ""

            lines = ["## 用户记忆（跨会话积累）\n"]
            for r in rows:
                lines.append(f"- [{r['memory_type']}] {r['key']}: {r['value']}")

            return "\n".join(lines)
        finally:
            conn.close()

    def cleanup_expired(self) -> int:
        """清理过期记忆"""
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            conn.commit()
            count = cursor.rowcount
            if count:
                logger.info(f"清理了 {count} 条过期记忆")
            return count
        finally:
            conn.close()

    @property
    def count(self) -> int:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()
            return row["cnt"]
        finally:
            conn.close()


# 全局单例
_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
