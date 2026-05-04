"""Conversational fallback agent."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from src.graph.state import AnalysisState
from src.utils.llm import get_llm

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are the Chat agent in an enterprise Data Agent.

Answer conversational requests directly. For data analysis, do not invent
numbers or conclusions; those must come from persisted execution evidence.
"""


def chat_node(state: AnalysisState) -> dict[str, Any]:
    """Run the conversational agent with a graceful LLM fallback."""

    try:
        llm = get_llm()
        messages = state.get("messages", [])
        recent = messages[-10:] if len(messages) > 10 else messages
        response = llm.invoke([SystemMessage(content=CHAT_SYSTEM_PROMPT), *recent])
        return {
            "messages": [response],
            "code_result": {
                "success": True,
                "code": "",
                "stdout": "Chat response generated.",
                "stderr": "",
                "figures": [],
            },
        }
    except Exception as exc:
        logger.warning("Chat agent fallback activated: %s", exc)
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I can continue the workflow, but the chat model is not configured. "
                        f"Reason: {str(exc)[:200]}"
                    )
                )
            ],
            "code_result": {
                "success": True,
                "code": "",
                "stdout": "Chat fallback response generated.",
                "stderr": "",
                "figures": [],
            },
        }


def placeholder_node(agent_name: str):
    """Return a minimal placeholder node for legacy imports."""

    def _node(state: AnalysisState) -> dict[str, Any]:
        return {
            "messages": [AIMessage(content=f"`{agent_name}` is not implemented.")],
            "code_result": {
                "success": True,
                "code": "",
                "stdout": f"{agent_name} placeholder completed.",
                "stderr": "",
                "figures": [],
            },
        }

    _node.__name__ = agent_name
    return _node
