"""Database-backed semantic registry facade for the multi-agent workflow."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.persistence.semantic_store import SemanticStore

SEMANTIC_VERSION = "semantic-registry-sqlite-p1.3"


def infer_business_domain(text: str) -> str:
    lower = text.lower()
    sales_tokens = [
        "sales",
        "sale",
        "gmv",
        "\u8ba2\u5355",
        "\u9500\u552e",
        "\u6210\u4ea4",
    ]
    if any(token in lower for token in sales_tokens):
        return "sales"
    return "general"


def is_high_risk(text: str) -> bool:
    lower = text.lower()
    risk_tokens = [
        "\u5ba1\u8ba1",
        "\u8d22\u52a1",
        "\u5bf9\u5916\u62ab\u9732",
        "\u8463\u4e8b\u4f1a",
        "\u76d1\u7ba1",
        "audit",
        "finance",
        "board",
        "regulator",
    ]
    return any(token in lower for token in risk_tokens)


def infer_metric_terms(text: str) -> list[str]:
    lower = text.lower()
    terms: list[str] = []
    for synonym in SemanticStore().list_synonyms():
        if synonym.lower() in lower and synonym not in terms:
            terms.append(synonym)

    sales_total = "\u9500\u552e\u603b\u989d"
    if "\u9500\u552e" in text and "\u603b\u989d" in text and sales_total not in terms:
        terms.append(sales_total)
    return terms


def retrieve_metrics(terms: list[str], domain: str) -> list[dict[str, Any]]:
    return SemanticStore().retrieve_metrics(terms, domain)


def select_domain_default(
    metric_candidates: list[dict[str, Any]],
    metric_term: str,
    domain: str,
    high_risk: bool = False,
) -> dict[str, Any] | None:
    return SemanticStore().select_default_metric(
        metric_candidates,
        metric_term,
        domain,
        scope_type="domain",
        scope_id=domain,
        high_risk=high_risk,
    )


def has_semantic_permission(roles: list[str], action: str, resource_type: str, resource_id: str) -> bool:
    return SemanticStore().has_permission(roles, action, resource_type, resource_id)


def resolve_access_policy(roles: list[str], business_domain: str, semantic_id: str) -> dict[str, Any]:
    return SemanticStore().resolve_access_policy(roles, business_domain, semantic_id)


def resolve_time_range(text: str, calendar: str = "company_business_week") -> dict[str, Any]:
    today = date.today()
    lower = text.lower()
    if "\u4e0a\u5468" in text or "last week" in lower:
        start_this_week = today - timedelta(days=today.weekday())
        start = start_this_week - timedelta(days=7)
        end = start_this_week
        return {
            "expression": "last_week",
            "calendar": calendar,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "inclusive_end": False,
            "version": "calendar.company_business_week.v1",
        }
    return {
        "expression": "unspecified",
        "calendar": calendar,
        "start_date": "",
        "end_date": "",
        "inclusive_end": False,
        "version": "calendar.company_business_week.v1",
    }


def render_metric_scope(metric: dict[str, Any]) -> str:
    return (
        f"{metric.get('display_name', metric.get('name'))} "
        f"{metric.get('semantic_id')}@{metric.get('version')}"
    )
