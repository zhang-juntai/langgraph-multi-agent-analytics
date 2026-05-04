"""Read-only business database access contract for enterprise deployments.

P1 keeps this as a controlled adapter boundary. Agents should not receive raw
credentials. They receive registered source descriptors, and future SQL tasks
must pass through SELECT-only validation before materializing query results.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from configs.settings import settings

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|merge|grant|revoke|call|execute)\b",
    re.IGNORECASE,
)


def get_registered_database_sources() -> list[dict[str, Any]]:
    """Load read-only database source descriptors from DATABASE_SOURCES_JSON.

    Example:
    [
      {
        "alias": "sales_dw",
        "dialect": "postgres",
        "read_only": true,
        "allowed_schemas": ["mart"],
        "connection_ref": "SALES_DW_URI"
      }
    ]
    """

    raw = os.getenv("DATABASE_SOURCES_JSON", "").strip()
    if not raw:
        return []
    sources = json.loads(raw)
    result = []
    for source in sources:
        item = dict(source)
        item["read_only"] = item.get("read_only", True)
        # Never expose the actual connection string to the LLM/state.
        item["connection_uri_configured"] = bool(os.getenv(item.get("connection_ref", "")))
        result.append(item)
    return result


def validate_read_only_sql(sql: str, allowed_schemas: list[str] | None = None) -> None:
    """Raise ValueError when SQL is not safe for read-only execution."""
    sql_clean = sql.strip().rstrip(";")
    if not sql_clean.lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed.")
    if ";" in sql_clean:
        raise ValueError("Multiple SQL statements are not allowed.")
    if FORBIDDEN_SQL.search(sql_clean):
        raise ValueError("SQL contains forbidden write/admin keywords.")

    schemas = allowed_schemas or []
    if schemas:
        lower_sql = sql_clean.lower()
        if not any(f"{schema.lower()}." in lower_sql for schema in schemas):
            raise ValueError("SQL must reference an allowed schema explicitly.")


def materialize_query_to_local_dataset(
    source: dict[str, Any],
    sql: str,
    session_id: str,
    sql_validation: dict[str, Any] | None = None,
) -> dict:
    """Execute a validated read-only query and save the result as a local CSV.

    Supported now:
    - sqlite via pandas/read_sql_query and sqlite3

    Planned production adapters:
    - postgres via psycopg2/sqlalchemy with read-only transaction
    - mysql via pymysql/sqlalchemy with read-only user
    """

    if not sql_validation or sql_validation.get("status") != "passed":
        raise ValueError("SQL validation has not passed. Refusing to execute database query.")

    validate_read_only_sql(sql, source.get("allowed_schemas", []))

    dialect = source.get("dialect", "").lower()
    conn_ref = source.get("connection_ref", "")
    conn_uri = os.getenv(conn_ref, "")
    if not conn_uri:
        raise ValueError(f"Database connection is not configured for {source.get('alias')}.")

    if dialect != "sqlite":
        raise NotImplementedError(
            "P1 includes the read-only database contract. Non-sqlite adapters should "
            "be enabled in P2 with SQL audit logging and connection pooling."
        )

    import sqlite3

    execution_sql = _sqlite_execution_sql(sql, source.get("allowed_schemas", []))
    with sqlite3.connect(conn_uri) as conn:
        df = pd.read_sql_query(execution_sql, conn)

    output_dir = settings.DATA_DIR / "database_extracts" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:8]
    path = output_dir / f"{source.get('alias', 'db')}_{file_id}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")

    return {
        "file_name": path.name,
        "file_path": str(path),
        "source_type": "database",
        "source_ref": source.get("alias", ""),
        "query": sql,
        "executed_query": execution_sql,
        "num_rows": int(df.shape[0]),
        "num_cols": int(df.shape[1]),
        "columns": [str(col) for col in df.columns],
        "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
        "preview": df.head(10).to_csv(index=False),
        "missing_info": {str(col): int(df[col].isna().sum()) for col in df.columns},
    }


def _sqlite_execution_sql(sql: str, allowed_schemas: list[str] | None = None) -> str:
    """Adapt governed schema-qualified SQL to local SQLite fixture tables."""

    execution_sql = sql
    for schema in allowed_schemas or []:
        execution_sql = re.sub(
            rf"\b{re.escape(schema)}\.",
            "",
            execution_sql,
            flags=re.IGNORECASE,
        )
    return execution_sql
