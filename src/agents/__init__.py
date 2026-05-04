"""
Agents 模块

动态加载 Agent 定义，提供 Agent 基类和注册表。
"""
from src.agents.loader import (
    AgentLoader,
    AgentDefinition,
    AgentMeta,
    get_agent_loader,
    load_agent,
)
from src.agents.base import (
    BaseAgent,
    AgentContext,
    AgentRegistry,
    register_agent,
    get_agent,
    list_agents,
)

__all__ = [
    # Loader
    "AgentLoader",
    "AgentDefinition",
    "AgentMeta",
    "get_agent_loader",
    "load_agent",
    # Base
    "BaseAgent",
    "AgentContext",
    "AgentRegistry",
    "register_agent",
    "get_agent",
    "list_agents",
]