"""LangGraph builder for the P1 enterprise data analysis agent."""

from __future__ import annotations

import logging
import inspect
from pathlib import Path
from typing import Any, Callable

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:
    END = "__end__"
    StateGraph = None

from src.agents.chat import chat_node
from src.agents.code_generator import code_generator_node
from src.agents.coordinator_p1 import coordinator_p1_node, route_by_agent_p1
from src.agents.data_profiler import data_profiler_node
from src.agents.debugger import debugger_node
from src.agents.memory_extractor import memory_extractor_node
from src.agents.report_writer import report_writer_node
from src.agents.semantic_pipeline import (
    context_resolver_node,
    disambiguation_engine_node,
    execution_engine_node,
    intent_parser_node,
    logical_plan_builder_node,
    policy_checker_node,
    query_generator_node,
    semantic_retriever_node,
    sql_validator_node,
)
from src.agents.visualizer import visualizer_node
from src.graph.state import AnalysisState
from src.skills.base import get_registry as _get_registry
from src.skills.builtin_skills import register_builtin_skills as _register

logger = logging.getLogger(__name__)

REPLACE_LIST_KEYS = {
    "task_queue",
    "completed_tasks",
    "failed_tasks",
    "evidence",
    "validation_results",
    "audit_events",
    "memory_candidates",
}


def _merge_state(accumulated: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if key in accumulated:
            if key in REPLACE_LIST_KEYS and isinstance(value, list):
                accumulated[key] = value
            elif isinstance(value, list) and isinstance(accumulated[key], list):
                accumulated[key].extend(value)
            elif isinstance(value, dict) and isinstance(accumulated[key], dict):
                accumulated[key].update(value)
            else:
                accumulated[key] = value
        else:
            accumulated[key] = value


class _FallbackCompiledGraph:
    """Small async graph runner used when LangGraph is not installed correctly."""

    def __init__(
        self,
        nodes: dict[str, Callable],
        edges: dict[str, str],
        conditional_edges: dict[str, tuple[Callable, dict[str, str]]],
        entry_point: str,
    ):
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point

    async def astream(
        self,
        input_state: dict[str, Any],
        config: dict[str, Any] | None = None,
        stream_mode: str = "updates",
    ):
        state = dict(input_state)
        current = self.entry_point
        step_count = 0

        while current != END:
            if current not in self.nodes:
                raise ValueError(f"Unknown graph node: {current}")
            if step_count >= 100:
                raise RuntimeError("Fallback graph exceeded 100 steps")

            node = self.nodes[current]
            result = node(state)
            if inspect.isawaitable(result):
                result = await result
            result = result or {}
            _merge_state(state, result)
            yield {current: result}

            if current in self.conditional_edges:
                route_fn, mapping = self.conditional_edges[current]
                route = route_fn(state)
                current = mapping.get(route, route)
            else:
                current = self.edges.get(current, END)

            step_count += 1

    def get_graph(self):
        class _GraphView:
            def __init__(self, nodes: dict[str, Callable]):
                self.nodes = {"__start__": None, "__end__": None, **nodes}

        return _GraphView(self.nodes)


class _FallbackStateGraph:
    def __init__(self, state_schema: Any):
        self.state_schema = state_schema
        self.nodes: dict[str, Callable] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[Callable, dict[str, str]]] = {}
        self.entry_point: str | None = None

    def add_node(self, name: str, func: Callable) -> None:
        self.nodes[name] = func

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        route_fn: Callable,
        mapping: dict[str, str],
    ) -> None:
        self.conditional_edges[source] = (route_fn, mapping)

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def compile(self, **kwargs) -> _FallbackCompiledGraph:
        if not self.entry_point:
            raise ValueError("Fallback graph entry point is not set")
        return _FallbackCompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            entry_point=self.entry_point,
        )


GraphBuilder = StateGraph or _FallbackStateGraph

_register()
_examples_dir = Path(__file__).parent.parent.parent / "skills" / "examples"
if _examples_dir.exists():
    _get_registry().load_from_directory(_examples_dir)


