"""Memory Extractor agent for candidate-only user experience learning."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage

from src.graph.state import AnalysisState


def memory_extractor_node(state: AnalysisState) -> dict[str, Any]:
    """Extract candidate memories without applying them automatically."""

    user_text = _last_user_text(state)
    user_id = state.get("user_id", "anonymous")
    session_id = state.get("session_id", "")
    turn_id = state.get("turn_id", "")
    plan_id = state.get("plan_id", "")
    domain = _business_domain(state)

    candidates = []
    candidates.extend(_language_candidates(user_text, user_id, session_id, turn_id, plan_id, domain))
    candidates.extend(_time_preference_candidates(user_text, user_id, session_id, turn_id, plan_id, domain))
    candidates.extend(_output_preference_candidates(user_text, user_id, session_id, turn_id, plan_id, domain))

    summary = f"Extracted {len(candidates)} memory candidate(s)."
    return {
        "memory_candidates": candidates,
        "code_result": {
            "success": True,
            "code": "",
            "stdout": summary,
            "stderr": "",
            "figures": [],
        },
        "supervisor_decision": "memory_candidates_extracted",
        "messages": [AIMessage(content=summary)],
    }


def _language_candidates(
    text: str,
    user_id: str,
    session_id: str,
    turn_id: str,
    plan_id: str,
    domain: str,
) -> list[dict[str, Any]]:
    if not _contains_chinese(text):
        return []
    return [
        _candidate(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            plan_id=plan_id,
            domain=domain,
            memory_type="user_preference",
            key="interaction.language",
            value={"language": "zh-CN"},
            confidence=0.75,
            rationale="The user submitted this turn in Chinese.",
        )
    ]


def _time_preference_candidates(
    text: str,
    user_id: str,
    session_id: str,
    turn_id: str,
    plan_id: str,
    domain: str,
) -> list[dict[str, Any]]:
    lowered = text.lower()
    has_last_7_days = any(token in text for token in ["近七天", "最近七天", "近7天", "最近7天"]) or "last 7 days" in lowered
    exclude_holidays = any(token in text for token in ["不包含节假日", "排除节假日", "不含节假日", "剔除节假日"])
    if not (has_last_7_days and exclude_holidays):
        return []
    return [
        _candidate(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            plan_id=plan_id,
            domain=domain,
            memory_type="user_preference",
            key="relative_time.last_7_days",
            value={"exclude_holidays": True},
            confidence=0.82,
            rationale="The user explicitly described last seven days as excluding holidays.",
        )
    ]


def _output_preference_candidates(
    text: str,
    user_id: str,
    session_id: str,
    turn_id: str,
    plan_id: str,
    domain: str,
) -> list[dict[str, Any]]:
    if not any(token in text for token in ["董事会", "管理层", "老板", "高管"]):
        return []
    return [
        _candidate(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            plan_id=plan_id,
            domain=domain,
            memory_type="output_preference",
            key="report.audience",
            value={"audience": "executive"},
            confidence=0.65,
            rationale="The user requested output for a leadership or board audience.",
        )
    ]


def _candidate(
    user_id: str,
    session_id: str,
    turn_id: str,
    plan_id: str,
    domain: str,
    memory_type: str,
    key: str,
    value: dict[str, Any],
    confidence: float,
    rationale: str,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "plan_id": plan_id,
        "memory_type": memory_type,
        "memory_key": key,
        "memory_value": value,
        "scope": "user",
        "business_domain": domain,
        "confidence": confidence,
        "status": "candidate",
        "source": {
            "source_type": "turn",
            "session_id": session_id,
            "turn_id": turn_id,
            "plan_id": plan_id,
        },
        "rationale": rationale,
    }


def _business_domain(state: AnalysisState) -> str:
    context = state.get("context_profile", {})
    if context.get("business_domain"):
        return context["business_domain"]
    intent = state.get("query_intent", {})
    return intent.get("business_domain", "general")


def _last_user_text(state: AnalysisState) -> str:
    for message in reversed(state.get("messages", []) or []):
        if getattr(message, "type", "") == "human" or message.__class__.__name__.lower().startswith("human"):
            return getattr(message, "content", str(message))
    return ""


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))
