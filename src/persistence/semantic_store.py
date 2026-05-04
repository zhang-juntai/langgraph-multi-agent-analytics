"""SQLite-backed semantic governance store.

Runtime semantic lookup should use this store. Seed files are only bootstrap
inputs for local development and tests; they are not the authority once rows
exist in the database.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from configs.settings import settings

DEFAULT_DB_PATH = settings.PROJECT_ROOT / "data" / "sessions.db"
DEFAULT_SEED_PATH = settings.PROJECT_ROOT / "configs" / "semantic_seed.json"


def _now() -> str:
    return datetime.now().isoformat()


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _loads(data: str | None, default: Any = None) -> Any:
    if not data:
        return default
    return json.loads(data)


def _checksum(data: Any) -> str:
    return hashlib.sha256(_json(data).encode("utf-8")).hexdigest()


class SemanticStore:
    """Governed semantic metadata store.

    The schema keeps metric identity, versions, synonyms, defaults, role
    permissions, workflow state, and audit events separate so this can migrate
    to PostgreSQL with minimal shape changes.
    """

    def __init__(self, db_path: str | Path | None = None, seed_path: str | Path | None = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.seed_path = Path(seed_path or DEFAULT_SEED_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()
        self.seed_from_file_if_empty()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tables(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS semantic_metrics (
                    semantic_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    business_domain TEXT NOT NULL,
                    definition_scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_version TEXT NOT NULL,
                    business_owner TEXT NOT NULL,
                    technical_owner TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_metric_versions (
                    id TEXT PRIMARY KEY,
                    semantic_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    default_calendar TEXT NOT NULL,
                    default_time_field TEXT NOT NULL,
                    default_source_alias TEXT NOT NULL,
                    default_schema TEXT NOT NULL,
                    visibility_roles_json TEXT NOT NULL,
                    sql_templates_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    approved_by TEXT,
                    published_at TEXT,
                    checksum TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (semantic_id) REFERENCES semantic_metrics(semantic_id) ON DELETE CASCADE,
                    UNIQUE (semantic_id, version)
                );

                CREATE TABLE IF NOT EXISTS semantic_metric_synonyms (
                    id TEXT PRIMARY KEY,
                    semantic_id TEXT NOT NULL,
                    term TEXT NOT NULL,
                    locale TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (semantic_id) REFERENCES semantic_metrics(semantic_id) ON DELETE CASCADE,
                    UNIQUE (semantic_id, term, locale)
                );

                CREATE TABLE IF NOT EXISTS semantic_metric_defaults (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    business_domain TEXT NOT NULL,
                    metric_term TEXT NOT NULL,
                    semantic_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    high_risk_allowed INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (semantic_id) REFERENCES semantic_metrics(semantic_id) ON DELETE CASCADE,
                    UNIQUE (scope_type, scope_id, business_domain, metric_term)
                );

                CREATE TABLE IF NOT EXISTS semantic_role_permissions (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (role, resource_type, resource_id, action)
                );

                CREATE TABLE IF NOT EXISTS semantic_workflows (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    approvers_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_audit_logs (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    before_json TEXT,
                    after_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_access_policies (
                    policy_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    business_domain TEXT NOT NULL,
                    semantic_id TEXT NOT NULL,
                    row_filter_sql TEXT,
                    denied_columns_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_data_sources (
                    source_alias TEXT PRIMARY KEY,
                    dialect TEXT NOT NULL,
                    business_domain TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_tables (
                    table_id TEXT PRIMARY KEY,
                    source_alias TEXT NOT NULL,
                    schema_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    business_domain TEXT NOT NULL,
                    description TEXT,
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sensitivity_level TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_alias) REFERENCES semantic_data_sources(source_alias) ON DELETE CASCADE,
                    UNIQUE (source_alias, schema_name, table_name)
                );

                CREATE TABLE IF NOT EXISTS semantic_columns (
                    column_id TEXT PRIMARY KEY,
                    table_id TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    business_name TEXT,
                    description TEXT,
                    is_sensitive INTEGER NOT NULL,
                    sensitivity_level TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (table_id) REFERENCES semantic_tables(table_id) ON DELETE CASCADE,
                    UNIQUE (table_id, column_name)
                );

                CREATE TABLE IF NOT EXISTS semantic_table_relationships (
                    id TEXT PRIMARY KEY,
                    source_table_id TEXT NOT NULL,
                    target_table_id TEXT NOT NULL,
                    join_type TEXT NOT NULL,
                    join_condition TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_table_id) REFERENCES semantic_tables(table_id) ON DELETE CASCADE,
                    FOREIGN KEY (target_table_id) REFERENCES semantic_tables(table_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_semantic_metrics_domain ON semantic_metrics(business_domain);
                CREATE INDEX IF NOT EXISTS idx_semantic_synonyms_term ON semantic_metric_synonyms(term);
                CREATE INDEX IF NOT EXISTS idx_semantic_defaults_lookup
                    ON semantic_metric_defaults(scope_type, scope_id, business_domain, metric_term);
                CREATE INDEX IF NOT EXISTS idx_semantic_permissions_role ON semantic_role_permissions(role);
                CREATE INDEX IF NOT EXISTS idx_semantic_users_status ON semantic_users(status);
                CREATE INDEX IF NOT EXISTS idx_semantic_access_policy_lookup
                    ON semantic_access_policies(role, business_domain, semantic_id, status);
                CREATE INDEX IF NOT EXISTS idx_semantic_tables_lookup
                    ON semantic_tables(source_alias, schema_name, table_name, status);
                CREATE INDEX IF NOT EXISTS idx_semantic_columns_lookup
                    ON semantic_columns(table_id, column_name, status);
                """
            )
            conn.commit()

    def seed_from_file_if_empty(self) -> None:
        if not self.seed_path.exists():
            return

        seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
        with self._get_conn() as conn:
            metric_count = conn.execute("SELECT COUNT(*) FROM semantic_metrics").fetchone()[0]
            default_count = conn.execute("SELECT COUNT(*) FROM semantic_metric_defaults").fetchone()[0]
            permission_count = conn.execute("SELECT COUNT(*) FROM semantic_role_permissions").fetchone()[0]
            user_count = conn.execute("SELECT COUNT(*) FROM semantic_users").fetchone()[0]
            access_policy_count = conn.execute("SELECT COUNT(*) FROM semantic_access_policies").fetchone()[0]
            catalog_count = conn.execute("SELECT COUNT(*) FROM semantic_tables").fetchone()[0]

        if metric_count == 0:
            for metric in seed.get("metrics", []):
                self.upsert_metric(metric, actor="seed")
        if default_count == 0:
            for default in seed.get("defaults", []):
                self.upsert_metric_default(default, actor="seed")
        if permission_count == 0:
            for permission in seed.get("role_permissions", []):
                self.upsert_role_permission(permission)
        if user_count == 0:
            for user in seed.get("users", []):
                self.upsert_user(user, actor="seed")
        if access_policy_count == 0:
            for policy in seed.get("access_policies", []):
                self.upsert_access_policy(policy, actor="seed")
        if catalog_count == 0:
            self.upsert_catalog(seed.get("catalog", {}), actor="seed")

    def upsert_metric(self, metric: dict[str, Any], actor: str) -> None:
        now = _now()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_metrics WHERE semantic_id = ?",
                (metric["semantic_id"],),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_metrics
                (semantic_id, name, display_name, business_domain, definition_scope,
                 status, current_version, business_owner, technical_owner, risk_level,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(semantic_id) DO UPDATE SET
                    name = excluded.name,
                    display_name = excluded.display_name,
                    business_domain = excluded.business_domain,
                    definition_scope = excluded.definition_scope,
                    status = excluded.status,
                    current_version = excluded.current_version,
                    business_owner = excluded.business_owner,
                    technical_owner = excluded.technical_owner,
                    risk_level = excluded.risk_level,
                    updated_at = excluded.updated_at
                """,
                (
                    metric["semantic_id"],
                    metric["name"],
                    metric.get("display_name", metric["name"]),
                    metric["business_domain"],
                    metric.get("definition_scope", "organization"),
                    metric.get("status", "draft"),
                    metric.get("current_version", "v1"),
                    metric.get("business_owner", ""),
                    metric.get("technical_owner", ""),
                    metric.get("risk_level", "medium"),
                    now,
                    now,
                ),
            )
            for version in metric.get("versions", []):
                self._upsert_metric_version(conn, metric["semantic_id"], version)
            for term in metric.get("synonyms", []):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO semantic_metric_synonyms
                    (id, semantic_id, term, locale, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), metric["semantic_id"], term, _locale_for(term), now),
                )
            self._audit(
                conn,
                actor=actor,
                action="metric.upsert",
                target_type="metric",
                target_id=metric["semantic_id"],
                before=dict(existing) if existing else None,
                after=metric,
            )
            conn.commit()

    def _upsert_metric_version(self, conn: sqlite3.Connection, semantic_id: str, version: dict[str, Any]) -> None:
        version_id = f"{semantic_id}:{version['version']}"
        content_checksum = _checksum(version)
        conn.execute(
            """
            INSERT INTO semantic_metric_versions
            (id, semantic_id, version, definition, default_calendar, default_time_field,
             default_source_alias, default_schema, visibility_roles_json, sql_templates_json,
             created_by, approved_by, published_at, checksum, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(semantic_id, version) DO UPDATE SET
                definition = excluded.definition,
                default_calendar = excluded.default_calendar,
                default_time_field = excluded.default_time_field,
                default_source_alias = excluded.default_source_alias,
                default_schema = excluded.default_schema,
                visibility_roles_json = excluded.visibility_roles_json,
                sql_templates_json = excluded.sql_templates_json,
                created_by = excluded.created_by,
                approved_by = excluded.approved_by,
                published_at = excluded.published_at,
                checksum = excluded.checksum
            """,
            (
                version_id,
                semantic_id,
                version["version"],
                version.get("definition", ""),
                version.get("default_calendar", "company_business_week"),
                version.get("default_time_field", ""),
                version.get("default_source_alias", ""),
                version.get("default_schema", ""),
                _json(version.get("visibility_roles", [])),
                _json(version.get("sql_templates", {})),
                version.get("created_by", "unknown"),
                version.get("approved_by"),
                version.get("published_at"),
                content_checksum,
                _now(),
            ),
        )

    def upsert_metric_default(self, default: dict[str, Any], actor: str) -> None:
        now = _now()
        with self._get_conn() as conn:
            existing = conn.execute(
                """
                SELECT * FROM semantic_metric_defaults
                WHERE scope_type = ? AND scope_id = ? AND business_domain = ? AND metric_term = ?
                """,
                (
                    default["scope_type"],
                    default["scope_id"],
                    default["business_domain"],
                    default["metric_term"],
                ),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_metric_defaults
                (id, scope_type, scope_id, business_domain, metric_term, semantic_id,
                 version, high_risk_allowed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_type, scope_id, business_domain, metric_term) DO UPDATE SET
                    semantic_id = excluded.semantic_id,
                    version = excluded.version,
                    high_risk_allowed = excluded.high_risk_allowed,
                    updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    default["scope_type"],
                    default["scope_id"],
                    default["business_domain"],
                    default["metric_term"],
                    default["semantic_id"],
                    default.get("version", "v1"),
                    1 if default.get("high_risk_allowed", False) else 0,
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                actor=actor,
                action="metric_default.upsert",
                target_type="metric_default",
                target_id=f"{default['scope_type']}:{default['scope_id']}:{default['metric_term']}",
                before=dict(existing) if existing else None,
                after=default,
            )
            conn.commit()

    def upsert_role_permission(self, permission: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO semantic_role_permissions
                (id, role, resource_type, resource_id, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    permission["role"],
                    permission["resource_type"],
                    permission["resource_id"],
                    permission["action"],
                    _now(),
                ),
            )
            conn.commit()

    def upsert_user(self, user: dict[str, Any], actor: str) -> None:
        now = _now()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_users
                (user_id, display_name, team, roles_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    team = excluded.team,
                    roles_json = excluded.roles_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    user["user_id"],
                    user.get("display_name", user["user_id"]),
                    user.get("team", "default"),
                    _json(user.get("roles", [])),
                    user.get("status", "active"),
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                actor=actor,
                action="user.upsert",
                target_type="user",
                target_id=user["user_id"],
                before=dict(existing) if existing else None,
                after=user,
            )
            conn.commit()

    def upsert_access_policy(self, policy: dict[str, Any], actor: str) -> str:
        now = _now()
        policy_id = policy.get("policy_id") or str(uuid.uuid4())
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_access_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_access_policies
                (policy_id, role, business_domain, semantic_id, row_filter_sql,
                 denied_columns_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(policy_id) DO UPDATE SET
                    role = excluded.role,
                    business_domain = excluded.business_domain,
                    semantic_id = excluded.semantic_id,
                    row_filter_sql = excluded.row_filter_sql,
                    denied_columns_json = excluded.denied_columns_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    policy_id,
                    policy["role"],
                    policy["business_domain"],
                    policy.get("semantic_id", "*"),
                    policy.get("row_filter_sql", ""),
                    _json(policy.get("denied_columns", [])),
                    policy.get("status", "active"),
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                actor=actor,
                action="access_policy.upsert",
                target_type="access_policy",
                target_id=policy_id,
                before=dict(existing) if existing else None,
                after=policy,
            )
            conn.commit()
        return policy_id

    def resolve_access_policy(self, roles: list[str], business_domain: str, semantic_id: str) -> dict[str, Any]:
        if not roles:
            return {"row_filters": [], "denied_columns": [], "matched_policies": []}
        with self._get_conn() as conn:
            placeholders = ",".join("?" for _ in roles)
            rows = conn.execute(
                f"""
                SELECT * FROM semantic_access_policies
                WHERE role IN ({placeholders})
                  AND status = 'active'
                  AND (business_domain = ? OR business_domain = '*')
                  AND (semantic_id = ? OR semantic_id = '*')
                ORDER BY semantic_id DESC, policy_id
                """,
                [*roles, business_domain, semantic_id],
            ).fetchall()
        row_filters: list[str] = []
        denied_columns: set[str] = set()
        matched: list[str] = []
        for row in rows:
            matched.append(row["policy_id"])
            row_filter = (row["row_filter_sql"] or "").strip()
            if row_filter:
                row_filters.append(row_filter)
            denied_columns.update(_loads(row["denied_columns_json"], []))
        return {
            "row_filters": row_filters,
            "denied_columns": sorted(denied_columns),
            "matched_policies": matched,
        }

    def upsert_catalog(self, catalog: dict[str, Any], actor: str) -> None:
        for source in catalog.get("data_sources", []):
            self.upsert_data_source(source, actor=actor)
        for table in catalog.get("tables", []):
            columns = table.get("columns", [])
            table_record = dict(table)
            table_record.pop("columns", None)
            self.upsert_table(table_record, actor=actor)
            for column in columns:
                self.upsert_column(table_record["table_id"], column, actor=actor)
        for relationship in catalog.get("relationships", []):
            self.upsert_table_relationship(relationship, actor=actor)

    def upsert_data_source(self, source: dict[str, Any], actor: str) -> str:
        now = _now()
        alias = source["source_alias"]
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_data_sources WHERE source_alias = ?",
                (alias,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_data_sources
                (source_alias, dialect, business_domain, owner, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_alias) DO UPDATE SET
                    dialect = excluded.dialect,
                    business_domain = excluded.business_domain,
                    owner = excluded.owner,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    alias,
                    source.get("dialect", ""),
                    source.get("business_domain", ""),
                    source.get("owner", ""),
                    source.get("status", "active"),
                    now,
                    now,
                ),
            )
            self._audit(conn, actor, "catalog.source.upsert", "data_source", alias, dict(existing) if existing else None, source)
            conn.commit()
        return alias

    def upsert_table(self, table: dict[str, Any], actor: str) -> str:
        now = _now()
        table_id = table.get("table_id") or f"table.{table['source_alias']}.{table['schema_name']}.{table['table_name']}"
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_tables WHERE table_id = ?",
                (table_id,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_tables
                (table_id, source_alias, schema_name, table_name, business_domain,
                 description, owner, status, sensitivity_level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(table_id) DO UPDATE SET
                    source_alias = excluded.source_alias,
                    schema_name = excluded.schema_name,
                    table_name = excluded.table_name,
                    business_domain = excluded.business_domain,
                    description = excluded.description,
                    owner = excluded.owner,
                    status = excluded.status,
                    sensitivity_level = excluded.sensitivity_level,
                    updated_at = excluded.updated_at
                """,
                (
                    table_id,
                    table["source_alias"],
                    table["schema_name"],
                    table["table_name"],
                    table.get("business_domain", ""),
                    table.get("description", ""),
                    table.get("owner", ""),
                    table.get("status", "active"),
                    table.get("sensitivity_level", "internal"),
                    now,
                    now,
                ),
            )
            self._audit(conn, actor, "catalog.table.upsert", "table", table_id, dict(existing) if existing else None, table)
            conn.commit()
        return table_id

    def upsert_column(self, table_id: str, column: dict[str, Any], actor: str) -> str:
        now = _now()
        column_id = column.get("column_id") or f"{table_id}.{column['column_name']}"
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_columns WHERE column_id = ?",
                (column_id,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_columns
                (column_id, table_id, column_name, data_type, business_name, description,
                 is_sensitive, sensitivity_level, tags_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(table_id, column_name) DO UPDATE SET
                    data_type = excluded.data_type,
                    business_name = excluded.business_name,
                    description = excluded.description,
                    is_sensitive = excluded.is_sensitive,
                    sensitivity_level = excluded.sensitivity_level,
                    tags_json = excluded.tags_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    column_id,
                    table_id,
                    column["column_name"],
                    column.get("data_type", ""),
                    column.get("business_name", ""),
                    column.get("description", ""),
                    1 if column.get("is_sensitive", False) else 0,
                    column.get("sensitivity_level", "internal"),
                    _json(column.get("tags", [])),
                    column.get("status", "active"),
                    now,
                    now,
                ),
            )
            self._audit(conn, actor, "catalog.column.upsert", "column", column_id, dict(existing) if existing else None, column)
            conn.commit()
        return column_id

    def upsert_table_relationship(self, relationship: dict[str, Any], actor: str) -> str:
        now = _now()
        relation_id = relationship.get("id") or str(uuid.uuid4())
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM semantic_table_relationships WHERE id = ?",
                (relation_id,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO semantic_table_relationships
                (id, source_table_id, target_table_id, join_type, join_condition, status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_table_id = excluded.source_table_id,
                    target_table_id = excluded.target_table_id,
                    join_type = excluded.join_type,
                    join_condition = excluded.join_condition,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    relation_id,
                    relationship["source_table_id"],
                    relationship["target_table_id"],
                    relationship.get("join_type", "inner"),
                    relationship.get("join_condition", ""),
                    relationship.get("status", "active"),
                    now,
                    now,
                ),
            )
            self._audit(conn, actor, "catalog.relationship.upsert", "relationship", relation_id, dict(existing) if existing else None, relationship)
            conn.commit()
        return relation_id

    def get_catalog_table(self, source_alias: str, schema_name: str, table_name: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM semantic_tables
                WHERE source_alias = ? AND schema_name = ? AND table_name = ? AND status = 'active'
                """,
                (source_alias, schema_name, table_name),
            ).fetchone()
        return dict(row) if row else None

    def list_catalog_columns(self, table_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM semantic_columns WHERE table_id = ? AND status = 'active'",
                (table_id,),
            ).fetchall()
        columns = []
        for row in rows:
            item = dict(row)
            item["is_sensitive"] = bool(item["is_sensitive"])
            item["tags"] = _loads(item.pop("tags_json"), [])
            columns.append(item)
        return columns

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_users WHERE user_id = ? AND status = 'active'",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        user = dict(row)
        user["roles"] = _loads(user.pop("roles_json"), [])
        return user

    def list_metrics(self, domain: str | None = None, include_unpublished: bool = False) -> list[dict[str, Any]]:
        params: list[Any] = []
        filters = []
        if domain:
            filters.append("business_domain = ?")
            params.append(domain)
        if not include_unpublished:
            filters.append("status = 'published'")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM semantic_metrics {where} ORDER BY business_domain, semantic_id",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_synonyms(self) -> list[str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT term FROM semantic_metric_synonyms ORDER BY LENGTH(term) DESC").fetchall()
        return [row["term"] for row in rows]

    def retrieve_metrics(self, terms: list[str], domain: str) -> list[dict[str, Any]]:
        if not terms:
            return []
        placeholders = ",".join("?" for _ in terms)
        params: list[Any] = list(terms)
        domain_filter = ""
        if domain != "general":
            domain_filter = "AND m.business_domain = ?"
            params.append(domain)

        with self._get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT m.*, v.definition, v.default_calendar, v.default_time_field,
                       v.default_source_alias, v.default_schema, v.visibility_roles_json,
                       v.sql_templates_json, v.checksum
                FROM semantic_metrics m
                JOIN semantic_metric_synonyms s ON s.semantic_id = m.semantic_id
                JOIN semantic_metric_versions v
                  ON v.semantic_id = m.semantic_id AND v.version = m.current_version
                WHERE s.term IN ({placeholders})
                  AND m.status IN ('published', 'deprecated')
                  {domain_filter}
                ORDER BY m.status = 'published' DESC, m.semantic_id
                """,
                params,
            ).fetchall()

        return [self._metric_from_row(row) for row in rows]

    def get_metric(self, semantic_id: str, version: str | None = None) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT m.*, v.definition, v.default_calendar, v.default_time_field,
                       v.default_source_alias, v.default_schema, v.visibility_roles_json,
                       v.sql_templates_json, v.checksum
                FROM semantic_metrics m
                JOIN semantic_metric_versions v
                  ON v.semantic_id = m.semantic_id
                 AND v.version = COALESCE(?, m.current_version)
                WHERE m.semantic_id = ?
                """,
                (version, semantic_id),
            ).fetchone()
        return self._metric_from_row(row) if row else None

    def create_metric_draft(self, metric: dict[str, Any], actor: str, actor_roles: list[str]) -> str:
        domain = metric.get("business_domain", "")
        if not self.has_permission(actor_roles, "metric.draft", "domain", domain):
            raise PermissionError("Actor is not allowed to create metric drafts in this domain.")
        draft = dict(metric)
        draft["status"] = "draft"
        draft.setdefault("current_version", "v1")
        for version in draft.get("versions", []):
            version.setdefault("created_by", actor)
            version.setdefault("published_at", None)
            version.setdefault("approved_by", None)
        self.upsert_metric(draft, actor=actor)
        return draft["semantic_id"]

    def update_metric_draft(self, semantic_id: str, patch: dict[str, Any], actor: str, actor_roles: list[str]) -> None:
        current = self.get_metric(semantic_id)
        if not current:
            raise ValueError(f"Metric does not exist: {semantic_id}")
        if current.get("status") != "draft":
            raise ValueError("Only draft metrics can be updated through this operation.")
        domain = current.get("business_domain", "")
        if not self.has_permission(actor_roles, "metric.draft", "domain", domain):
            raise PermissionError("Actor is not allowed to update metric drafts in this domain.")

        with self._get_conn() as conn:
            allowed_fields = {
                "name",
                "display_name",
                "definition_scope",
                "business_owner",
                "technical_owner",
                "risk_level",
            }
            fields = []
            values: list[Any] = []
            for key, value in patch.items():
                if key in allowed_fields:
                    fields.append(f"{key} = ?")
                    values.append(value)
            if fields:
                fields.append("updated_at = ?")
                values.append(_now())
                values.append(semantic_id)
                conn.execute(
                    f"UPDATE semantic_metrics SET {', '.join(fields)} WHERE semantic_id = ?",
                    values,
                )
            self._audit(
                conn,
                actor=actor,
                action="metric_draft.update",
                target_type="metric",
                target_id=semantic_id,
                before=current,
                after=patch,
            )
            conn.commit()

    def select_default_metric(
        self,
        metric_candidates: list[dict[str, Any]],
        metric_term: str,
        domain: str,
        scope_type: str = "domain",
        scope_id: str | None = None,
        high_risk: bool = False,
    ) -> dict[str, Any] | None:
        candidate_ids = {metric.get("semantic_id") for metric in metric_candidates}
        if not candidate_ids:
            return None
        scope_id = scope_id or domain
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM semantic_metric_defaults
                WHERE scope_type = ? AND scope_id = ? AND business_domain = ? AND metric_term = ?
                """,
                (scope_type, scope_id, domain, metric_term),
            ).fetchone()
        if not row or row["semantic_id"] not in candidate_ids:
            return None
        if high_risk and not bool(row["high_risk_allowed"]):
            return None
        return self.get_metric(row["semantic_id"], row["version"])

    def has_permission(self, roles: list[str], action: str, resource_type: str, resource_id: str) -> bool:
        if not roles:
            return False
        with self._get_conn() as conn:
            for role in roles:
                row = conn.execute(
                    """
                    SELECT 1 FROM semantic_role_permissions
                    WHERE role = ?
                      AND (action = ? OR action = '*')
                      AND (resource_type = ? OR resource_type = '*')
                      AND (resource_id = ? OR resource_id = '*')
                    LIMIT 1
                    """,
                    (role, action, resource_type, resource_id),
                ).fetchone()
                if row:
                    return True
        return False

    def create_workflow(
        self,
        target_type: str,
        target_id: str,
        action: str,
        requester: str,
        approvers: list[str],
    ) -> str:
        workflow_id = str(uuid.uuid4())
        now = _now()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO semantic_workflows
                (id, target_type, target_id, action, status, requester, approvers_json,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (workflow_id, target_type, target_id, action, "pending", requester, _json(approvers), now, now),
            )
            self._audit(
                conn,
                actor=requester,
                action=f"workflow.{action}.create",
                target_type=target_type,
                target_id=target_id,
                before=None,
                after={"workflow_id": workflow_id, "approvers": approvers},
            )
            conn.commit()
        return workflow_id

    def request_metric_publish(
        self,
        semantic_id: str,
        requester: str,
        requester_roles: list[str],
        approvers: list[str],
    ) -> str:
        metric = self.get_metric(semantic_id)
        if not metric:
            raise ValueError(f"Metric does not exist: {semantic_id}")
        domain = metric.get("business_domain", "")
        if not self.has_permission(requester_roles, "metric.request_publish", "domain", domain):
            raise PermissionError("Requester is not allowed to request metric publication.")
        return self.create_workflow(
            target_type="metric",
            target_id=semantic_id,
            action="publish",
            requester=requester,
            approvers=approvers,
        )

    def deprecate_metric(self, semantic_id: str, actor: str, actor_roles: list[str]) -> None:
        metric = self.get_metric(semantic_id)
        if not metric:
            raise ValueError(f"Metric does not exist: {semantic_id}")
        if not self.has_permission(actor_roles, "metric.approve_business", "domain", metric.get("business_domain", "")):
            raise PermissionError("Actor is not allowed to deprecate metrics in this domain.")
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE semantic_metrics SET status = 'deprecated', updated_at = ? WHERE semantic_id = ?",
                (_now(), semantic_id),
            )
            self._audit(
                conn,
                actor=actor,
                action="metric.deprecate",
                target_type="metric",
                target_id=semantic_id,
                before=metric,
                after={"status": "deprecated"},
            )
            conn.commit()

    def list_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM semantic_audit_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        logs = []
        for row in rows:
            item = dict(row)
            item["before"] = _loads(item.pop("before_json"), None)
            item["after"] = _loads(item.pop("after_json"), None)
            logs.append(item)
        return logs

    def approve_workflow(
        self,
        workflow_id: str,
        actor: str,
        actor_roles: list[str],
        approval_kind: str,
    ) -> None:
        if approval_kind not in {"business", "technical"}:
            raise ValueError("approval_kind must be business or technical")

        with self._get_conn() as conn:
            workflow = conn.execute(
                "SELECT * FROM semantic_workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if not workflow:
                raise ValueError(f"Workflow does not exist: {workflow_id}")
            metric = self.get_metric(workflow["target_id"])
            if not metric:
                raise ValueError(f"Workflow target metric does not exist: {workflow['target_id']}")

            action = "metric.approve_business" if approval_kind == "business" else "metric.approve_technical"
            if not self.has_permission(actor_roles, action, "domain", metric.get("business_domain", "")):
                raise PermissionError(f"Actor is not allowed to perform {approval_kind} approval.")

            existing_approvers = _loads(workflow["approvers_json"], [])
            approval_record = {"actor": actor, "kind": approval_kind, "approved_at": _now()}
            approvers = existing_approvers + [approval_record]
            approved_kinds = {item.get("kind") for item in approvers if isinstance(item, dict)}
            status = "approved" if {"business", "technical"}.issubset(approved_kinds) else "pending"
            conn.execute(
                """
                UPDATE semantic_workflows
                SET status = ?, approvers_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, _json(approvers), _now(), workflow_id),
            )
            self._audit(
                conn,
                actor=actor,
                action=f"workflow.{approval_kind}.approve",
                target_type=workflow["target_type"],
                target_id=workflow["target_id"],
                before=dict(workflow),
                after={"workflow_id": workflow_id, "status": status, "approvers": approvers},
            )
            conn.commit()

    def _metric_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        metric = dict(row)
        metric["version"] = metric.pop("current_version")
        metric["visibility_roles"] = _loads(metric.pop("visibility_roles_json"), [])
        metric["sql_templates"] = _loads(metric.pop("sql_templates_json"), {})
        metric["definition_version_checksum"] = metric.pop("checksum")
        return metric

    def _audit(
        self,
        conn: sqlite3.Connection,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        before: dict | None,
        after: dict | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO semantic_audit_logs
            (id, actor, action, target_type, target_id, before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                actor,
                action,
                target_type,
                target_id,
                _json(before) if before is not None else None,
                _json(after) if after is not None else None,
                _now(),
            ),
        )


def _locale_for(term: str) -> str:
    return "zh-CN" if any(ord(char) > 127 for char in term) else "en-US"
