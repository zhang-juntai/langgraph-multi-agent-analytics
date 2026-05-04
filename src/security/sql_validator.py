"""Production governed SQL validation using sqlglot AST."""

from __future__ import annotations

import re
from typing import Any

from configs.settings import settings
from src.persistence.semantic_store import SemanticStore

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|merge|grant|revoke|call|execute)\b",
    re.IGNORECASE,
)

SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "sys",
    "mysql",
    "performance_schema",
    "sqlite_master",
}

SAFE_AGGREGATES = {"sum", "avg", "min", "max", "count"}

CHECK_MESSAGES = {
    "sql_present": "No SQL was generated for validation.",
    "read_query_prefix": "Only read queries starting with SELECT or WITH are allowed before AST validation.",
    "single_statement": "Multiple SQL statements are not allowed.",
    "no_forbidden_keywords": "The SQL contains write, DDL, or administrative keywords.",
    "sqlglot_ast_parse": "The SQL cannot be parsed by the production SQL parser.",
    "ast_select_only": "Only SELECT statements are allowed.",
    "no_select_star": "SELECT * is not allowed because required columns must be explicit.",
    "tables_detected": "The SQL must reference at least one governed Catalog table.",
    "no_system_tables": "System tables and metadata schemas are not queryable by the agent.",
    "no_cte_in_production": "CTE queries are disabled in the current production validator policy.",
    "no_subquery_in_production": "Subqueries are disabled in the current production validator policy.",
    "allowed_functions_only": "The SQL uses functions outside the approved aggregate allowlist.",
    "no_unapproved_detail_query": "Detail-level row queries are disabled unless explicitly allowed by policy.",
    "catalog_tables_exist": "One or more referenced tables are not registered in Catalog.",
    "catalog_columns_exist": "One or more referenced columns are not registered in Catalog.",
    "denied_columns_not_used": "The SQL references columns denied by the user's access policy.",
    "sensitive_columns_not_used": "The SQL references sensitive columns that are blocked for agent queries.",
    "row_filters_applied": "Required row-level access filters are missing from the SQL.",
}


