"""P1 Coordinator: intent, clarification, planning, supervision, and validation."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
try:
    from langgraph.graph import END
except ModuleNotFoundError:
    END = "__end__"

from src.graph.state import AnalysisState, TaskItem
from src.persistence.session_store import SessionStore
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

MAX_RETRY = 3

SEMANTIC_AGENTS = {
    "intent_parser",
    "context_resolver",
    "semantic_retriever",
    "disambiguation_engine",
    "logical_plan_builder",
    "policy_checker",
}
EXECUTION_AGENTS = {
    "query_generator",
    "sql_validator",
    "execution_engine",
    "data_profiler",
    "code_generator",
    "visualizer",
    "report_writer",
    "chat",
    "debugger",
    "memory_extractor",
}
VALID_AGENTS = SEMANTIC_AGENTS | EXECUTION_AGENTS
DATA_INTENTS = {
    "data_profile",
    "descriptive_analysis",
    "diagnostic_analysis",
    "visualization",
    "reporting",
    "forecasting",
    "recommendation",
    "data_quality",
}

INTENT_TYPES = [
    "chat",
    "data_profile",
    "descriptive_analysis",
    "diagnostic_analysis",
    "visualization",
    "reporting",
    "forecasting",
    "recommendation",
    "data_quality",
    "unknown",
]

P1_COORDINATOR_PROMPT = """You are the P1 Coordinator for an enterprise data analysis agent.

You must return only valid JSON. Do not calculate data results yourself.

Classify the user's request and decide whether execution is allowed. Execution is
allowed only when the request is sufficiently specified. If required information
is missing, set clarification_required=true and ask concise clarification
questions.

Intent types:
chat, data_profile, descriptive_analysis, diagnostic_analysis, visualization,
reporting, forecasting, recommendation, data_quality, unknown.

For data tasks, verify these fields:
- dataset availability or database source availability
- business question
- metrics or target variable when needed
- dimensions/comparison groups when needed
- time range/time column when needed
- output expectation

Available datasets:
{dataset_context}

Available database sources:
{database_context}

