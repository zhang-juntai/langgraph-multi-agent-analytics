"""
多文件关系发现服务

自动分析表之间的关联关系（主键-外键），
支持跨表查询和代码生成。
"""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from configs.settings import settings

logger = logging.getLogger(__name__)

# 关系类型
RELATION_TYPES = {
    "foreign_key": "外键关系",
    "same_values": "值域相同",
    "name_similarity": "列名相似",
}


class RelationshipDiscovery:
    """自动发现表间关系"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or settings.PROJECT_ROOT / "data" / "sessions.db")
        self._init_tables()

    def _init_tables(self):
        """初始化关系存储表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS table_relations (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    from_table TEXT NOT NULL,
                    from_column TEXT NOT NULL,
                    to_table TEXT NOT NULL,
                    to_column TEXT NOT NULL,
                    relation_type TEXT DEFAULT 'foreign_key',
                    confidence REAL DEFAULT 0.5,
                    sample_values TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_relations_session
                    ON table_relations(session_id);
            """)
        logger.info("Relationship tables initialized")

    def discover_relations(
        self,
        session_id: str,
        datasets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        分析多个数据集，发现可能的关联关系

        Args:
            session_id: 会话 ID
            datasets: 数据集列表，每个包含 file_name, columns, preview 等

        Returns:
            发现的关系列表
        """
        if len(datasets) < 2:
            logger.info("只有一个数据集，跳过关系发现")
            return []

        relations = []

        # 提取所有表和列的信息
        table_columns = {}
        for ds in datasets:
            table_name = Path(ds.get("file_name", "unknown")).stem
            columns = ds.get("columns", [])
            preview = ds.get("preview", [])
            table_columns[table_name] = {
                "columns": columns,
                "preview": preview,
            }

        # 比较每对表
        table_names = list(table_columns.keys())
        for i, table_a in enumerate(table_names):
            for table_b in table_names[i + 1:]:
                # 检查 A -> B 的关系
                found_relations = self._find_relations_between(
                    table_a, table_columns[table_a],
                    table_b, table_columns[table_b],
                )
                relations.extend(found_relations)

                # 检查 B -> A 的关系
                found_relations = self._find_relations_between(
                    table_b, table_columns[table_b],
                    table_a, table_columns[table_a],
                )
                relations.extend(found_relations)

        # 存储到数据库
        if relations:
            self._save_relations(session_id, relations)

        logger.info(f"发现 {len(relations)} 个潜在关系")
        return relations

    def _find_relations_between(
        self,
        table_a: str,
        info_a: dict,
        table_b: str,
        info_b: dict,
    ) -> list[dict[str, Any]]:
        """查找从 A 到 B 的关系"""
        relations = []
        cols_a = info_a.get("columns", [])
        cols_b = info_b.get("columns", [])
        preview_a = info_a.get("preview", [])
        preview_b = info_b.get("preview", [])

        for col_a in cols_a:
            for col_b in cols_b:
                confidence = 0.0
                relation_type = "unknown"

                # 1. 检查列名相似性
                name_sim = self._name_similarity(col_a, col_b)
                if name_sim > 0.7:
                    confidence = max(confidence, name_sim * 0.7)
                    relation_type = "name_similarity"

                # 2. 检查值域重叠（如果有预览数据）
                if preview_a and preview_b:
                    try:
                        # 获取列索引
                        idx_a = cols_a.index(col_a)
                        idx_b = cols_b.index(col_b)

                        # 提取值
                        values_a = set()
                        values_b = set()
                        for row in preview_a[:100]:
                            if idx_a < len(row):
                                values_a.add(str(row[idx_a]))
                        for row in preview_b[:100]:
                            if idx_b < len(row):
                                values_b.add(str(row[idx_b]))

                        # 计算重叠
                        if values_a and values_b:
                            overlap = self._value_overlap(values_a, values_b)
                            if overlap > 0.5:
                                # 如果 A 的值都在 B 中，可能是外键
                                confidence = max(confidence, overlap)
                                relation_type = "foreign_key"
                    except Exception as e:
                        logger.debug(f"值域分析失败: {e}")

                # 3. 检查 ID 模式
                if self._is_id_column(col_a) and self._is_id_column(col_b):
                    if name_sim > 0.5:
                        confidence = max(confidence, 0.8)
                        relation_type = "foreign_key"

                # 如果置信度足够高，记录关系
                if confidence >= 0.5:
                    relations.append({
                        "from_table": table_a,
                        "from_column": col_a,
                        "to_table": table_b,
                        "to_column": col_b,
                        "relation_type": relation_type,
                        "confidence": round(confidence, 2),
                    })

        return relations

    def _name_similarity(self, name_a: str, name_b: str) -> float:
        """计算列名相似度"""
        a_lower = name_a.lower().replace("_", "")
        b_lower = name_b.lower().replace("_", "")

        # 完全相同
        if a_lower == b_lower:
            return 1.0

        # 包含关系
        if a_lower in b_lower or b_lower in a_lower:
            return 0.8

        # 常见模式：customer_id vs id
        if a_lower.endswith("id") and b_lower == "id":
            prefix = a_lower[:-2]
            if prefix in b_lower:
                return 0.9

        if b_lower.endswith("id") and a_lower == "id":
            prefix = b_lower[:-2]
            if prefix in a_lower:
                return 0.9

        # 简单字符重叠
        common = sum(1 for c in a_lower if c in b_lower)
        return common / max(len(a_lower), len(b_lower), 1)

    def _value_overlap(self, values_a: set, values_b: set) -> float:
        """计算值域重叠度"""
        if not values_a or not values_b:
            return 0.0

        # A 的值有多少在 B 中出现
        common = len(values_a & values_b)
        return common / len(values_a)

    def _is_id_column(self, col_name: str) -> bool:
        """检测是否是 ID 列"""
        col_lower = col_name.lower()
        patterns = ["id", "_id", "pk", "key", "code"]
        return any(p in col_lower for p in patterns)

    def _save_relations(self, session_id: str, relations: list[dict]):
        """保存关系到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            for rel in relations:
                rel_id = str(uuid.uuid4())[:8]
                conn.execute("""
                    INSERT INTO table_relations
                    (id, session_id, from_table, from_column, to_table, to_column,
                     relation_type, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel_id, session_id,
                    rel["from_table"], rel["from_column"],
                    rel["to_table"], rel["to_column"],
                    rel["relation_type"], rel["confidence"]
                ))
        logger.info(f"保存了 {len(relations)} 个关系到数据库")

    def get_relations(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话的所有表关系"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM table_relations
                WHERE session_id = ?
                ORDER BY confidence DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_relations(self, session_id: str):
        """删除会话的所有关系"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM table_relations WHERE session_id = ?", (session_id,))

    def format_relations_for_prompt(self, session_id: str) -> str:
        """格式化关系信息，用于注入到 LLM 提示词"""
        relations = self.get_relations(session_id)
        if not relations:
            return "未发现表间关联关系"

        lines = ["## 发现的表间关联关系\n"]
        for rel in relations:
            lines.append(
                f"- **{rel['from_table']}.{rel['from_column']}** → "
                f"**{rel['to_table']}.{rel['to_column']}** "
                f"(置信度: {rel['confidence']:.0%}, 类型: {rel['relation_type']})"
            )

        lines.append("\n在生成 SQL 或 pandas 代码时，可以利用这些关系进行 JOIN 操作。")
        return "\n".join(lines)


# 全局实例
_discovery_instance: RelationshipDiscovery | None = None


def get_relationship_discovery() -> RelationshipDiscovery:
    """获取全局关系发现实例"""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = RelationshipDiscovery()
    return _discovery_instance