def validate_governed_sql(
    sql: str,
    dialect: str,
    source_alias: str,
    metric: dict[str, Any],
    access_policy: dict[str, Any],
    store: SemanticStore | None = None,
) -> dict[str, Any]:
    """Validate final executable SQL before Execution Engine can run it."""

    store = store or SemanticStore()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    sql_clean = (sql or "").strip().rstrip(";")
    parsed: dict[str, Any] = {
        "tables": [],
        "columns": [],
        "has_select_star": False,
        "has_cte": False,
        "has_join": False,
        "has_subquery": False,
        "has_aggregate": False,
        "is_detail_query": False,
        "functions": [],
    }

    _check(checks, bool(sql_clean), "sql_present", errors)
    _check(checks, _has_read_query_prefix(sql_clean), "read_query_prefix", errors)
    _check(checks, ";" not in sql_clean, "single_statement", errors)
    _check(checks, FORBIDDEN_SQL.search(sql_clean) is None, "no_forbidden_keywords", errors)

    if not errors:
        try:
            parsed = _parse_with_sqlglot(sql_clean, dialect)
            _check(checks, True, "sqlglot_ast_parse", errors)
        except Exception as exc:
            _check(checks, False, "sqlglot_ast_parse", errors, {"error": str(exc)})

    if not errors:
        _check(checks, parsed["statement_type"] == "select", "ast_select_only", errors)
        _check(checks, not parsed["has_select_star"], "no_select_star", errors)
        _check(checks, bool(parsed["tables"]), "tables_detected", errors)
        _check(checks, not parsed["system_tables"], "no_system_tables", errors, {"system_tables": parsed["system_tables"]})
        _check(checks, not parsed["has_cte"], "no_cte_in_production", errors)
        _check(checks, not parsed["has_subquery"], "no_subquery_in_production", errors)
        _check(checks, _functions_allowed(parsed["functions"]), "allowed_functions_only", errors, {"functions": parsed["functions"]})
        _check(
            checks,
            not parsed["is_detail_query"] or settings.SQL_VALIDATOR_ALLOW_DETAIL_QUERY,
            "no_unapproved_detail_query",
            errors,
            {"is_detail_query": parsed["is_detail_query"]},
        )

        catalog_tables = []
        catalog_columns_by_table: dict[str, dict[str, dict[str, Any]]] = {}
        table_errors = []
        for table_ref in parsed["tables"]:
            table = store.get_catalog_table(
                source_alias,
                table_ref.get("schema_name") or metric.get("default_schema", ""),
                table_ref["table_name"],
            )
            if not table:
                table_errors.append(table_ref)
                continue
            catalog_tables.append(table)
            table_columns = store.list_catalog_columns(table["table_id"])
            catalog_columns_by_table[table["table_id"]] = {col["column_name"].lower(): col for col in table_columns}
        _check(checks, not table_errors, "catalog_tables_exist", errors, {"missing_tables": table_errors})

        if catalog_tables:
            known_columns = _merged_columns(catalog_columns_by_table)
            missing_columns = sorted(col for col in parsed["columns"] if col.lower() not in known_columns)
            _check(checks, not missing_columns, "catalog_columns_exist", errors, {"missing_columns": missing_columns})

            denied = {col.lower() for col in access_policy.get("denied_columns", [])}
            referenced_denied = sorted(col for col in parsed["columns"] if col.lower() in denied)
            _check(checks, not referenced_denied, "denied_columns_not_used", errors, {"denied_columns": referenced_denied})

            sensitive_columns = {
                name for name, column in known_columns.items()
                if column.get("is_sensitive")
            }
            referenced_sensitive = sorted(col for col in parsed["columns"] if col.lower() in sensitive_columns)
            _check(
                checks,
                not referenced_sensitive,
                "sensitive_columns_not_used",
                errors,
                {"sensitive_columns": referenced_sensitive},
            )

    row_filters = [item for item in access_policy.get("row_filters", []) if str(item).strip()]
    missing_filters = _missing_row_filters(sql_clean, row_filters, dialect)
    _check(checks, not missing_filters, "row_filters_applied", errors, {"missing_filters": missing_filters})

    passed = not errors
    failure_reasons = _failure_reasons(checks)
    return {
        "validation_type": "governed_sql_guard",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "checks": checks,
        "error_message": "; ".join(errors),
        "failure_reasons": failure_reasons,
        "failure_summary": _failure_summary(failure_reasons),
        "tables": [
            f"{source_alias}.{item.get('schema_name')}.{item.get('table_name')}"
            for item in parsed["tables"]
        ],
        "columns": parsed["columns"],
        "functions": parsed["functions"],
        "has_cte": parsed["has_cte"],
        "has_join": parsed["has_join"],
        "has_subquery": parsed["has_subquery"],
        "has_aggregate": parsed["has_aggregate"],
        "is_detail_query": parsed["is_detail_query"],
        "row_filters_required": row_filters,
        "row_filters_applied": not missing_filters,
        "catalog_version": "semantic_catalog_sqlite_p1.6",
        "validator_mode": settings.SQL_VALIDATOR_MODE,
        "parser": "sqlglot",
    }