def _get_checkpointer():
    from configs.settings import settings
    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ModuleNotFoundError:
        logger.warning("LangGraph checkpointer unavailable; fallback graph will run without it")
        return None

    if settings.CHECKPOINTER_TYPE.lower() == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            logger.info("Using PostgreSQL checkpointer")
            return PostgresSaver.from_conn_string(settings.POSTGRES_URI)
        except Exception as exc:
            logger.warning("PostgreSQL checkpointer unavailable, using memory: %s", exc)

    return InMemorySaver()


def build_analysis_graph_p1(
    with_checkpointer: bool = True,
    debug: bool = False,
) -> "CompiledStateGraph":
    """Build the P1 coordinator-supervised workflow."""
    graph = GraphBuilder(AnalysisState)

    graph.add_node("coordinator_p1", coordinator_p1_node)
    graph.add_node("intent_parser", intent_parser_node)
    graph.add_node("context_resolver", context_resolver_node)
    graph.add_node("semantic_retriever", semantic_retriever_node)
    graph.add_node("disambiguation_engine", disambiguation_engine_node)
    graph.add_node("logical_plan_builder", logical_plan_builder_node)
    graph.add_node("policy_checker", policy_checker_node)
    graph.add_node("query_generator", query_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("execution_engine", execution_engine_node)
    graph.add_node("data_profiler", data_profiler_node)
    graph.add_node("code_generator", code_generator_node)
    graph.add_node("visualizer", visualizer_node)
    graph.add_node("report_writer", report_writer_node)
    graph.add_node("chat", chat_node)
    graph.add_node("debugger", debugger_node)
    graph.add_node("memory_extractor", memory_extractor_node)

    graph.set_entry_point("coordinator_p1")
    graph.add_conditional_edges(
        "coordinator_p1",
        route_by_agent_p1,
        {
            "coordinator_p1": "coordinator_p1",
            "data_profiler": "data_profiler",
            "intent_parser": "intent_parser",
            "context_resolver": "context_resolver",
            "semantic_retriever": "semantic_retriever",
            "disambiguation_engine": "disambiguation_engine",
            "logical_plan_builder": "logical_plan_builder",
            "policy_checker": "policy_checker",
            "query_generator": "query_generator",
            "sql_validator": "sql_validator",
            "execution_engine": "execution_engine",
            "code_generator": "code_generator",
            "visualizer": "visualizer",
            "report_writer": "report_writer",
            "chat": "chat",
            "debugger": "debugger",
            "memory_extractor": "memory_extractor",
            END: END,
        },
    )

    for node_name in [
        "data_profiler",
        "intent_parser",
        "context_resolver",
        "semantic_retriever",
        "disambiguation_engine",
        "logical_plan_builder",
        "policy_checker",
        "query_generator",
        "sql_validator",
        "execution_engine",
        "code_generator",
        "visualizer",
        "report_writer",
        "chat",
        "debugger",
        "memory_extractor",
    ]:
        graph.add_edge(node_name, "coordinator_p1")

    compile_kwargs: dict[str, Any] = {"debug": debug}
    if with_checkpointer and StateGraph is not None:
        checkpointer = _get_checkpointer()
        if checkpointer is not None:
            compile_kwargs["checkpointer"] = checkpointer

    compiled = graph.compile(**compile_kwargs)
    logger.info("P1 data analysis workflow graph compiled")
    return compiled


_graph_p1_instance = None


def get_graph_p1(force_rebuild: bool = False, **kwargs) -> "CompiledStateGraph":
    global _graph_p1_instance
    if _graph_p1_instance is None or force_rebuild:
        _graph_p1_instance = build_analysis_graph_p1(**kwargs)
    return _graph_p1_instance


def build_analysis_graph(
    with_checkpointer: bool = True,
    debug: bool = False,
) -> "CompiledStateGraph":
    """Compatibility alias. The supported graph is P1."""
    return build_analysis_graph_p1(with_checkpointer=with_checkpointer, debug=debug)


def get_graph(force_rebuild: bool = False, **kwargs) -> "CompiledStateGraph":
    """Compatibility alias. The supported graph is P1."""
    return get_graph_p1(force_rebuild=force_rebuild, **kwargs)