Return JSON with this shape:
{{
  "intent": {{
    "intent_type": "...",
    "business_question": "...",
    "analysis_goal": "...",
    "target_entities": [],
    "metrics": [],
    "dimensions": [],
    "time_range": "",
    "filters": [],
    "output_expectation": [],
    "required_inputs": [],
    "ambiguities": [],
    "confidence": 0.0,
    "requires_data": true
  }},
  "clarification_required": true,
  "clarification_questions": [],
  "missing_fields": [],
  "assumptions": [],
  "expected_outputs": [],
  "risk_controls": [],
  "tasks": [
    {{
      "agent": "data_profiler|code_generator|visualizer|report_writer|chat",
      "description": "...",
      "depends_on": [],
      "input_dataset_ids": [],
      "expected_evidence": []
    }}
  ]
}}
"""


def coordinator_p1_node(state: AnalysisState) -> dict[str, Any]:
    """Run one supervision step for the P1 analysis workflow."""
    store = SessionStore()
    session_id = state.get("session_id", "")
    task_queue = list(state.get("task_queue", []))
    completed_tasks = list(state.get("completed_tasks", []))
    failed_tasks = list(state.get("failed_tasks", []))
    current_task = state.get("current_task")

    if current_task:
        return _supervise_last_task(state, store)

    if not task_queue and not completed_tasks and not failed_tasks and not state.get("analysis_plan"):
        return _dispatch_semantic_pipeline(state, store)

    if task_queue:
        next_task = dict(task_queue[0])
        remaining = task_queue[1:]
        next_task["status"] = "running"
        task_id = next_task.get("id", "")
        if task_id:
            store.update_task_status(
                task_id,
                "running",
                attempt_count=next_task.get("attempt_count", 0),
            )
        return {
            "current_task": next_task,
            "current_task_id": task_id,
            "task_queue": remaining,
            "next_agent": next_task.get("agent", "chat"),
            "supervisor_decision": "dispatch_task",
        }

    plan = state.get("analysis_plan", {})
    plan_id = state.get("plan_id") or plan.get("id", "")
    intent_type = (plan.get("intent") or state.get("structured_intent", {})).get("intent_type", "")
    if _should_schedule_memory_extractor(completed_tasks, failed_tasks):
        memory_task = {
            "id": str(uuid.uuid4())[:8],
            "plan_id": plan_id,
            "turn_id": state.get("turn_id", ""),
            "agent": "memory_extractor",
            "description": "Extract candidate user preferences and reusable experience from this turn.",
            "depends_on": [task.get("id", "") for task in completed_tasks if task.get("id")],
            "input_dataset_ids": [],
            "expected_evidence": ["memory_candidates"],
            "status": "running",
            "attempt_count": 0,
            "result_summary": "",
            "failure_reason": "",
        }
        if plan_id:
            store.add_analysis_task(session_id, plan_id, memory_task)
            store.update_task_status(memory_task["id"], "running", attempt_count=0)
        return {
            "messages": [AIMessage(content="Extracting candidate memories from this turn.")],
            "scheduling_complete": False,
            "current_task": memory_task,
            "current_task_id": memory_task["id"],
            "next_agent": "memory_extractor",
            "supervisor_decision": "prepare_memory_extraction",
        }

    if intent_type == "chat" or any(task.get("agent") == "report_writer" for task in completed_tasks):
        if plan_id:
            store.update_plan_status(plan_id, "completed")
        if state.get("turn_id"):
            store.update_turn_status(state.get("turn_id", ""), "completed")
        return {
            "messages": [AIMessage(content="Request completed.")],
            "scheduling_complete": True,
            "next_agent": END,
            "supervisor_decision": "completed",
        }

    if failed_tasks:
        if plan_id:
            store.update_plan_status(plan_id, "failed")
        if state.get("turn_id"):
            store.update_turn_status(state.get("turn_id", ""), "failed")
        message = _failure_message(failed_tasks)
        return {
            "messages": [AIMessage(content=message)],
            "scheduling_complete": True,
            "next_agent": END,
            "supervisor_decision": "failed",
        }

    report_task = {
        "id": str(uuid.uuid4())[:8],
        "plan_id": plan_id,
        "turn_id": state.get("turn_id", ""),
        "agent": "report_writer",
        "description": "Generate an evidence-backed analysis report.",
        "depends_on": [task.get("id", "") for task in completed_tasks if task.get("id")],
        "input_dataset_ids": [],
        "expected_evidence": ["report_file", "evidence_citations"],
        "status": "running",
        "attempt_count": 0,
        "result_summary": "",
        "failure_reason": "",
    }
    if plan_id:
        store.add_analysis_task(session_id, plan_id, report_task)
        store.update_task_status(report_task["id"], "running", attempt_count=0)
    return {
        "messages": [AIMessage(content="Analysis tasks completed. Preparing evidence-based report.")],
        "scheduling_complete": False,
        "current_task": report_task,
        "current_task_id": report_task["id"],
        "next_agent": "report_writer",
        "supervisor_decision": "prepare_report",
    }


def _dispatch_semantic_pipeline(state: AnalysisState, store: SessionStore) -> dict[str, Any]:
    """Dispatch pre-execution semantic agents before creating a runnable plan."""
    if state.get("clarification_required"):
        return _persist_clarification(state, store)

    if not state.get("query_intent"):
        return _route_to_semantic_agent("intent_parser")

    intent = state.get("query_intent", {})
    if intent.get("task_type") == "chat":
        return _create_plan_from_semantics(state, store)
    if intent.get("task_type") == "data_analysis" and state.get("datasets"):
        return _create_plan_from_semantics(state, store)

    if not state.get("context_profile"):
        return _route_to_semantic_agent("context_resolver")

    if not state.get("semantic_candidates"):
        return _route_to_semantic_agent("semantic_retriever")

    if not state.get("disambiguation"):
        return _route_to_semantic_agent("disambiguation_engine")

    disambiguation = state.get("disambiguation", {})
    if disambiguation.get("action") == "clarify" or state.get("clarification_required"):
        return _persist_clarification(state, store)

    if disambiguation.get("action") == "blocked":
        if state.get("turn_id"):
            store.update_turn_status(state.get("turn_id", ""), "failed")
        return {
            "messages": [AIMessage(content=state.get("error") or disambiguation.get("reason", "Semantic resolution failed."))],
            "scheduling_complete": True,
            "next_agent": END,
            "supervisor_decision": "semantic_blocked",
        }

    if not state.get("logical_plan"):
        return _route_to_semantic_agent("logical_plan_builder")

    if not state.get("policy_decision"):
        return _route_to_semantic_agent("policy_checker")

    policy = state.get("policy_decision", {})
    if not policy.get("allowed", False):
        if state.get("turn_id"):
            store.update_turn_status(state.get("turn_id", ""), "failed")
        return {
            "messages": [AIMessage(content=state.get("error") or f"Policy check denied execution: {policy.get('reason', '')}")],
            "scheduling_complete": True,
            "next_agent": END,
            "supervisor_decision": "policy_denied",
        }

    return _create_plan_from_semantics(state, store)


def _route_to_semantic_agent(agent: str) -> dict[str, Any]:
    return {
        "next_agent": agent,
        "supervisor_decision": f"dispatch_{agent}",
    }


def _persist_clarification(state: AnalysisState, store: SessionStore) -> dict[str, Any]:
    questions = state.get("clarification_questions", []) or state.get("disambiguation", {}).get("questions", [])
    question_text = "\n".join(f"- {question}" for question in questions) or "- Please clarify the business meaning."
    clarification_id = store.create_clarification(
        state.get("session_id", ""),
        question_text,
        ["business_semantic_ambiguity"],
        turn_id=state.get("turn_id", ""),
    )
    if state.get("turn_id"):
        store.update_turn_status(state.get("turn_id", ""), "waiting_clarification")
    return {
        "messages": [AIMessage(content="I need a business clarification before execution:\n\n" + question_text)],
        "clarification_required": True,
        "clarification_questions": questions,
        "clarification_id": clarification_id,
        "turn_id": state.get("turn_id", ""),
        "scheduling_complete": True,
        "next_agent": END,
        "supervisor_decision": "clarification_required",
    }


def _create_plan_from_semantics(state: AnalysisState, store: SessionStore) -> dict[str, Any]:
    user_message = _last_human_message(state.get("messages", []))
    intent = state.get("query_intent", {})
    logical_plan = state.get("logical_plan", {})
    datasets = state.get("datasets", [])
    database_sources = state.get("database_sources", [])
    tasks = _tasks_from_semantics(intent, logical_plan, datasets, database_sources)

    plan_id = str(uuid.uuid4())
    turn_id = state.get("turn_id", "")
    for task in tasks:
        task["plan_id"] = plan_id
        task["turn_id"] = turn_id

    plan = {
        "id": plan_id,
        "session_id": state.get("session_id", ""),
        "turn_id": turn_id,
        "user_message": user_message,
        "intent": {
            "intent_type": intent.get("task_type", "chat"),
            "business_question": user_message,
            "analysis_goal": user_message,
            "metrics": intent.get("raw_metrics", []),
            "dimensions": intent.get("raw_dimensions", []),
            "time_range": intent.get("raw_time", ""),
            "filters": intent.get("raw_filters", []),
            "requires_data": intent.get("requires_data", False),
        },
        "logical_plan": logical_plan,
        "assumptions": _semantic_assumptions(state),
        "tasks": tasks,
        "expected_outputs": ["evidence-backed answer", "metric scope disclosure"],
        "risk_controls": _risk_controls(database_sources) + ["metric_scope_must_be_disclosed"],
        "status": "planned",
    }
    store.create_analysis_plan(state.get("session_id", ""), user_message, plan)
    store.append_turn_plan(turn_id, plan_id)
    store.update_plan_status(plan_id, "running")

    first_task = dict(tasks[0])
    remaining = tasks[1:]
    first_task["status"] = "running"
    store.update_task_status(first_task["id"], "running", attempt_count=0)

    return {
        "structured_intent": plan["intent"],
        "intent": intent.get("task_type", "chat"),
        "analysis_plan": plan,
        "plan_id": plan_id,
        "turn_id": turn_id,
        "task_queue": remaining,
        "current_task": first_task,
        "current_task_id": first_task["id"],
        "completed_tasks": [],
        "failed_tasks": [],
        "clarification_required": False,
        "scheduling_complete": False,
        "next_agent": first_task.get("agent", "chat"),
        "max_retry": MAX_RETRY,
        "supervisor_decision": "plan_created",
    }


def _tasks_from_semantics(
    intent: dict,
    logical_plan: dict,
    datasets: list[dict],
    database_sources: list[dict],
) -> list[TaskItem]:
    dataset_ids = [_dataset_ref(ds, i) for i, ds in enumerate(datasets)]
    task_type = intent.get("task_type", "chat")
    if task_type == "chat":
        return [_task("chat", "Answer the user conversationally.", ["message"], dataset_ids)]

    if logical_plan and database_sources:
        return [
            _task("query_generator", "Generate executable SQL from governed semantic objects.", ["sql", "metric_scope"], dataset_ids),
            _task("sql_validator", "Validate SQL against Catalog, access policy, and read-only rules.", ["sql_validation", "catalog_lineage"], dataset_ids),
            _task("execution_engine", "Execute read-only query and materialize result evidence.", ["query_result", "dataset_snapshot"], dataset_ids),
        ]

    return [
        _task("data_profiler", "Profile available data and record quality evidence.", ["data_profile", "code_execution"], dataset_ids),
        _task("code_generator", intent.get("analysis_goal") or "Run the requested analysis.", ["metric_result", "code_execution"], dataset_ids),
    ]


def _semantic_assumptions(state: AnalysisState) -> list[str]:
    assumptions: list[str] = []
    disambiguation = state.get("disambiguation", {})
    if disambiguation.get("reason"):
        assumptions.append(disambiguation["reason"])
    logical_plan = state.get("logical_plan", {})
    metric = logical_plan.get("metric", {})
    if metric:
        assumptions.append(
            f"Metric scope: {metric.get('semantic_id')}@{metric.get('version')} "
            f"owned by {metric.get('business_owner')} / {metric.get('technical_owner')}"
        )
    time_range = logical_plan.get("time_range", {})
    if time_range:
        assumptions.append(
            f"Time range: {time_range.get('expression')} "
            f"{time_range.get('start_date')} to {time_range.get('end_date')} "
            f"using {time_range.get('calendar')}"
        )
    return assumptions


def _interpret_and_plan(state: AnalysisState, store: SessionStore) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = _last_human_message(messages)
    datasets = state.get("datasets", [])
    database_sources = state.get("database_sources", [])
    datasets, materialized_notice = _maybe_materialize_database_dataset(
        user_message,
        datasets,
        database_sources,
        state.get("session_id", ""),
        store,
    )
    llm_result = _call_intent_llm(user_message, datasets, database_sources)

    intent = llm_result.get("intent", {})
    intent_type = intent.get("intent_type", "unknown")
    if intent_type not in INTENT_TYPES:
        intent_type = "unknown"
        intent["intent_type"] = intent_type

    missing_fields = _deterministic_missing_fields(intent, datasets, database_sources)
    clarification_questions = list(llm_result.get("clarification_questions", []) or [])
    if missing_fields:
        clarification_questions = _build_clarification_questions(missing_fields, intent)

    clarification_required = bool(missing_fields or llm_result.get("clarification_required"))

    if clarification_required:
        question = "\n".join(f"- {q}" for q in clarification_questions) or "- Please clarify your analysis goal."
        clarification_id = store.create_clarification(
            state.get("session_id", ""),
            question,
            missing_fields or ["ambiguous_request"],
            turn_id=state.get("turn_id", ""),
        )
        if state.get("turn_id"):
            store.update_turn_status(state.get("turn_id", ""), "waiting_clarification")
        content = "Before I can run the analysis, I need clarification:\n\n" + question
        return {
            "messages": [AIMessage(content=content)],
            "structured_intent": intent,
            "intent": intent_type,
            "clarification_required": True,
            "clarification_questions": clarification_questions,
            "clarification_id": clarification_id,
            "turn_id": state.get("turn_id", ""),
            "scheduling_complete": True,
            "next_agent": END,
            "supervisor_decision": "clarification_required",
        }

    tasks = _normalize_tasks(llm_result.get("tasks", []), intent, datasets, database_sources)
    plan_id = str(uuid.uuid4())
    turn_id = state.get("turn_id", "")
    for task in tasks:
        task["plan_id"] = plan_id
        task["turn_id"] = turn_id
    plan = {
        "id": plan_id,
        "session_id": state.get("session_id", ""),
        "turn_id": turn_id,
        "user_message": user_message,
        "intent": intent,
        "assumptions": llm_result.get("assumptions", []),
        "tasks": tasks,
        "expected_outputs": llm_result.get("expected_outputs", []),
        "risk_controls": _risk_controls(database_sources),
        "status": "planned",
    }
    store.create_analysis_plan(state.get("session_id", ""), user_message, plan)
    store.append_turn_plan(turn_id, plan_id)
    store.update_plan_status(plan_id, "running")

    first_task = dict(tasks[0])
    remaining = tasks[1:]
    first_task["status"] = "running"
    store.update_task_status(first_task["id"], "running", attempt_count=0)

    return {
        "structured_intent": intent,
        "intent": intent_type,
        "analysis_plan": plan,
        "plan_id": plan_id,
        "turn_id": turn_id,
        "task_queue": remaining,
        "current_task": first_task,
        "current_task_id": first_task["id"],
        "datasets": datasets,
        "completed_tasks": [],
        "failed_tasks": [],
        "clarification_required": False,
        "scheduling_complete": False,
        "next_agent": first_task.get("agent", "chat"),
        "max_retry": MAX_RETRY,
        "supervisor_decision": "plan_created",
        "messages": [AIMessage(content=materialized_notice)] if materialized_notice else [],
    }


def _supervise_last_task(state: AnalysisState, store: SessionStore) -> dict[str, Any]:
    task = dict(state.get("current_task") or {})
    plan_id = state.get("plan_id") or task.get("plan_id", "")
    session_id = state.get("session_id", "")
    task_id = task.get("id", "")
    attempt_count = int(task.get("attempt_count", 0))
    code_result = state.get("code_result", {})
    existing_evidence = list(state.get("evidence", []))
    existing_validations = list(state.get("validation_results", []))
    if task.get("agent") == "sql_validator":
        existing_validations = [
            item for item in existing_validations
            if item.get("validation_type") != "governed_sql_guard"
        ]
    existing_audit_events = list(state.get("audit_events", []))

    evidence = _build_evidence(state, task, plan_id)
    evidence_id = store.save_evidence(session_id, plan_id, task_id, evidence)
    evidence["id"] = evidence_id

    persisted_validations = []
    if task.get("agent") == "sql_validator" and state.get("sql_validation"):
        sql_validation = dict(state.get("sql_validation", {}))
        sql_validation["turn_id"] = state.get("turn_id", "")
        sql_validation_id = store.save_validation(session_id, plan_id, task_id, sql_validation)
        sql_validation["id"] = sql_validation_id
        persisted_validations.append(sql_validation)

    validation = _validate_task_result(state, task, evidence)
    validation["turn_id"] = state.get("turn_id", "")
    validation_id = store.save_validation(session_id, plan_id, task_id, validation)
    validation["id"] = validation_id
    audit_event = _save_task_audit_event(
        store=store,
        state=state,
        task=task,
        plan_id=plan_id,
        session_id=session_id,
        evidence_id=evidence_id,
        validation=validation,
        persisted_validations=persisted_validations,
    )

    all_evidence = existing_evidence + [evidence]
    all_validations = existing_validations + persisted_validations + [validation]
    all_audit_events = existing_audit_events + ([audit_event] if audit_event else [])

    if validation["status"] == "passed":
        persisted_memory_candidates = _save_memory_candidates(store, state, task, evidence_id)
        completed_task = dict(task)
        completed_task["status"] = "completed"
        completed_task["result_summary"] = _task_result_summary(evidence)
        store.update_task_status(
            task_id,
            "completed",
            result_summary=completed_task["result_summary"],
            attempt_count=attempt_count,
        )
        return {
            "current_task": {},
            "current_task_id": "",
            "completed_tasks": list(state.get("completed_tasks", [])) + [completed_task],
            "evidence": all_evidence,
            "validation_results": all_validations,
            "audit_events": all_audit_events,
            "memory_candidates": persisted_memory_candidates or state.get("memory_candidates", []),
            "needs_retry": False,
            "needs_debug": False,
            "retry_count": 0,
            "next_agent": "coordinator_p1",
            "supervisor_decision": "task_completed",
        }

    attempt_count += 1
    if attempt_count >= MAX_RETRY:
        failed_task = dict(task)
        failed_task["status"] = "failed"
        failed_task["attempt_count"] = attempt_count
        failed_task["failure_reason"] = validation.get("error_message", "Validation failed")
        store.update_task_status(
            task_id,
            "failed",
            failure_reason=failed_task["failure_reason"],
            attempt_count=attempt_count,
        )
        return {
            "current_task": {},
            "current_task_id": "",
            "failed_tasks": list(state.get("failed_tasks", [])) + [failed_task],
            "evidence": all_evidence,
            "validation_results": all_validations,
            "audit_events": all_audit_events,
            "validation_failure": _state_validation_failure(state, validation),
            "needs_retry": False,
            "needs_debug": False,
            "retry_count": attempt_count,
            "error": failed_task["failure_reason"],
            "next_agent": "coordinator_p1",
            "supervisor_decision": "max_retry_reached",
        }

    retry_task = dict(task)
    retry_task["status"] = "pending"
    retry_task["attempt_count"] = attempt_count
    store.update_task_status(
        task_id,
        "pending",
        failure_reason=validation.get("error_message", ""),
        attempt_count=attempt_count,
    )

    if code_result and code_result.get("success") is False and task.get("agent") != "debugger":
        debug_task = {
            "id": str(uuid.uuid4())[:8],
            "plan_id": plan_id,
            "agent": "debugger",
            "description": f"Fix failed task: {task.get('description', '')}",
            "depends_on": [task_id],
            "input_dataset_ids": task.get("input_dataset_ids", []),
            "expected_evidence": ["debug_attempt", "code_execution"],
            "status": "pending",
            "attempt_count": attempt_count,
            "result_summary": "",
            "failure_reason": "",
        }
        if plan_id:
            store.add_analysis_task(session_id, plan_id, debug_task)
        return {
            "current_task": {},
            "current_task_id": "",
            "task_queue": [debug_task, retry_task] + list(state.get("task_queue", [])),
            "evidence": all_evidence,
            "validation_results": all_validations,
            "audit_events": all_audit_events,
            "validation_failure": _state_validation_failure(state, validation),
            "needs_retry": True,
            "needs_debug": True,
            "retry_count": attempt_count,
            "next_agent": "coordinator_p1",
            "supervisor_decision": "retry_with_debugger",
        }

    return {
        "current_task": {},
        "current_task_id": "",
        "task_queue": [retry_task] + list(state.get("task_queue", [])),
        "evidence": all_evidence,
        "validation_results": all_validations,
        "audit_events": all_audit_events,
        "validation_failure": _state_validation_failure(state, validation),
        "needs_retry": True,
        "retry_count": attempt_count,
        "next_agent": "coordinator_p1",
        "supervisor_decision": "retry_task",
    }


def _call_intent_llm(user_message: str, datasets: list[dict], database_sources: list[dict]) -> dict:
    prompt = P1_COORDINATOR_PROMPT.format(
        dataset_context=_dataset_context(datasets),
        database_context=_database_context(database_sources),
    )
    try:
        response = get_llm().invoke([SystemMessage(content=prompt), HumanMessage(content=user_message)])
        return _extract_json(response.content)
    except Exception as exc:
        logger.warning("Intent LLM failed, using deterministic fallback: %s", exc)
        return _fallback_intent(user_message, datasets, database_sources)


def _maybe_materialize_database_dataset(
    user_message: str,
    datasets: list[dict],
    database_sources: list[dict],
    session_id: str,
    _store: SessionStore,
) -> tuple[list[dict], str]:
    """Detect explicit SQL without executing it outside the governed graph path."""
    if datasets or not database_sources:
        return datasets, ""

    match = re.search(r"(select\s+.+)", user_message, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return datasets, ""

    logger.info(
        "Direct SQL materialization was blocked for session %s; query must pass through sql_validator.",
        session_id,
    )
    return datasets, (
        "Direct SQL execution is disabled in governed mode. "
        "The request will be planned and executed through SQL Validator."
    )


def _extract_json(content: str) -> dict:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1)
    return json.loads(content)


def _fallback_intent(user_message: str, datasets: list[dict], database_sources: list[dict]) -> dict:
    lower = user_message.lower()
    data_tokens = [
        "analy",
        "trend",
        "chart",
        "plot",
        "report",
        "forecast",
        "diagnos",
        "compare",
        "metric",
        "\u5206\u6790",
        "\u8d8b\u52bf",
        "\u56fe\u8868",
        "\u62a5\u544a",
        "\u9884\u6d4b",
        "\u5bf9\u6bd4",
        "\u6307\u6807",
        "\u8bca\u65ad",
    ]
    chart_tokens = ["chart", "plot", "\u56fe\u8868", "\u53ef\u89c6\u5316"]
    needs_data = any(token in lower for token in data_tokens)
    intent_type = "chat"
    if needs_data:
        intent_type = "visualization" if any(t in lower for t in chart_tokens) else "descriptive_analysis"
    return {
        "intent": {
            "intent_type": intent_type,
            "business_question": user_message,
            "analysis_goal": user_message,
            "target_entities": [],
            "metrics": [],
            "dimensions": [],
            "time_range": "",
            "filters": [],
            "output_expectation": ["answer"],
            "required_inputs": [],
            "ambiguities": [],
            "confidence": 0.5,
            "requires_data": needs_data,
        },
        "clarification_required": needs_data and not (datasets or database_sources),
        "clarification_questions": [],
        "missing_fields": [],
        "assumptions": [],
        "expected_outputs": ["evidence-backed answer"],
        "risk_controls": [],
        "tasks": [],
    }

def _deterministic_missing_fields(intent: dict, datasets: list[dict], database_sources: list[dict]) -> list[str]:
    missing: list[str] = []
    intent_type = intent.get("intent_type", "unknown")
    requires_data = intent.get("requires_data", intent_type in DATA_INTENTS)
    if requires_data and not datasets and not database_sources:
        missing.append("dataset_or_database_source")
    if requires_data and not datasets and database_sources:
        missing.append("governed_semantic_metric")
    if requires_data and not intent.get("business_question"):
        missing.append("business_question")
    if intent_type in {"diagnostic_analysis", "forecasting", "recommendation"} and not intent.get("metrics"):
        missing.append("metrics_or_target")
    if intent_type == "forecasting" and not intent.get("time_range"):
        missing.append("forecast_horizon_or_time_range")
    if intent_type == "visualization" and not intent.get("dimensions") and not intent.get("metrics"):
        missing.append("chart_metric_or_dimension")
    return missing


def _build_clarification_questions(missing: list[str], intent: dict) -> list[str]:
    mapping = {
        "dataset_or_database_source": "Which dataset or read-only business database source should I analyze?",
        "governed_semantic_metric": "Which governed business metric or published report definition should I use?",
        "business_question": "What business question should this analysis answer?",
        "metrics_or_target": "Which metric, KPI, or target variable should I analyze?",
        "forecast_horizon_or_time_range": "What time range and forecast horizon should I use?",
        "chart_metric_or_dimension": "Which metric and grouping dimension should the chart use?",
    }
    return [mapping.get(field, f"Please clarify: {field}") for field in missing]


def _normalize_tasks(raw_tasks: list[dict], intent: dict, datasets: list[dict], database_sources: list[dict]) -> list[TaskItem]:
    tasks: list[TaskItem] = []
    dataset_ids = [_dataset_ref(ds, i) for i, ds in enumerate(datasets)]
    for raw in raw_tasks or []:
        agent = raw.get("agent", "chat")
        if agent not in VALID_AGENTS:
            agent = "chat"
        tasks.append(_task(agent, raw.get("description", ""), raw.get("expected_evidence", []), dataset_ids))

    if not tasks:
        intent_type = intent.get("intent_type", "chat")
        if intent_type == "chat":
            tasks = [_task("chat", intent.get("business_question", "Answer the user."), ["message"], dataset_ids)]
        else:
            tasks = [
                _task("data_profiler", "Profile available data and record quality evidence.", ["data_profile", "code_execution"], dataset_ids),
                _task("code_generator", intent.get("analysis_goal") or "Run the requested analysis.", ["metric_result", "code_execution"], dataset_ids),
            ]
            if intent_type in {"visualization", "reporting", "descriptive_analysis", "diagnostic_analysis"}:
                tasks.append(_task("visualizer", "Create required evidence-backed visualizations.", ["figure", "code_execution"], dataset_ids))
    return tasks


def _task(agent: str, description: str, expected_evidence: list[str], dataset_ids: list[str]) -> TaskItem:
    return {
        "id": str(uuid.uuid4())[:8],
        "agent": agent,
        "description": description or f"Run {agent}",
        "depends_on": [],
        "input_dataset_ids": dataset_ids,
        "expected_evidence": expected_evidence,
        "status": "pending",
        "attempt_count": 0,
        "result_summary": "",
        "failure_reason": "",
    }


def _build_evidence(state: AnalysisState, task: dict, plan_id: str) -> dict:
    agent = task.get("agent", "unknown")
    code_result = {} if agent in {"chat", "report_writer", "sql_validator"} else (state.get("code_result", {}) or {})
    figures = [] if agent in {"chat", "report_writer"} else (code_result.get("figures") or state.get("figures", []) or [])
    stdout = code_result.get("stdout", "") or ""
    metric_refs = _extract_metric_refs(stdout)
    logical_plan = state.get("logical_plan", {}) or {}
    generated_query = state.get("generated_query", {}) or {}
    metric = logical_plan.get("metric", {}) or {}
    if metric:
        metric_refs.setdefault("metric_scope", {
            "semantic_id": metric.get("semantic_id", ""),
            "version": metric.get("version", ""),
            "business_owner": metric.get("business_owner", ""),
            "technical_owner": metric.get("technical_owner", ""),
        })
    return {
        "plan_id": plan_id,
        "task_id": task.get("id", ""),
        "turn_id": state.get("turn_id", ""),
        "evidence_type": _evidence_type(agent, code_result, figures),
        "content": {
            "agent": agent,
            "task": task.get("description", ""),
            "session_id": state.get("session_id", ""),
            "turn_id": state.get("turn_id", ""),
            "plan_id": plan_id,
            "task_id": task.get("id", ""),
            "result_summary": _message_tail(state),
            "logical_plan": logical_plan if agent in {"query_generator", "execution_engine", "report_writer"} else {},
            "generated_query": generated_query if agent in {"query_generator", "execution_engine"} else {},
            "sql_validation": state.get("sql_validation", {}) if agent in {"sql_validator", "execution_engine", "report_writer"} else {},
            "validation_failure": state.get("validation_failure", {}) if agent in {"sql_validator", "execution_engine"} else {},
            "memory_candidates": state.get("memory_candidates", []) if agent == "memory_extractor" else [],
        },
        "code": code_result.get("code") or generated_query.get("sql") or ("" if agent in {"chat", "report_writer"} else state.get("current_code", "")),
        "stdout": stdout,
        "stderr": code_result.get("stderr", "") or (state.get("error", "") if agent == "report_writer" else ""),
        "figure_paths": figures,
        "dataset_refs": task.get("input_dataset_ids", []),
        "metric_refs": metric_refs,
        "success": _evidence_success(agent, code_result, state),
    }


def _validate_task_result(state: AnalysisState, task: dict, evidence: dict) -> dict:
    checks: list[dict[str, Any]] = []
    agent = task.get("agent", "")
    code = evidence.get("code", "")
    code_expected = agent in {"query_generator", "execution_engine", "data_profiler", "code_generator", "visualizer", "debugger"} or bool(code)

    if code_expected:
        passed = evidence.get("success") is True
        checks.append({"name": "code_execution_success", "passed": passed})
    else:
        checks.append({"name": "non_code_task", "passed": evidence.get("success") is True})

    if agent == "visualizer":
        paths = evidence.get("figure_paths", []) or []
        paths_exist = bool(paths) and all(Path(path).exists() for path in paths)
        checks.append({"name": "figure_exists", "passed": paths_exist})

    if agent in {"data_profiler", "code_generator", "visualizer"}:
        has_dataset = bool(state.get("datasets") or state.get("database_sources"))
        checks.append({"name": "dataset_required", "passed": has_dataset})

    if agent == "query_generator":
        checks.append({"name": "governed_query_exists", "passed": bool(state.get("generated_query", {}).get("sql"))})

    if agent == "sql_validator":
        checks.append({"name": "sql_validation_passed", "passed": state.get("sql_validation", {}).get("status") == "passed"})

    if agent == "execution_engine":
        checks.append({"name": "sql_validation_required", "passed": state.get("sql_validation", {}).get("status") == "passed"})
        checks.append({"name": "materialized_dataset_exists", "passed": bool(state.get("datasets"))})

    if agent == "memory_extractor":
        candidates = state.get("memory_candidates", [])
        checks.append({"name": "memory_candidates_structured", "passed": isinstance(candidates, list)})

    stderr = evidence.get("stderr", "") or ""
    no_traceback = "traceback" not in stderr.lower()
    checks.append({"name": "no_traceback", "passed": no_traceback})
    checks.append({"name": "agent_error_absent", "passed": not bool(evidence.get("stderr"))})

    failed = [check for check in checks if not check["passed"]]
    failure_reasons = [
        {
            "code": check["name"],
            "severity": "high" if check["name"] in {"sql_validation_passed", "sql_validation_required"} else "medium",
            "message": _task_gate_message(check["name"]),
            "details": check.get("details", {}),
        }
        for check in failed
    ]
    return {
        "validation_type": "task_hard_gate",
        "status": "failed" if failed else "passed",
        "checks": checks,
        "error_message": "; ".join(check["name"] for check in failed),
        "failure_reasons": failure_reasons,
        "failure_summary": "; ".join(reason["message"] for reason in failure_reasons),
    }


def _task_gate_message(check_name: str) -> str:
    messages = {
        "code_execution_success": "The task did not produce a successful execution result.",
        "figure_exists": "The expected chart file was not created.",
        "dataset_required": "The task requires a dataset or registered database source.",
        "governed_query_exists": "No governed SQL query was generated.",
        "sql_validation_passed": "SQL Validator rejected the generated query.",
        "sql_validation_required": "Execution was blocked because SQL validation did not pass.",
        "materialized_dataset_exists": "The query did not materialize a result dataset.",
        "memory_candidates_structured": "Memory extractor did not return a structured candidate list.",
        "no_traceback": "The task output contains a traceback.",
        "agent_error_absent": "The agent returned an error and cannot be marked completed.",
    }
    return messages.get(check_name, f"Task validation check failed: {check_name}.")


def _evidence_success(agent: str, code_result: dict, state: AnalysisState) -> bool:
    if agent == "sql_validator":
        return bool(state.get("sql_validation", {}).get("passed"))
    if code_result:
        return bool(code_result.get("success", False))
    if state.get("error") and agent != "chat":
        return False
    return agent in {"chat", "report_writer"}


def _save_task_audit_event(
    store: SessionStore,
    state: AnalysisState,
    task: dict,
    plan_id: str,
    session_id: str,
    evidence_id: str,
    validation: dict,
    persisted_validations: list[dict],
) -> dict[str, Any] | None:
    agent = task.get("agent", "unknown")
    sql_validation = state.get("sql_validation", {}) if agent == "sql_validator" else {}
    event_type = "analysis.task.completed" if validation.get("status") == "passed" else "analysis.task.failed"
    if agent == "sql_validator":
        event_type = "sql_validation.passed" if sql_validation.get("status") == "passed" else "sql_validation.failed"

    details = {
        "agent": agent,
        "task_description": task.get("description", ""),
        "evidence_id": evidence_id,
        "validation_id": validation.get("id", ""),
        "validation_type": validation.get("validation_type", ""),
        "error_message": validation.get("error_message", ""),
        "failure_reasons": validation.get("failure_reasons", []),
    }
    if persisted_validations:
        details["persisted_validations"] = [
            {
                "id": item.get("id", ""),
                "validation_type": item.get("validation_type", ""),
                "status": item.get("status", ""),
                "error_message": item.get("error_message", ""),
                "failure_reasons": item.get("failure_reasons", []),
            }
            for item in persisted_validations
        ]
    if sql_validation:
        details["sql_validation"] = {
            "status": sql_validation.get("status", ""),
            "failure_summary": sql_validation.get("failure_summary", ""),
            "failure_reasons": sql_validation.get("failure_reasons", []),
            "tables": sql_validation.get("tables", []),
            "columns": sql_validation.get("columns", []),
            "row_filters_applied": sql_validation.get("row_filters_applied"),
            "catalog_version": sql_validation.get("catalog_version", ""),
        }
    if state.get("generated_query"):
        generated = state.get("generated_query", {})
        details["query"] = {
            "language": generated.get("language", "sql"),
            "dialect": generated.get("dialect", ""),
            "source_alias": generated.get("source_alias", ""),
            "metric_semantic_id": generated.get("metric_semantic_id", ""),
            "metric_version": generated.get("metric_version", ""),
        }

    try:
        event_id = store.save_audit_event(
            session_id=session_id,
            plan_id=plan_id,
            task_id=task.get("id", ""),
            turn_id=state.get("turn_id", ""),
            actor=state.get("user_id", ""),
            event_type=event_type,
            resource_type="analysis_task",
            resource_id=task.get("id", ""),
            status=validation.get("status", "failed"),
            details=details,
        )
        return {
            "id": event_id,
            "event_type": event_type,
            "resource_type": "analysis_task",
            "resource_id": task.get("id", ""),
            "status": validation.get("status", "failed"),
            "details": details,
        }
    except Exception as exc:
        logger.warning("Failed to save audit event for task %s: %s", task.get("id", ""), exc)
        return None


def _state_validation_failure(state: AnalysisState, validation: dict) -> dict[str, Any]:
    sql_validation = state.get("sql_validation", {})
    if sql_validation.get("status") == "failed":
        generated = state.get("generated_query", {})
        return {
            "validation_type": sql_validation.get("validation_type", "governed_sql_guard"),
            "status": "failed",
            "summary": sql_validation.get("failure_summary") or sql_validation.get("error_message", "SQL validation failed."),
            "reasons": sql_validation.get("failure_reasons", []),
            "failed_checks": [check for check in sql_validation.get("checks", []) if not check.get("passed")],
            "source_alias": generated.get("source_alias", ""),
            "dialect": generated.get("dialect", ""),
            "sql": generated.get("sql", ""),
        }
    return {
        "validation_type": validation.get("validation_type", "task_hard_gate"),
        "status": validation.get("status", "failed"),
        "summary": validation.get("failure_summary") or validation.get("error_message", "Task validation failed."),
        "reasons": validation.get("failure_reasons", []),
        "failed_checks": [check for check in validation.get("checks", []) if not check.get("passed")],
    }


def _save_memory_candidates(
    store: SessionStore,
    state: AnalysisState,
    task: dict,
    evidence_id: str,
) -> list[dict[str, Any]]:
    if task.get("agent") != "memory_extractor":
        return []
    persisted = []
    for candidate in state.get("memory_candidates", []) or []:
        item = dict(candidate)
        item.setdefault("user_id", state.get("user_id", "anonymous"))
        item.setdefault("session_id", state.get("session_id", ""))
        item.setdefault("turn_id", state.get("turn_id", ""))
        item.setdefault("plan_id", state.get("plan_id", ""))
        item.setdefault("status", "candidate")
        item.setdefault("source", {})
        item["source"] = {
            **item.get("source", {}),
            "evidence_id": evidence_id,
            "task_id": task.get("id", ""),
        }
        try:
            item["id"] = store.save_memory_candidate(item)
            persisted.append(item)
        except Exception as exc:
            logger.warning("Failed to persist memory candidate: %s", exc)
    return persisted


def _should_schedule_memory_extractor(completed_tasks: list[dict], failed_tasks: list[dict]) -> bool:
    if failed_tasks:
        return False
    agents = {task.get("agent") for task in completed_tasks}
    if "memory_extractor" in agents:
        return False
    return bool(agents & {"chat", "report_writer"})


def route_by_agent_p1(state: AnalysisState) -> str:
    if state.get("scheduling_complete", False):
        return END
    next_agent = state.get("next_agent", "chat")
    if next_agent == END:
        return END
    if next_agent == "coordinator_p1":
        return "coordinator_p1"
    if next_agent not in VALID_AGENTS and next_agent != "debugger":
        logger.warning("Unknown agent '%s', routing to chat", next_agent)
        return "chat"
    return next_agent


def _evidence_type(agent: str, code_result: dict, figures: list[str]) -> str:
    if agent == "query_generator":
        return "query_plan"
    if agent == "sql_validator":
        return "sql_validation"
    if agent == "execution_engine":
        return "query_result"
    if agent == "visualizer" or figures:
        return "figure"
    if agent == "data_profiler":
        return "data_profile"
    if agent == "debugger":
        return "debug_attempt"
    if agent == "memory_extractor":
        return "memory_candidates"
    if code_result:
        return "code_execution"
    return "message"


def _extract_metric_refs(stdout: str) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    for line in stdout.splitlines():
        for key, value in re.findall(r"([A-Za-z_][\w\s%-]{0,40})\s*[:=]\s*(-?\d+(?:\.\d+)?)", line):
            refs[key.strip()] = value
    return refs


def _task_result_summary(evidence: dict) -> str:
    stdout = (evidence.get("stdout") or "").strip()
    if stdout:
        return stdout[:300]
    content = evidence.get("content", {})
    return (content.get("result_summary") or evidence.get("evidence_type", "completed"))[:300]


def _message_tail(state: AnalysisState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    content = getattr(messages[-1], "content", str(messages[-1]))
    return content[-1000:]


def _last_human_message(messages: list[Any]) -> str:
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", "")
        if msg_type == "human" or msg.__class__.__name__.lower().startswith("human"):
            return getattr(msg, "content", str(msg))
    return getattr(messages[-1], "content", str(messages[-1])) if messages else ""


def _dataset_context(datasets: list[dict]) -> str:
    if not datasets:
        return "No local datasets."
    lines = []
    for i, ds in enumerate(datasets):
        lines.append(
            f"- {i}: {ds.get('file_name', 'dataset')} rows={ds.get('num_rows', '?')} "
            f"cols={ds.get('columns', [])}"
        )
    return "\n".join(lines)


def _database_context(sources: list[dict]) -> str:
    if not sources:
        return "No registered database sources."
    lines = []
    for source in sources:
        lines.append(
            f"- alias={source.get('alias')} dialect={source.get('dialect')} "
            f"read_only={source.get('read_only', True)} schemas={source.get('allowed_schemas', [])}"
        )
    return "\n".join(lines)


def _dataset_ref(ds: dict, index: int) -> str:
    return ds.get("file_storage_id") or ds.get("source_ref") or ds.get("file_path") or f"dataset_{index}"


def _risk_controls(database_sources: list[dict]) -> list[str]:
    controls = [
        "LLM plans and explains; SQL/Python executors produce deterministic results.",
        "Reports may cite only persisted evidence.",
        "Failed tasks cannot be marked completed.",
        f"Each task stops after max_retry={MAX_RETRY}.",
    ]
    if database_sources:
        controls.extend(
            [
                "Business database access must use read-only aliases.",
                "SQL must be SELECT-only and schema-scoped before execution.",
                "Query results should be materialized as reproducible local datasets before downstream Python analysis, unless streaming aggregation is explicitly required.",
            ]
        )
    return controls


def _failure_message(failed_tasks: list[dict]) -> str:
    lines = ["Analysis stopped because a task failed after retry limits:"]
    for task in failed_tasks:
        lines.append(
            f"- {task.get('agent')}: {task.get('description')} "
            f"(attempts={task.get('attempt_count', MAX_RETRY)}, reason={task.get('failure_reason', 'unknown')})"
        )
    return "\n".join(lines)