def _parse_with_sqlglot(sql: str, dialect: str) -> dict[str, Any]:
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError as exc:
        if settings.SQL_VALIDATOR_MODE == "development" and settings.SQL_VALIDATOR_ALLOW_DEV_FALLBACK:
            raise RuntimeError("sqlglot is required even in development for P1.6 validation.") from exc
        raise RuntimeError("sqlglot is required for production SQL validation.") from exc

    expressions = sqlglot.parse(sql, read=_sqlglot_dialect(dialect))
    if len(expressions) != 1:
        raise ValueError("SQL must parse into exactly one statement.")
    root = expressions[0]
    statement_type = "select" if isinstance(root, exp.Select) else root.__class__.__name__.lower()

    tables = []
    system_tables = []
    for table in root.find_all(exp.Table):
        schema = table.db or ""
        name = table.name
        ref = {"schema_name": schema, "table_name": name}
        tables.append(ref)
        if schema.lower() in SYSTEM_SCHEMAS or name.lower() in SYSTEM_SCHEMAS:
            system_tables.append(ref)

    columns = []
    for column in root.find_all(exp.Column):
        name = column.name
        if name and name not in columns:
            columns.append(name)

    functions = []
    aggregate_count = 0
    for func in root.find_all(exp.Func):
        if isinstance(func, (exp.And, exp.Or, exp.Not, exp.In, exp.Between, exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE)):
            continue
        name = (func.sql_name() or func.key or "").lower()
        if name and name not in functions:
            functions.append(name)
        if name in SAFE_AGGREGATES:
            aggregate_count += 1

    has_star = any(isinstance(node, exp.Star) for node in root.walk())
    has_cte = any(isinstance(node, exp.CTE) for node in root.walk())
    has_join = any(isinstance(node, exp.Join) for node in root.walk())
    has_subquery = any(isinstance(node, exp.Subquery) for node in root.walk())
    select_expr_count = len(root.expressions) if isinstance(root, exp.Select) else 0
    is_detail_query = bool(columns) and aggregate_count == 0 and not has_star and select_expr_count > 0

    return {
        "statement_type": statement_type,
        "tables": _dedupe_table_refs(tables),
        "columns": columns,
        "has_select_star": has_star,
        "has_cte": has_cte,
        "has_join": has_join,
        "has_subquery": has_subquery,
        "has_aggregate": aggregate_count > 0,
        "is_detail_query": is_detail_query,
        "functions": functions,
        "system_tables": system_tables,
    }


def _missing_row_filters(sql: str, row_filters: list[str], dialect: str) -> list[str]:
    if not row_filters:
        return []
    normalized_sql = _normalize_ast_sql(sql, dialect)
    missing = []
    for row_filter in row_filters:
        normalized_filter = _normalize_ast_sql(f"SELECT 1 WHERE {row_filter}", dialect)
        filter_predicate = normalized_filter.split(" WHERE ", 1)[-1]
        if filter_predicate not in normalized_sql:
            missing.append(row_filter)
    return missing


def _normalize_ast_sql(sql: str, dialect: str) -> str:
    import sqlglot

    parsed = sqlglot.parse_one(sql, read=_sqlglot_dialect(dialect))
    return re.sub(r"\s+", " ", parsed.sql(dialect=_sqlglot_dialect(dialect)).strip().upper())


def _has_read_query_prefix(sql: str) -> bool:
    lowered = sql.lstrip().lower()
    return lowered.startswith("select") or lowered.startswith("with")


def _functions_allowed(functions: list[str]) -> bool:
    return all(func in SAFE_AGGREGATES for func in functions)


def _sqlglot_dialect(dialect: str) -> str:
    if dialect == "postgres":
        return "postgres"
    if dialect == "mysql":
        return "mysql"
    if dialect == "sqlite":
        return "sqlite"
    return dialect or "sqlite"


def _dedupe_table_refs(tables: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for item in tables:
        key = (item.get("schema_name", ""), item.get("table_name", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _merged_columns(catalog_columns_by_table: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    merged = {}
    for columns in catalog_columns_by_table.values():
        merged.update(columns)
    return merged


def _check(
    checks: list[dict[str, Any]],
    passed: bool,
    name: str,
    errors: list[str],
    details: dict[str, Any] | None = None,
) -> None:
    check = {"name": name, "passed": passed}
    if details:
        check["details"] = details
    checks.append(check)
    if not passed:
        errors.append(name)


def _failure_reasons(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons = []
    for check in checks:
        if check.get("passed"):
            continue
        code = str(check.get("name", "unknown_check"))
        reasons.append(
            {
                "code": code,
                "severity": _severity(code),
                "message": CHECK_MESSAGES.get(code, f"SQL validation check failed: {code}."),
                "details": check.get("details", {}),
            }
        )
    return reasons


def _failure_summary(reasons: list[dict[str, Any]]) -> str:
    if not reasons:
        return ""
    return "SQL rejected: " + "; ".join(reason["message"] for reason in reasons)


def _severity(code: str) -> str:
    if code in {
        "no_forbidden_keywords",
        "no_system_tables",
        "denied_columns_not_used",
        "sensitive_columns_not_used",
        "row_filters_applied",
    }:
        return "high"
    if code in {
        "catalog_tables_exist",
        "catalog_columns_exist",
        "no_unapproved_detail_query",
        "no_cte_in_production",
        "no_subquery_in_production",
    }:
        return "medium"
    return "low"
