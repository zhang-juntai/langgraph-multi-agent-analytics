import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.builder import build_analysis_graph, build_analysis_graph_p1, get_graph


def test_p1_graph_compiles_without_checkpointer():
    graph = build_analysis_graph_p1(with_checkpointer=False)
    assert graph is not None


def test_compat_builder_returns_p1_graph():
    graph = build_analysis_graph(with_checkpointer=False)
    graph_dict = graph.get_graph()
    assert "coordinator_p1" in graph_dict.nodes
    assert "coordinator" not in graph_dict.nodes
    assert "data_parser" not in graph_dict.nodes


def test_p1_graph_has_required_nodes():
    graph = get_graph(force_rebuild=True, with_checkpointer=False)
    graph_dict = graph.get_graph()
    node_ids = set(graph_dict.nodes.keys())

    expected_nodes = {
        "__start__",
        "__end__",
        "coordinator_p1",
        "intent_parser",
        "context_resolver",
        "semantic_retriever",
        "disambiguation_engine",
        "logical_plan_builder",
        "policy_checker",
        "query_generator",
        "sql_validator",
        "execution_engine",
        "data_profiler",
        "code_generator",
        "debugger",
        "visualizer",
        "report_writer",
        "chat",
        "memory_extractor",
    }

    assert expected_nodes.issubset(node_ids)
