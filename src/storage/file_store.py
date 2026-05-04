"""
文件存储服务 - 统一管理文件上传和图片存储

支持混合存储:
- 小文件 (< 1MB): 存储到数据库 BLOB
- 大文件 (>= 1MB): 存储到文件系统，数据库只存路径
"""
from __future__ import annotations

import base64
import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 大小阈值: 1MB
SIZE_THRESHOLD = 1 * 1024 * 1024


class FileStorageService:
    """文件存储服务"""

    def __init__(self, db_path: str = "data/sessions.db", storage_dir: str = "data/storage"):
        self.db_path = db_path
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """初始化存储表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS file_storage (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content BLOB,
                    storage_path TEXT,
                    storage_type TEXT DEFAULT 'database',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS figure_storage (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    execution_id TEXT,
                    name TEXT NOT NULL,
                    format TEXT DEFAULT 'png',
                    width INTEGER,
                    height INTEGER,
                    content BLOB,
                    base64 TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_file_storage_session
                ON file_storage(session_id);
                CREATE INDEX IF NOT EXISTS idx_figure_storage_session
                ON figure_storage(session_id);
            """)
        logger.info("File storage tables initialized")

    def store_file(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        mime_type: str | None = None,
    ) -> str:
        """
        存储上传的文件

        Args:
            session_id: 会话 ID
            filename: 文件名
            content: 文件内容 (bytes)
            mime_type: MIME 类型

        Returns:
            file_storage_id
        """
        file_id = str(uuid.uuid4())
        size = len(content)

        # 自动检测 MIME 类型
        if mime_type is None:
            ext = Path(filename).suffix.lower()
            mime_map = {
                '.csv': 'text/csv',
                '.tsv': 'text/tab-separated-values',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.xls': 'application/vnd.ms-excel',
                '.json': 'application/json',
                '.txt': 'text/plain',
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')

        # 决定存储方式
        if size >= SIZE_THRESHOLD:
            # 大文件: 存储到文件系统
            storage_path = self.storage_dir / session_id / f"{file_id}_{filename}"
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            storage_path.write_bytes(content)
            storage_type = 'filesystem'
            content_blob = None
            logger.info(f"Large file stored to filesystem: {storage_path}")
        else:
            # 小文件: 存储到数据库
            storage_path = None
            storage_type = 'database'
            content_blob = content

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO file_storage
                (id, session_id, filename, mime_type, size_bytes, content, storage_path, storage_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, session_id, filename, mime_type, size, content_blob,
                  str(storage_path) if storage_path else None, storage_type))

        logger.info(f"Stored file: {filename} ({size} bytes, {storage_type})")
        return file_id

    def get_file(self, file_id: str) -> bytes | None:
        """获取文件内容"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content, storage_path, storage_type
                FROM file_storage WHERE id = ?
            """, (file_id,))
            row = cursor.fetchone()

            if not row:
                return None

            content, storage_path, storage_type = row

            if storage_type == 'database' and content:
                return bytes(content)
            elif storage_path:
                path = Path(storage_path)
                if path.exists():
                    return path.read_bytes()

        return None

    def get_file_info(self, file_id: str) -> dict | None:
        """获取文件元信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, session_id, filename, mime_type, size_bytes,
                       storage_type, created_at
                FROM file_storage WHERE id = ?
            """, (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def store_figure(
        self,
        session_id: str,
        content: bytes,
        name: str = "figure",
        execution_id: str | None = None,
        format: str = "png",
        width: int | None = None,
        height: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        存储生成的图表

        Args:
            session_id: 会话 ID
            content: 图片内容 (bytes)
            name: 图表名称
            execution_id: 执行 ID
            format: 格式 (png/svg/jpg)
            width: 宽度
            height: 高度
            metadata: 元数据

        Returns:
            figure_storage_id
        """
        figure_id = str(uuid.uuid4())
        base64_str = base64.b64encode(content).decode('utf-8')
        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO figure_storage
                (id, session_id, execution_id, name, format, width, height, content, base64, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (figure_id, session_id, execution_id, name, format,
                  width, height, content, base64_str, metadata_json))

        logger.info(f"Stored figure: {name}.{format} ({len(content)} bytes)")
        return figure_id

    def get_figure(self, figure_id: str) -> tuple[bytes, str, str] | None:
        """
        获取图表内容

        Returns:
            (content, format, base64) or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content, format, base64 FROM figure_storage WHERE id = ?
            """, (figure_id,))
            row = cursor.fetchone()
            if row:
                return bytes(row[0]), row[1], row[2]  # content, format, base64
            return None

    def get_figure_base64(self, figure_id: str) -> str | None:
        """
        获取图表的 Base64 编码 (前端直接使用)

        Returns:
            data:image/png;base64,... 格式的字符串
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT base64, format FROM figure_storage WHERE id = ?
            """, (figure_id,))
            row = cursor.fetchone()
            if row:
                return f"data:image/{row[1]};base64,{row[0]}"
            return None

    def get_figure_info(self, figure_id: str) -> dict | None:
        """获取图表元信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, session_id, execution_id, name, format,
                       width, height, metadata, created_at
                FROM figure_storage WHERE id = ?
            """, (figure_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                return result
            return None

    def delete_session_files(self, session_id: str) -> int:
        """删除会话的所有文件"""
        deleted = 0

        with sqlite3.connect(self.db_path) as conn:
            # 删除文件系统中的大文件
            cursor = conn.execute("""
                SELECT storage_path FROM file_storage
                WHERE session_id = ? AND storage_type = 'filesystem'
            """, (session_id,))

            for (path_str,) in cursor.fetchall():
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        path.unlink()
                        deleted += 1

            # 删除数据库记录
            conn.execute("DELETE FROM file_storage WHERE session_id = ?", (session_id,))
            figure_count = conn.execute(
                "SELECT COUNT(*) FROM figure_storage WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM figure_storage WHERE session_id = ?", (session_id,))

        deleted += figure_count
        logger.info(f"Deleted {deleted} files for session {session_id}")
        return deleted

    def list_session_files(self, session_id: str) -> list[dict]:
        """列出会话的所有文件"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, filename, mime_type, size_bytes, storage_type, created_at
                FROM file_storage WHERE session_id = ?
                ORDER BY created_at DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def list_session_figures(self, session_id: str) -> list[dict]:
        """列出会话的所有图表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, name, format, width, height, created_at
                FROM figure_storage WHERE session_id = ?
                ORDER BY created_at DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_storage_stats(self) -> dict:
        """获取存储统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            file_count = conn.execute("SELECT COUNT(*) FROM file_storage").fetchone()[0]
            figure_count = conn.execute("SELECT COUNT(*) FROM figure_storage").fetchone()[0]

            db_size = conn.execute("""
                SELECT COALESCE(SUM(size_bytes), 0) FROM file_storage
                WHERE storage_type = 'database'
            """).fetchone()[0]

            figure_size = conn.execute("""
                SELECT COALESCE(SUM(LENGTH(content)), 0) FROM figure_storage
            """).fetchone()[0]

        return {
            "file_count": file_count,
            "figure_count": figure_count,
            "database_size_bytes": db_size + figure_size,
            "database_size_mb": round((db_size + figure_size) / 1024 / 1024, 2),
        }


# 全局实例
_file_store: FileStorageService | None = None


def get_file_store() -> FileStorageService:
    """获取全局文件存储实例"""
    global _file_store
    if _file_store is None:
        _file_store = FileStorageService()
    return _file_store
