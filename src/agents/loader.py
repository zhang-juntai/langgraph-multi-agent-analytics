"""
Agent Loader - 动态加载 Agent 定义

从 agents/*/AGENT.md 文件加载 Agent 定义，
支持 YAML frontmatter 解析和验证。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# Agent 定义目录
AGENTS_DIR = Path(__file__).parent.parent.parent / "agents"


@dataclass
class AgentMeta:
    """Agent 元数据"""
    name: str
    display_name: str
    version: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    dependencies: dict[str, Any] = field(default_factory=dict)
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)
    guardrails: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDefinition:
    """完整的 Agent 定义"""
    meta: AgentMeta
    content: str  # Markdown body
    workflow: str = ""
    decision_logic: str = ""
    examples: list[dict] = field(default_factory=list)
    path: Path = None


class AgentLoader:
    """
    Agent 加载器

    从 agents/ 目录加载所有 AGENT.md 文件，
    解析 YAML frontmatter 和 Markdown 内容。
    """

    def __init__(self, agents_dir: Path = None):
        self.agents_dir = agents_dir or AGENTS_DIR
        self._cache: dict[str, AgentDefinition] = {}

    def load_all(self, use_cache: bool = True) -> dict[str, AgentDefinition]:
        """
        加载所有 Agent 定义

        Args:
            use_cache: 是否使用缓存

        Returns:
            Dict[str, AgentDefinition]: Agent 名称到定义的映射
        """
        if use_cache and self._cache:
            return self._cache

        agents = {}

        for agent_dir in self.agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            agent_file = agent_dir / "AGENT.md"
            if not agent_file.exists():
                logger.debug(f"Skipping {agent_dir.name}: no AGENT.md")
                continue

            try:
                definition = self.load(agent_file)
                agents[definition.meta.name] = definition
                logger.info(f"Loaded agent: {definition.meta.name} v{definition.meta.version}")
            except Exception as e:
                logger.error(f"Failed to load agent from {agent_file}: {e}")

        self._cache = agents
        return agents

    def load(self, path: Path) -> AgentDefinition:
        """
        加载单个 Agent 定义

        Args:
            path: AGENT.md 文件路径

        Returns:
            AgentDefinition
        """
        content = path.read_text(encoding="utf-8")

        # 解析 frontmatter
        frontmatter, body = self._parse_frontmatter(content)

        # 构建 meta
        meta = AgentMeta(
            name=frontmatter.get("name", path.parent.name),
            display_name=frontmatter.get("display_name", ""),
            version=frontmatter.get("version", "1.0.0"),
            description=frontmatter.get("description", ""),
            capabilities=frontmatter.get("capabilities", []),
            dependencies=frontmatter.get("dependencies", {}),
            inputs=frontmatter.get("inputs", []),
            outputs=frontmatter.get("outputs", []),
            guardrails=frontmatter.get("guardrails", {}),
        )

        # 解析 body sections
        sections = self._parse_sections(body)

        return AgentDefinition(
            meta=meta,
            content=body,
            workflow=sections.get("workflow", ""),
            decision_logic=sections.get("decision_logic", ""),
            examples=self._parse_examples(sections.get("examples", "")),
            path=path,
        )

    def get(self, name: str) -> Optional[AgentDefinition]:
        """按名称获取 Agent 定义"""
        if not self._cache:
            self.load_all()
        return self._cache.get(name)

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """解析 YAML frontmatter"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            logger.warning("No frontmatter found, using empty meta")
            return {}, content

        try:
            frontmatter = yaml.safe_load(match.group(1))
            body = match.group(2)
            return frontmatter or {}, body
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse frontmatter: {e}")
            return {}, content

    def _parse_sections(self, body: str) -> dict[str, str]:
        """解析 Markdown sections"""
        sections = {}
        current_section = None
        current_content = []

        for line in body.split("\n"):
            # 检测 section 标题 (## Section Name)
            section_match = re.match(r"^##\s+(.+)$", line)
            if section_match:
                # 保存前一个 section
                if current_section:
                    sections[self._normalize_section_name(current_section)] = "\n".join(current_content).strip()

                current_section = section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个 section
        if current_section:
            sections[self._normalize_section_name(current_section)] = "\n".join(current_content).strip()

        return sections

    def _normalize_section_name(self, name: str) -> str:
        """标准化 section 名称"""
        return name.lower().replace(" ", "_").replace("-", "_")

    def _parse_examples(self, content: str) -> list[dict]:
        """解析 Examples section"""
        if not content:
            return []

        examples = []
        # 简单解析：查找 ### Example N 标题
        current_example = None

        for line in content.split("\n"):
            example_match = re.match(r"^###\s+Example\s+(\d+)", line)
            if example_match:
                if current_example:
                    examples.append(current_example)
                current_example = {"number": int(example_match.group(1)), "content": ""}
            elif current_example:
                current_example["content"] += line + "\n"

        if current_example:
            examples.append(current_example)

        return examples


def get_agent_loader() -> AgentLoader:
    """获取全局 Agent 加载器实例"""
    return AgentLoader()


def load_agent(name: str) -> Optional[AgentDefinition]:
    """便捷函数：按名称加载 Agent"""
    return get_agent_loader().get(name)