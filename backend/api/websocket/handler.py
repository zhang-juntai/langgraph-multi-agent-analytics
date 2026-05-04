"""WebSocket chat handler for the P1 data analysis graph."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from src.graph.builder import get_graph_p1
from src.persistence.session_store import SessionStore
from src.persistence.semantic_store import SemanticStore
from src.security.auth_context import AuthError, resolve_auth_context
from src.storage.database_connector import get_registered_database_sources

logger = logging.getLogger(__name__)

AGENT_NAMES = {
    "coordinator_p1": "Coordinator P1",
    "intent_parser": "Intent Parser",
    "context_resolver": "Context Resolver",
    "semantic_retriever": "Semantic Retriever",
    "disambiguation_engine": "Disambiguation Engine",
    "logical_plan_builder": "Logical Plan Builder",
    "policy_checker": "Policy Checker",
    "query_generator": "Query Generator",
    "sql_validator": "SQL Validator",
    "execution_engine": "Execution Engine",
    "data_profiler": "Data Profiler",
    "code_generator": "Code Generator",
    "debugger": "Debugger",
    "visualizer": "Visualizer",
    "report_writer": "Report Writer",
    "chat": "Chat",
    "memory_extractor": "Memory Extractor",
}


def _merge_state(accumulated: dict[str, Any], update: dict[str, Any]) -> None:
    replace_list_keys = {
        "task_queue",
        "completed_tasks",
        "failed_tasks",
        "evidence",
        "validation_results",
        "audit_events",
        "memory_candidates",
    }
    for key, value in update.items():
        if key in accumulated:
            if key in replace_list_keys and isinstance(value, list):
                accumulated[key] = value
            elif isinstance(value, list) and isinstance(accumulated[key], list):
                accumulated[key].extend(value)
            elif isinstance(value, dict) and isinstance(accumulated[key], dict):
                accumulated[key].update(value)
            else:
                accumulated[key] = value
        else:
            accumulated[key] = value


def _figure_urls(figures: list[Any]) -> list[str]:
    urls: list[str] = []
    for fig_path in figures:
        if not isinstance(fig_path, str):
            continue
        path = fig_path.replace("\\", "/")
        if "outputs" in path:
            relative_path = path.split("outputs")[-1].lstrip("/")
            urls.append(f"/static/figures/{relative_path}")
        else:
            urls.append(f"/static/figures/{Path(path).name}")
    return urls


async def websocket_chat(websocket: WebSocket, session_id: str):
    """Serve a single WebSocket chat connection."""
    await websocket.accept()
    logger.info("WebSocket connected: session_id=%s", session_id)

    store = SessionStore()
    semantic_store = SemanticStore()
    graph = get_graph_p1(with_checkpointer=False)

    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if isinstance(message_type, str) and message_type.startswith("semantic."):
                try:
                    auth = _resolve_websocket_auth(websocket, data)
                except AuthError as exc:
                    await websocket.send_json(_semantic_error(message_type, f"Authentication failed: {exc}"))
                    continue
                response = _handle_semantic_message(semantic_store, auth, data)
                await websocket.send_json(response)
                continue

            if message_type != "message":
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unsupported message type: {message_type}",
                })
                continue

            user_message = (data.get("message") or "").strip()
            if not user_message:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message content is required.",
                })
                continue

            if not store.get_session(session_id):
                store.create_session(session_id, f"Session {session_id[:6]}")

            try:
                auth = _resolve_websocket_auth(websocket, data)
            except AuthError as exc:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Authentication failed: {exc}",
                })
                continue
            turn_id = store.create_turn(session_id, user_message, auth.user_id)
            store.add_message(session_id, "user", user_message, turn_id=turn_id)

            state = {
                "session_id": session_id,
                "turn_id": turn_id,
                "messages": [HumanMessage(content=user_message)],
                "datasets": store.get_datasets(session_id),
                "database_sources": get_registered_database_sources(),
                "active_dataset_index": 0,
                "user_id": auth.user_id,
                "team": auth.team,
                "roles": auth.roles,
                "auth_context": auth.to_state(),
                "preferences": data.get("preferences", {}),
                "report_context": data.get("report_context", {}),
                "task_queue": [],
                "completed_tasks": [],
                "failed_tasks": [],
                "evidence": [],
                "validation_results": [],
                "audit_events": [],
                "memory_candidates": [],
                "scheduling_complete": False,
                "max_retry": 3,
            }

            await websocket.send_json({"type": "start", "session_id": session_id, "turn_id": turn_id})

            try:
                accumulated_state: dict[str, Any] = {}
                assistant_chunks: list[str] = []

                async for chunk in graph.astream(
                    state,
                    config={"configurable": {"thread_id": session_id}},
                ):
                    for node_name, node_output in chunk.items():
                        if not isinstance(node_output, dict):
                            continue

                        _merge_state(accumulated_state, node_output)

                        if "task_queue" in node_output or "completed_tasks" in node_output:
                            await websocket.send_json({
                                "type": "task_status",
                                "pending": len(node_output.get("task_queue", [])),
                                "completed": len(node_output.get("completed_tasks", [])),
                                "failed": len(node_output.get("failed_tasks", [])),
                            })

                        if "analysis_plan" in node_output:
                            await websocket.send_json({
                                "type": "plan",
                                "content": node_output["analysis_plan"],
                            })

                        if node_output.get("clarification_required"):
                            await websocket.send_json({
                                "type": "clarification",
                                "questions": node_output.get("clarification_questions", []),
                                "clarification_id": node_output.get("clarification_id", ""),
                            })

                        if "evidence" in node_output:
                            await websocket.send_json({
                                "type": "evidence",
                                "content": node_output.get("evidence", []),
                            })

                        if "validation_results" in node_output:
                            await websocket.send_json({
                                "type": "validation",
                                "content": node_output.get("validation_results", []),
                            })

                        if "validation_failure" in node_output:
                            await websocket.send_json({
                                "type": "validation_failed",
                                "content": _validation_failure_payload(node_output.get("validation_failure", {})),
                            })

                        if "audit_events" in node_output:
                            await websocket.send_json({
                                "type": "audit",
                                "content": node_output.get("audit_events", []),
                            })

                        if "memory_candidates" in node_output:
                            await websocket.send_json({
                                "type": "memory_candidates",
                                "content": node_output.get("memory_candidates", []),
                            })

                        if "supervisor_decision" in node_output:
                            await websocket.send_json({
                                "type": "supervisor_decision",
                                "content": node_output.get("supervisor_decision"),
                            })

                        await websocket.send_json({
                            "type": "agent",
                            "agent": node_name,
                            "agent_display": AGENT_NAMES.get(node_name, node_name),
                        })

                        for skill_call in node_output.get("skill_calls", []) or []:
                            await websocket.send_json({
                                "type": "skill",
                                "skill": skill_call.get("skill", "unknown"),
                                "skill_display": skill_call.get("display_name", skill_call.get("skill", "unknown")),
                            })

                        messages = node_output.get("messages") or []
                        if messages:
                            last_msg = messages[-1]
                            content = getattr(last_msg, "content", "")
                            if content:
                                assistant_chunks.append(content)
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": content,
                                    "agent": node_name,
                                })

                current_code = accumulated_state.get("current_code", "") or accumulated_state.get("code", "")
                if current_code:
                    store.save_artifact(session_id, "code", content=current_code, turn_id=turn_id)
                    await websocket.send_json({"type": "code", "content": current_code})

                report = accumulated_state.get("report", "")
                if report:
                    store.save_artifact(session_id, "report", content=report, turn_id=turn_id)
                    await websocket.send_json({"type": "report", "content": report})

                figures = accumulated_state.get("figures", []) or []
                for fig_path in figures:
                    if isinstance(fig_path, str):
                        store.save_artifact(session_id, "figure", file_path=fig_path, turn_id=turn_id)

                figure_urls = _figure_urls(figures)
                if figure_urls:
                    await websocket.send_json({"type": "figures", "content": figure_urls})

                datasets = accumulated_state.get("datasets")
                if isinstance(datasets, list):
                    store.save_datasets(session_id, datasets)

                assistant_content = report or "\n\n".join(assistant_chunks[-3:])
                if assistant_content:
                    store.add_message(session_id, "assistant", assistant_content, turn_id=turn_id)

                await websocket.send_json({"type": "done", "session_id": session_id, "turn_id": turn_id})

            except Exception as e:
                store.update_turn_status(turn_id, "failed")
                logger.error("Graph execution failed: %s", e, exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Analysis failed: {str(e)}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session_id=%s", session_id)
    except Exception as e:
        logger.error("WebSocket handler failed: %s", e, exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket error: {str(e)}",
            })
        except Exception:
            pass
    finally:
        logger.info("WebSocket closed: session_id=%s", session_id)


def _handle_semantic_message(store: SemanticStore, auth, data: dict[str, Any]) -> dict[str, Any]:
    message_type = data.get("type", "")
    payload = data.get("payload", {}) or {}
    try:
        if message_type == "semantic.list_metrics":
            include_unpublished = _has_admin_role(auth.roles) and bool(payload.get("include_unpublished", False))
            metrics = store.list_metrics(
                domain=payload.get("business_domain"),
                include_unpublished=include_unpublished,
            )
            visible = [
                metric for metric in metrics
                if include_unpublished
                or store.has_permission(auth.roles, "metric.view", "domain", metric.get("business_domain", ""))
                or store.has_permission(auth.roles, "metric.view", "metric", metric.get("semantic_id", ""))
            ]
            return {"type": "semantic.result", "request_type": message_type, "content": visible}

        if message_type == "semantic.get_metric":
            metric = store.get_metric(payload.get("semantic_id", ""), payload.get("version"))
            if not metric:
                return _semantic_error(message_type, "Metric not found.")
            if not (
                _has_admin_role(auth.roles)
                or store.has_permission(auth.roles, "metric.view", "domain", metric.get("business_domain", ""))
                or store.has_permission(auth.roles, "metric.view", "metric", metric.get("semantic_id", ""))
            ):
                return _semantic_error(message_type, "Permission denied.")
            return {"type": "semantic.result", "request_type": message_type, "content": metric}

        if message_type == "semantic.create_metric_draft":
            semantic_id = store.create_metric_draft(payload.get("metric", {}), auth.user_id, auth.roles)
            return {"type": "semantic.result", "request_type": message_type, "content": {"semantic_id": semantic_id}}

        if message_type == "semantic.update_metric_draft":
            store.update_metric_draft(
                payload.get("semantic_id", ""),
                payload.get("patch", {}),
                auth.user_id,
                auth.roles,
            )
            return {"type": "semantic.result", "request_type": message_type, "content": {"updated": True}}

        if message_type == "semantic.request_publish":
            workflow_id = store.request_metric_publish(
                payload.get("semantic_id", ""),
                auth.user_id,
                auth.roles,
                payload.get("approvers", []),
            )
            return {"type": "semantic.result", "request_type": message_type, "content": {"workflow_id": workflow_id}}

        if message_type == "semantic.approve_business":
            store.approve_workflow(payload.get("workflow_id", ""), auth.user_id, auth.roles, "business")
            return {"type": "semantic.result", "request_type": message_type, "content": {"approved": True}}

        if message_type == "semantic.approve_technical":
            store.approve_workflow(payload.get("workflow_id", ""), auth.user_id, auth.roles, "technical")
            return {"type": "semantic.result", "request_type": message_type, "content": {"approved": True}}

        if message_type == "semantic.deprecate_metric":
            store.deprecate_metric(payload.get("semantic_id", ""), auth.user_id, auth.roles)
            return {"type": "semantic.result", "request_type": message_type, "content": {"deprecated": True}}

        if message_type == "semantic.list_audit_logs":
            if not _has_admin_role(auth.roles):
                return _semantic_error(message_type, "Permission denied.")
            logs = store.list_audit_logs(limit=int(payload.get("limit", 50)))
            return {"type": "semantic.result", "request_type": message_type, "content": logs}

        return _semantic_error(message_type, f"Unsupported semantic message type: {message_type}")
    except Exception as exc:
        logger.warning("Semantic governance action failed: %s", exc, exc_info=True)
        return _semantic_error(message_type, str(exc))


def _semantic_error(request_type: str, message: str) -> dict[str, Any]:
    return {"type": "semantic.error", "request_type": request_type, "message": message}


def _validation_failure_payload(failure: dict[str, Any]) -> dict[str, Any]:
    reasons = failure.get("reasons", []) or []
    return {
        "validation_type": failure.get("validation_type", "unknown"),
        "status": failure.get("status", "failed"),
        "summary": failure.get("summary", "Validation failed."),
        "reasons": reasons,
        "failed_checks": failure.get("failed_checks", []),
        "source_alias": failure.get("source_alias", ""),
        "dialect": failure.get("dialect", ""),
        "sql": failure.get("sql", ""),
    }


def _has_admin_role(roles: list[str]) -> bool:
    return "admin" in set(roles)


def _resolve_websocket_auth(websocket: WebSocket, data: dict[str, Any]):
    token = _extract_bearer_token(websocket, data)
    return resolve_auth_context(user_id=data.get("user_id"), token=token)


def _extract_bearer_token(websocket: WebSocket, data: dict[str, Any]) -> str | None:
    explicit_token = data.get("access_token") or data.get("token")
    if explicit_token:
        return str(explicit_token)

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    query_token = websocket.query_params.get("access_token")
    if query_token:
        return query_token
    return None
