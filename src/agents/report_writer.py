"""Evidence-driven report writer for the P1 data analysis agent."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from configs.settings import settings
from src.graph.state import AnalysisState
from src.persistence.session_store import SessionStore
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

REPORT_PROMPT = """You are an enterprise data analysis report writer.

You must use only the provided evidence. Do not invent facts, metrics, trends,
causes, recommendations, or numbers. If evidence is insufficient, say exactly
what is missing.

Write a concise Markdown report with:
1. Answer
2. Metric scope used
3. Evidence used
4. Key findings
5. Charts or artifacts
6. Limitations
7. Recommended next actions

The metric scope section is mandatory when evidence contains metric_scope. It
must include semantic id, version, business owner, technical owner, source, and
time range when those fields are present in evidence.

Evidence:
{evidence_context}
"""


def report_writer_node(state: AnalysisState) -> dict[str, Any]:
    evidence = _load_evidence(state)
    plan = state.get("analysis_plan", {})

    if not evidence:
        msg = (
            "I cannot write a data report because no execution evidence is available. "
            "A report can only cite persisted code results, stdout/stderr, metrics, or figures."
        )
        return {
            "messages": [AIMessage(content=msg)],
            "error": "missing_evidence",
            "needs_retry": False,
        }

    evidence_context = _build_evidence_context(evidence)
    user_request = plan.get("user_message") or _last_human_message(state.get("messages", []))

    try:
        response = get_llm().invoke(
            [
                SystemMessage(content=REPORT_PROMPT.format(evidence_context=evidence_context)),
                HumanMessage(content=user_request),
            ]
        )
        report = response.content.strip()
    except Exception as exc:
        logger.warning("ReportWriter LLM fallback activated: %s", exc)
        report = _fallback_report(evidence_context)

    validation = _validate_report_against_evidence(report, evidence_context)
    if validation["status"] != "passed":
        msg = (
            "Report validation failed because it referenced numbers that were not found "
            f"in execution evidence: {', '.join(validation.get('missing_numbers', []))}"
        )
        _save_report_validation(state, validation)
        return {
            "messages": [AIMessage(content=msg)],
            "validation_results": list(state.get("validation_results", [])) + [validation],
            "error": "report_evidence_validation_failed",
        }

    report_path = _save_report(report)
    _save_report_validation(state, validation)

    reply = f"Evidence-based report generated: `{report_path}`\n\n---\n\n{report}"
    return {
        "messages": [AIMessage(content=reply)],
        "report": report,
        "validation_results": list(state.get("validation_results", [])) + [validation],
    }


def _fallback_report(evidence_context: str) -> str:
    return (
        "# Evidence-Based Report\n\n"
        "## Answer\n"
        "The language model was unavailable, so this deterministic report only reproduces persisted evidence.\n\n"
        "## Evidence Used\n"
        f"{evidence_context}\n\n"
        "## Limitations\n"
        "No additional interpretation was generated."
    )


def _load_evidence(state: AnalysisState) -> list[dict]:
    evidence = list(state.get("evidence", []) or [])
    plan_id = state.get("plan_id")
    if plan_id:
        try:
            evidence.extend(SessionStore().list_evidence(plan_id))
        except Exception as exc:
            logger.debug("Could not load persisted evidence: %s", exc)

    deduped: dict[str, dict] = {}
    for item in evidence:
        key = item.get("id") or f"{item.get('task_id')}:{item.get('evidence_type')}:{len(deduped)}"
        deduped[key] = item
    return list(deduped.values())


def _build_evidence_context(evidence: list[dict]) -> str:
    parts = []
    for idx, item in enumerate(evidence, 1):
        parts.append(
            "\n".join(
                [
                    f"## Evidence {idx}",
                    f"- type: {item.get('evidence_type')}",
                    f"- task_id: {item.get('task_id')}",
                    f"- success: {item.get('success')}",
                    f"- dataset_refs: {item.get('dataset_refs', [])}",
                    f"- metric_refs: {item.get('metric_refs', {})}",
                    f"- figure_paths: {item.get('figure_paths', [])}",
                    "stdout:",
                    str(item.get("stdout", ""))[:3000],
                    "stderr:",
                    str(item.get("stderr", ""))[:1000],
                    "content:",
                    str(item.get("content", ""))[:2000],
                ]
            )
        )
    return "\n\n".join(parts)


def _validate_report_against_evidence(report: str, evidence_context: str) -> dict[str, Any]:
    evidence_numbers = set(_numbers(evidence_context))
    report_numbers = set(_numbers(report))
    missing = sorted(n for n in report_numbers if n not in evidence_numbers)
    return {
        "validation_type": "report_evidence_gate",
        "status": "failed" if missing else "passed",
        "checks": [
            {"name": "has_evidence", "passed": bool(evidence_context.strip())},
            {"name": "numbers_exist_in_evidence", "passed": not missing},
        ],
        "missing_numbers": missing,
        "error_message": "unsupported_numbers" if missing else "",
    }


def _numbers(text: str) -> list[str]:
    # Ignore tiny section numbers; validate material numeric claims.
    return re.findall(r"(?<![\w.])-?(?:\d{2,}|\d+\.\d+)%?", text)


def _save_report(report: str) -> Path:
    report_dir = settings.OUTPUT_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text(report, encoding="utf-8")
    return path


def _save_report_validation(state: AnalysisState, validation: dict) -> None:
    plan_id = state.get("plan_id")
    session_id = state.get("session_id")
    if not plan_id or not session_id:
        return
    try:
        SessionStore().save_validation(session_id, plan_id, None, validation)
    except Exception as exc:
        logger.debug("Could not save report validation: %s", exc)


def _last_human_message(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human" or msg.__class__.__name__.lower().startswith("human"):
            return getattr(msg, "content", str(msg))
    return ""
