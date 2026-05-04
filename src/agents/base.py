"""
Base Agent - 所有 Agent 的基类

提供从 AGENT.md 加载定义和执行工作流的能力。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.agents.loader import AgentDefinition, AgentLoader
from src.graph.state import AnalysisState

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    state: AnalysisState
    agent_def: AgentDefinition
    mcp_client: Any = None  # MCPClient
    skill_registry: Any = None  # SkillRegistry
    metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 继承此类，从 AGENT.md 加载定义。
    """

    # Agent 名称（子类必须定义）
    name: ClassVar[str]

    # Agent 定义（从 AGENT.md 加载）
    _definition: AgentDefinition | None = None

    @classmethod
    def get_definition(cls) -> AgentDefinition:
        """获取 Agent 定义（从 AGENT.md 加载）"""
        if cls._definition is None:
            loader = AgentLoader()
            cls._definition = loader.get(cls.name)
            if cls._definition is None:
                raise ValueError(f"Agent definition not found: {cls.name}")
        return cls._definition

    @classmethod
    def get_meta(cls):
        """获取 Agent 元数据"""
        return cls.get_definition().meta

    def __init__(self, mcp_client=None, skill_registry=None):
        """
        初始化 Agent

        Args:
            mcp_client: MCP 客户端实例
            skill_registry: Skill 注册表实例
        """
        self.mcp_client = mcp_client
        self.skill_registry = skill_registry
        self._definition = self.get_definition()
        self.logger = logging.getLogger(f"agent.{self.name}")

    async def execute(self, state: AnalysisState) -> dict[str, Any]:
        """
        执行 Agent

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        context = AgentContext(
            state=state,
            agent_def=self._definition,
            mcp_client=self.mcp_client,
            skill_registry=self.skill_registry,
        )

        # 检查 guardrails
        guardrails = self._definition.meta.guardrails
        if guardrails:
            timeout = guardrails.get("timeout_seconds", 120)
            max_retries = guardrails.get("max_retries", 3)
            # 应用 guardrails...

        try:
            result = await self.run(context)
            return result
        except Exception as e:
            self.logger.error(f"Agent {self.name} failed: {e}")
            return {
                "error": str(e),
                "agent": self.name,
            }

    @abstractmethod
    async def run(self, context: AgentContext) -> dict[str, Any]:
        """
        执行 Agent 核心逻辑（子类实现）

        Args:
            context: 执行上下文

        Returns:
            状态更新字典
        """
        pass

    def get_guardrail(self, key: str, default: Any = None) -> Any:
        """获取 guardrail 配置"""
        return self._definition.meta.guardrails.get(key, default)

    def get_capability(self, capability: str) -> bool:
        """检查是否具有某能力"""
        return capability in self._definition.meta.capabilities

    def __repr__(self) -> str:
        meta = self._definition.meta
        return f"Agent({self.name}: {meta.display_name} v{meta.version})"


class AgentRegistry:
    """
    Agent 注册表

    管理所有 Agent 实例。
    """

    def __init__(self):
        self._agents: dict[str, type[BaseAgent]] = {}
        self._instances: dict[str, BaseAgent] = {}

    def register(self, agent_class: type[BaseAgent]) -> None:
        """注册 Agent 类"""
        self._agents[agent_class.name] = agent_class
        logger.info(f"Registered agent: {agent_class.name}")

    def get(self, name: str, **kwargs) -> BaseAgent:
        """获取 Agent 实例"""
        if name not in self._instances:
            if name not in self._agents:
                raise ValueError(f"Unknown agent: {name}")
            self._instances[name] = self._agents[name](**kwargs)
        return self._instances[name]

    def list_agents(self) -> list[str]:
        """列出所有已注册的 Agent"""
        return list(self._agents.keys())


# 全局注册表
_registry = AgentRegistry()


def register_agent(agent_class: type[BaseAgent]) -> type[BaseAgent]:
    """装饰器：注册 Agent"""
    _registry.register(agent_class)
    return agent_class


def get_agent(name: str, **kwargs) -> BaseAgent:
    """获取 Agent 实例"""
    return _registry.get(name, **kwargs)


def list_agents() -> list[str]:
    """列出所有 Agent"""
    return _registry.list_agents()