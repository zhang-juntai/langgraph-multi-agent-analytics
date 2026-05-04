"""Specialized semantic agents for the enterprise data workflow."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.graph.state import AnalysisState
from src.semantic.registry import (
    SEMANTIC_VERSION,
    has_semantic_permission,
    infer_business_domain,
    infer_metric_terms,
    is_high_risk,
    render_metric_scope,
    resolve_access_policy,
    resolve_time_range,
    retrieve_metrics,
)
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

INTENT_PARSE_PROMPT = """You are the Query Parser for an enterprise Data Agent.

Return only valid JSON. Convert vague business language into candidate business
concepts; do not invent data results, table names, or field names.

Rules:
- If the user asks colloquially, infer likely business concepts.
- Ask clarification only for business meaning, not database details.
- If a request could map to multiple governed metrics, keep the broad business
  term so the Disambiguation Engine can ask the user.
- Do not output SQL.

JSON shape:
{
  "task_type": "chat|metric_analysis|data_analysis",
  "business_domain": "sales|finance|marketing|general",
  "candidate_metric_terms": [],
  "raw_dimensions": [],
  "raw_filters": [],
  "raw_time": "",
  "comparison": "",
  "output_purpose": "answer|report|chart|diagnosis",
  "requires_data": true,
  "high_risk": false,
  "clarification_questions": [],
  "confidence": 0.0
}
"""


def intent_parser_node(state: AnalysisState) -> dict[str, Any]:
    text = _last_user_text(state)
    parsed = _parse_intent_with_llm(text)
    fallback = _fallback_parse_intent(text)

    metric_terms = _merge_terms(
        parsed.get("candidate_metric_terms", []),
        parsed.get("raw_metrics", []),
        infer_metric_terms(text),
        fallback.get("raw_metrics", []),
    )
    requires_data = bool(parsed.get("requires_data", fallback["requires_data"]))
    if metric_terms:
        requires_data = True
    domain = parsed.get("business_domain") or fallback["business_domain"]
    task_type = parsed.get("task_type") or ("metric_analysis" if metric_terms else fallback["task_type"])
    if requires_data and metric_terms:
        task_type = "metric_analysis"
    elif requires_data and task_type == "chat":
        task_type = "data_analysis"

    intent = {
        "task_type": task_type,
        "business_domain": domain,
        "raw_metrics": metric_terms,
        "raw_dimensions": parsed.get("raw_dimensions", []),
        "raw_filters": parsed.get("raw_filters", []),
        "raw_time": parsed.get("raw_time") or fallback["raw_time"],
        "comparison": parsed.get("comparison", ""),
        "output_purpose": parsed.get("output_purpose", "answer"),
        "requires_data": requires_data,
        "high_risk": bool(parsed.get("high_risk", is_high_risk(text))),
        "clarification_questions": parsed.get("clarification_questions", []),
        "confidence": parsed.get("confidence", fallback.get("confidence", 0.5)),
    }
    return {
        "query_intent": intent,
        "task_type": task_type,
        "supervisor_decision": "intent_parsed",
        "messages": [AIMessage(content=f"Parsed query intent: {task_type}.")],
    }


def context_resolver_node(state: AnalysisState) -> dict[str, Any]:
    intent = state.get("query_intent", {})
    context = {
        "user_id": state.get("user_id", "anonymous"),
        "team": state.get("team", "default"),
        "business_domain": intent.get("business_domain", "general"),
        "roles": state.get("roles", []),
        "preferences": state.get("preferences", {}),
        "report_context": state.get("report_context", {}),
    }
    return {
        "context_profile": context,
        "supervisor_decision": "context_resolved",
        "messages": [AIMessage(content="Resolved user and domain context.")],
    }


def semantic_retriever_node(state: AnalysisState) -> dict[str, Any]:
    intent = state.get("query_intent", {})
    context = state.get("context_profile", {})
    domain = context.get("business_domain") or intent.get("business_domain", "general")
    metric_terms = intent.get("raw_metrics", [])
    metrics = retrieve_metrics(metric_terms, domain)
    time_range = resolve_time_range(_last_user_text(state))
    candidates = {
        "metrics": metrics,
        "dimensions": [],
        "time_ranges": [time_range],
        "verified_queries": [],
    }
    return {
        "semantic_candidates": candidates,
        "supervisor_decision": "semantic_candidates_retrieved",
        "messages": [AIMessage(content=f"Retrieved {len(metrics)} candidate metric definition(s).")],
    }


def disambiguation_engine_node(state: AnalysisState) -> dict[str, Any]:
    intent = state.get("query_intent", {})
    candidates = state.get("semantic_candidates", {})
    context = state.get("context_profile", {})
    metrics = candidates.get("metrics", [])
    time_ranges = candidates.get("time_ranges", [])
    if intent.get("task_type") == "chat":
        return {
            "disambiguation": {"action": "auto_select", "reason": "chat request"},
            "supervisor_decision": "disambiguation_skipped",
        }

    if intent.get("clarification_questions"):
        return {
            "disambiguation": {
                "action": "clarify",
                "questions": intent.get("clarification_questions", []),
                "reason": "Intent parser requested business clarification.",
            },
            "clarification_required": True,
            "clarification_questions": intent.get("clarification_questions", []),
            "supervisor_decision": "business_clarification_required",
        }

    if not metrics:
        return {
            "disambiguation": {
                "action": "blocked",
                "reason": "No published metric definition matched the business request.",
                "questions": [],
            },
            "supervisor_decision": "semantic_gap_blocked",
            "error": "No governed semantic metric matched the request. A business owner and data steward must publish the metric first.",
        }

    if len(metrics) == 1:
        return _selected_result(metrics[0], time_ranges, "single published metric matched")

    question = "The request can match multiple governed metric definitions. Which business meaning should I use: " + "; ".join(
        render_metric_scope(metric) for metric in metrics
    )
    return {
        "disambiguation": {
            "action": "clarify",
            "questions": [question],
            "reason": "Multiple metric definitions matched. Default metrics are not executed silently.",
        },
        "clarification_required": True,
        "clarification_questions": [question],
        "supervisor_decision": "business_clarification_required",
    }


def logical_plan_builder_node(state: AnalysisState) -> dict[str, Any]:
    disambiguation = state.get("disambiguation", {})
    metric = disambiguation.get("selected_metric", {})
    time_range = disambiguation.get("selected_time_range", {})
    intent = state.get("query_intent", {})
    plan = {
        "plan_type": intent.get("task_type", "metric_analysis"),
        "metric": metric,
        "dimensions": [],
        "filters": [],
        "time_range": time_range,
        "output_purpose": intent.get("output_purpose", "answer"),
        "semantic_version": SEMANTIC_VERSION,
        "steps": [
            {"agent": "query_generator", "goal": "Generate SQL from governed semantic objects."},
            {"agent": "execution_engine", "goal": "Execute read-only query and materialize result evidence."},
            {"agent": "report_writer", "goal": "Explain result with metric scope and evidence."},
        ],
    }
    return {
        "logical_plan": plan,
        "supervisor_decision": "logical_plan_built",
        "messages": [AIMessage(content="Built logical plan from governed semantic objects.")],
    }


def policy_checker_node(state: AnalysisState) -> dict[str, Any]:
    context = state.get("context_profile", {})
    plan = state.get("logical_plan", {})
    metric = plan.get("metric", {})
    roles = set(context.get("roles", []))
    allowed_roles = set(metric.get("visibility_roles", []))
    domain = metric.get("business_domain", "")
    semantic_id = metric.get("semantic_id", "")
    checks = []

    metric_published = metric.get("status") == "published"
    checks.append({"name": "metric_published", "passed": metric_published})

    role_allowed = (
        not allowed_roles
        or bool(roles & allowed_roles)
        or has_semantic_permission(list(roles), "metric.view", "domain", domain)
        or has_semantic_permission(list(roles), "metric.view", "metric", semantic_id)
    )
    checks.append({"name": "metric_visibility", "passed": role_allowed})

    access_policy = resolve_access_policy(list(roles), domain, semantic_id)
    access_policy_ok = bool(access_policy.get("matched_policies")) or "admin" in roles
    checks.append({
        "name": "access_policy_resolved",
        "passed": access_policy_ok,
        "details": access_policy,
    })

    owner_model_present = bool(metric.get("business_owner") and metric.get("technical_owner"))
    checks.append({"name": "owner_model_present", "passed": owner_model_present})

    source_alias = metric.get("default_source_alias", "")
    sources = state.get("database_sources", [])
    source_configured = any(source.get("alias") == source_alias for source in sources)
    checks.append({"name": "database_source_registered", "passed": source_configured})

    allowed = all(check["passed"] for check in checks)
    reason = "" if allowed else "; ".join(check["name"] for check in checks if not check["passed"])
    return {
        "policy_decision": {
            "allowed": allowed,
            "checks": checks,
            "reason": reason,
            "access_policy": access_policy,
        },
        "supervisor_decision": "policy_allowed" if allowed else "policy_denied",
        "error": "" if allowed else f"Policy check denied execution: {reason}",
    }


def query_generator_node(state: AnalysisState) -> dict[str, Any]:
    plan = state.get("logical_plan", {})
    metric = plan.get("metric", {})
    time_range = plan.get("time_range", {})
    sources = state.get("database_sources", [])
    source_alias = metric.get("default_source_alias", "")
    source = next((item for item in sources if item.get("alias") == source_alias), sources[0] if sources else {})
    dialect = source.get("dialect", "generic")
    templates = metric.get("sql_templates", {}) or {}
    template = templates.get(dialect) or templates.get("generic", "")
    access_policy = state.get("policy_decision", {}).get("access_policy", {})
    sql = template.format(
        start_date=time_range.get("start_date", ""),
        end_date=time_range.get("end_date", ""),
    )
    sql = _apply_row_filters(sql, access_policy.get("row_filters", []))
    generated = {
        "language": "sql",
        "dialect": dialect,
        "source_alias": source.get("alias", source_alias),
        "sql": sql,
        "metric_semantic_id": metric.get("semantic_id", ""),
        "metric_version": metric.get("version", ""),
        "time_range": time_range,
        "access_policy": access_policy,
    }
    return {
        "generated_query": generated,
        "current_code": sql,
        "code_result": {
            "success": bool(sql),
            "code": sql,
            "stdout": f"Generated governed SQL for {metric.get('semantic_id', '')}.",
            "stderr": "" if sql else "No SQL template is configured for the selected metric.",
            "figures": [],
        },
        "supervisor_decision": "query_generated",
    }


def execution_engine_node(state: AnalysisState) -> dict[str, Any]:
    generated = state.get("generated_query", {})
    sql = generated.get("sql", "")
    sql_validation = state.get("sql_validation", {})
    if sql_validation.get("status") != "passed":
        return _execution_failed(sql, "SQL validation has not passed. Execution is blocked.")

    source_alias = generated.get("source_alias", "")
    source = next((item for item in state.get("database_sources", []) if item.get("alias") == source_alias), {})
    if not source:
        return _execution_failed(sql, f"Database source `{source_alias}` is not registered.")

    try:
        from src.storage.database_connector import materialize_query_to_local_dataset

        dataset = materialize_query_to_local_dataset(source, sql, state.get("session_id", ""), sql_validation)
        try:
            from src.persistence.session_store import SessionStore

            SessionStore().save_dataset(state.get("session_id", ""), dataset)
        except Exception:
            pass
        stdout = _preview_to_metric_stdout(dataset.get("preview", ""))
        return {
            "datasets": [dataset],
            "code_result": {
                "success": True,
                "code": sql,
                "stdout": stdout or f"Rows materialized: {dataset.get('num_rows', 0)}",
                "stderr": "",
                "figures": [],
            },
            "supervisor_decision": "query_executed",
        }
    except Exception as exc:
        return _execution_failed(sql, str(exc))


def sql_validator_node(state: AnalysisState) -> dict[str, Any]:
    generated = state.get("generated_query", {})
    plan = state.get("logical_plan", {})
    metric = plan.get("metric", {})
    policy = state.get("policy_decision", {})
    try:
        from src.security.sql_validator import validate_governed_sql

        validation = validate_governed_sql(
            sql=generated.get("sql", ""),
            dialect=generated.get("dialect", ""),
            source_alias=generated.get("source_alias", metric.get("default_source_alias", "")),
            metric=metric,
            access_policy=policy.get("access_policy", {}),
        )
    except Exception as exc:
        message = str(exc)
        validation = {
            "validation_type": "governed_sql_guard",
            "status": "failed",
            "passed": False,
            "checks": [{"name": "validator_runtime", "passed": False}],
            "error_message": message,
            "failure_reasons": [
                {
                    "code": "validator_runtime",
                    "severity": "high",
                    "message": "The SQL Validator failed before it could complete validation.",
                    "details": {"error": message},
                }
            ],
            "failure_summary": f"SQL rejected: validator runtime failure: {message}",
        }

    result = {
        "sql_validation": validation,
        "validation_results": list(state.get("validation_results", [])) + [validation],
        "supervisor_decision": "sql_validated" if validation.get("passed") else "sql_validation_failed",
        "error": "" if validation.get("passed") else validation.get("error_message", "SQL validation failed."),
    }
    if not validation.get("passed"):
        result["validation_failure"] = _validation_failure_payload(validation, generated)
    return result


def _validation_failure_payload(validation: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    return {
        "validation_type": validation.get("validation_type", "governed_sql_guard"),
        "status": validation.get("status", "failed"),
        "summary": validation.get("failure_summary") or validation.get("error_message", "SQL validation failed."),
        "reasons": validation.get("failure_reasons", []),
        "failed_checks": [check for check in validation.get("checks", []) if not check.get("passed")],
        "source_alias": generated.get("source_alias", ""),
        "dialect": generated.get("dialect", ""),
        "sql": generated.get("sql", ""),
    }


def _selected_result(metric: dict[str, Any], time_ranges: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    time_range = time_ranges[0] if time_ranges else resolve_time_range("")
    return {
        "disambiguation": {
            "action": "auto_select",
            "selected_metric": metric,
            "selected_time_range": time_range,
            "questions": [],
            "reason": reason,
        },
        "supervisor_decision": "semantic_disambiguated",
        "messages": [AIMessage(content=f"Selected metric scope: {render_metric_scope(metric)}.")],
    }


def _parse_intent_with_llm(text: str) -> dict[str, Any]:
    try:
        response = get_llm().invoke(
            [
                SystemMessage(content=INTENT_PARSE_PROMPT),
                HumanMessage(content=text),
            ]
        )
        return _extract_json(response.content)
    except Exception as exc:
        logger.info("Intent parser LLM fallback activated: %s", exc)
        return {}


def _fallback_parse_intent(text: str) -> dict[str, Any]:
    lower = text.lower()
    vague_sales_tokens = [
        "\u5356\u5f97\u600e\u4e48\u6837",
        "\u5356\u5f97\u548b\u6837",
        "\u5356\u7684\u600e\u6837",
        "\u751f\u610f\u600e\u4e48\u6837",
        "\u4e1a\u7ee9",
        "\u9500\u552e\u8868\u73b0",
        "sales performance",
        "how did sales do",
    ]
    metric_terms = infer_metric_terms(text)
    if any(token in lower for token in vague_sales_tokens):
        metric_terms = _merge_terms(metric_terms, ["\u9500\u552e\u603b\u989d"])

    requires_data = bool(metric_terms) or any(
        token in lower
        for token in [
            "\u5206\u6790",
            "\u6307\u6807",
            "\u8d8b\u52bf",
            "\u9500\u552e",
            "\u4e1a\u7ee9",
            "report",
            "analysis",
            "metric",
            "sales",
        ]
    )
    raw_time = "last_week" if ("\u4e0a\u5468" in text or "last week" in lower) else ""
    task_type = "metric_analysis" if metric_terms else ("data_analysis" if requires_data else "chat")
    return {
        "task_type": task_type,
        "business_domain": infer_business_domain(text),
        "raw_metrics": metric_terms,
        "raw_time": raw_time,
        "requires_data": requires_data,
        "confidence": 0.45,
    }


def _merge_terms(*term_lists: Any) -> list[str]:
    merged: list[str] = []
    for term_list in term_lists:
        if not term_list:
            continue
        if isinstance(term_list, str):
            term_list = [term_list]
        for term in term_list:
            if term and term not in merged:
                merged.append(str(term))
    return merged


def _extract_json(content: str) -> dict[str, Any]:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1)
    return json.loads(content)


def _last_user_text(state: AnalysisState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    for message in reversed(messages):
        if getattr(message, "type", "") == "human" or message.__class__.__name__.lower().startswith("human"):
            return getattr(message, "content", str(message))
    return getattr(messages[-1], "content", str(messages[-1]))


def _execution_failed(sql: str, message: str) -> dict[str, Any]:
    return {
        "code_result": {
            "success": False,
            "code": sql,
            "stdout": "",
            "stderr": message,
            "figures": [],
        },
        "error": message,
        "supervisor_decision": "query_execution_failed",
    }


def _apply_row_filters(sql: str, row_filters: list[str]) -> str:
    filters = [f"({item.strip()})" for item in row_filters if str(item).strip()]
    if not filters:
        return sql
    sql_clean = sql.strip().rstrip(";")
    policy_clause = " AND ".join(filters)
    if re.search(r"\bwhere\b", sql_clean, flags=re.IGNORECASE):
        return f"{sql_clean} AND {policy_clause}"
    return f"{sql_clean} WHERE {policy_clause}"


def _preview_to_metric_stdout(preview: str) -> str:
    lines = [line.strip() for line in str(preview).splitlines() if line.strip()]
    if len(lines) < 2:
        return ""
    headers = lines[0].split(",")
    values = lines[1].split(",")
    return "\n".join(f"{header}: {value}" for header, value in zip(headers, values))
