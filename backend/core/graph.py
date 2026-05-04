"""Compatibility wrapper for the P1 analysis graph."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_graph(with_checkpointer: bool = True):
    """Return the P1 graph."""
    from src.graph.builder import get_graph_p1

    return get_graph_p1(with_checkpointer=with_checkpointer)
