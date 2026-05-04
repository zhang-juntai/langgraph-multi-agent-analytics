"""
Skill 基类和注册体系（v2 — 兼容 Agent Skills 规范）

支持两种 Skill 格式：
1. SKILL.md 格式（行业标准）：
   - 每个 Skill 是一个目录，包含 SKILL.md + 可选附件
   - SKILL.md 使用 YAML frontmatter + Markdown 正文
   - 兼容 langchain-skills / Claude Code / Deep Agents 等生态
   - 可从 GitHub 下载社区 Skill

2. 代码 Skill 格式（内置）：
   - Python 函数生成分析代码模板
   - 适用于内置的数据分析能力

设计思路（对齐 LangChain Agent Skills 规范）：
- Progressive Disclosure：注册时只加载元信息（name + description），
  实际指令在需要时才读取 SKILL.md 完整内容
- 可注册/可版本化/可搜索/可从 GitHub 加载
- Coordinator 通过 Registry 查询可用 Skill 来增强路由决策

Skill 分类：
- analysis: 数据分析类（统计、分布、相关性）
- transform: 数据变换类（清洗、特征工程）
- visualization: 可视化类（折线图、柱状图、热力图）
- modeling: 建模类（回归、分类、预测）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SkillCategory(str, Enum):
    """Skill 分类"""
    ANALYSIS = "analysis"
    TRANSFORM = "transform"
    VISUALIZATION = "visualization"
    MODELING = "modeling"
    UTILITY = "utility"


@dataclass
class SkillMeta:
    """
    Skill 元信息
    描述一个 Skill 的名称、功能、使用方式等。
    """
    name: str                          # 唯一标识符，如 "describe_statistics"
    display_name: str                  # 显示名称，如 "描述性统计分析"
    description: str                   # 功能描述（供 LLM 理解）
    category: SkillCategory            # 分类
    version: str = "1.0.0"            # 版本号
    tags: list[str] = field(default_factory=list)  # 标签，用于搜索
    input_description: str = ""        # 输入说明
    output_description: str = ""       # 输出说明
    code_template: str = ""            # 代码模板（供 CodeGenerator 参考）
    examples: list[str] = field(default_factory=list)  # 使用示例
    # SKILL.md 格式相关
    skill_dir: str = ""               # Skill 目录路径（SKILL.md 所在目录）
    source: str = "builtin"           # 来源：builtin / local / github


@dataclass
class Skill:
    """
    一个完整的 Skill 单元
    包含元信息 + 可执行的代码生成逻辑
    """
    meta: SkillMeta

    # 代码生成函数：接收上下文参数，返回 Python 代码字符串
    generate_code: Callable[..., str] | None = None

    # 直接执行函数（某些 Skill 不需要生成代码，直接返回结果）
    execute: Callable[..., dict[str, Any]] | None = None

    # SKILL.md 完整内容（延迟加载 — Progressive Disclosure）
    _full_instructions: str | None = None

    def __post_init__(self):
        # SKILL.md 格式的 Skill 不需要 generate_code 或 execute
        if (self.generate_code is None
                and self.execute is None
                and not self.meta.skill_dir):
            raise ValueError(
                f"Skill '{self.meta.name}' 必须提供 generate_code、execute 或 skill_dir 之一"
            )

    @property
    def full_instructions(self) -> str:
        """
        获取 Skill 的完整指令文本（Progressive Disclosure）。
        对于 SKILL.md 格式，首次访问时从文件加载。
        对于代码 Skill，返回描述 + 代码模板。
        """
        if self._full_instructions is not None:
            return self._full_instructions

        # 尝试从 SKILL.md 加载
        if self.meta.skill_dir:
            skill_md = Path(self.meta.skill_dir) / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                # 去掉 YAML frontmatter，只返回正文
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        self._full_instructions = parts[2].strip()
                    else:
                        self._full_instructions = content
                else:
                    self._full_instructions = content
                return self._full_instructions

        # 代码 Skill：构造描述文本
        parts = [f"# {self.meta.display_name}", "", self.meta.description]
        if self.meta.code_template:
            parts.extend(["", "## 代码模板", f"```python\n{self.meta.code_template}\n```"])
        self._full_instructions = "\n".join(parts)
        return self._full_instructions


class SkillRegistry:
    """
    Skill 注册表（全局单例）
    负责 Skill 的注册、查找和路由。
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册一个 Skill"""
        name = skill.meta.name
        if name in self._skills:
            existing = self._skills[name]
            logger.info(
                f"Skill 覆盖注册: {name} "
                f"(v{existing.meta.version} → v{skill.meta.version})"
            )
        else:
            logger.info(f"Skill 注册: {name} (v{skill.meta.version})")
        self._skills[name] = skill

    def get(self, name: str) -> Skill | None:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def list_all(self) -> list[SkillMeta]:
        """列出所有已注册 Skill 的元信息"""
        return [s.meta for s in self._skills.values()]

    def list_by_category(self, category: SkillCategory) -> list[SkillMeta]:
        """按分类列出 Skill"""
        return [
            s.meta for s in self._skills.values()
            if s.meta.category == category
        ]

    def search(self, query: str) -> list[SkillMeta]:
        """模糊搜索 Skill（按名称、描述、标签）"""
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            meta = skill.meta
            searchable = (
                f"{meta.name} {meta.display_name} {meta.description} "
                f"{' '.join(meta.tags)}"
            ).lower()
            if query_lower in searchable:
                results.append(meta)
        return results

    def get_skill_descriptions(self) -> str:
        """
        生成所有 Skill 的描述文本（供 Coordinator 使用）
        格式适合注入到 LLM 的系统提示词中。
        只包含元信息（Progressive Disclosure），不加载完整指令。
        """
        if not self._skills:
            return "暂无已注册的 Skill。"

        lines = ["## 可用分析技能\n"]
        by_category: dict[str, list[SkillMeta]] = {}
        for meta in self.list_all():
            cat = meta.category.value
            by_category.setdefault(cat, []).append(meta)

        for category, skills in sorted(by_category.items()):
            lines.append(f"### {category}")
            for s in skills:
                source_tag = f" [{s.source}]" if s.source != "builtin" else ""
                lines.append(
                    f"- **{s.display_name}** (`{s.name}`): "
                    f"{s.description}{source_tag}"
                )
            lines.append("")

        return "\n".join(lines)

    def load_from_directory(self, skills_dir: str | Path) -> int:
        """
        从目录批量加载 SKILL.md 格式的 Skill。

        目录结构：
        skills_dir/
        ├── web-research/
        │   ├── SKILL.md
        │   └── helper.py
        ├── data-cleaning/
        │   └── SKILL.md
        └── ...

        Returns:
            加载的 Skill 数量
        """
        skills_dir = Path(skills_dir)
        if not skills_dir.exists():
            logger.warning(f"Skill 目录不存在: {skills_dir}")
            return 0

        loaded = 0
        for skill_path in sorted(skills_dir.iterdir()):
            if not skill_path.is_dir():
                continue
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill = _parse_skill_md(skill_md)
                if skill:
                    self.register(skill)
                    loaded += 1
            except Exception as e:
                logger.error(f"加载 Skill 失败 [{skill_path.name}]: {e}")

        logger.info(f"从 {skills_dir} 加载了 {loaded} 个 SKILL.md Skill")
        return loaded

    @property
    def count(self) -> int:
        return len(self._skills)


def _parse_skill_md(skill_md_path: Path) -> Skill | None:
    """
    解析 SKILL.md 文件为 Skill 对象。

    SKILL.md 格式：
    ---
    name: skill-name
    description: What the skill does
    version: 1.0.0
    category: analysis
    tags: [tag1, tag2]
    code_template_file: generate.py  # 可选
    ---
    # Skill Title

    Full instructions here...
    """
    content = skill_md_path.read_text(encoding="utf-8")

    # 解析 YAML frontmatter
    if not content.startswith("---"):
        logger.warning(f"SKILL.md 缺少 YAML frontmatter: {skill_md_path}")
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        logger.warning(f"SKILL.md frontmatter 格式错误: {skill_md_path}")
        return None

    frontmatter = parts[1].strip()

    # 简单 YAML 解析（避免引入 pyyaml 依赖）
    meta_dict: dict[str, Any] = {}
    for line in frontmatter.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # 处理列表格式 [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                value = [
                    v.strip().strip("\"'")
                    for v in value[1:-1].split(",")
                    if v.strip()
                ]
            # 处理引号
            elif value.startswith(("'", '"')) and value.endswith(("'", '"')):
                value = value[1:-1]
            meta_dict[key] = value

    name = meta_dict.get("name", skill_md_path.parent.name)
    description = meta_dict.get("description", "")
    version = meta_dict.get("version", "1.0.0")
    category_str = meta_dict.get("category", "utility")
    tags = meta_dict.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    # 映射 category
    try:
        category = SkillCategory(category_str)
    except ValueError:
        category = SkillCategory.UTILITY

    display_name = meta_dict.get("display_name", name.replace("-", " ").title())

    # 处理 code_template_file - 动态导入 generate_code
    generate_code_func = None
    code_template_file = meta_dict.get("code_template_file")
    if code_template_file:
        try:
            skill_dir = skill_md_path.parent
            code_file_path = skill_dir / code_template_file
            if code_file_path.exists():
                # 动态导入 generate_code 函数
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"{name}_generate",
                    code_file_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "generate_code"):
                        generate_code_func = module.generate_code
                        logger.info(f"成功导入 {name} 的 generate_code 函数")
                    else:
                        logger.warning(f"{code_file_path} 中没有找到 generate_code 函数")
                else:
                    logger.warning(f"无法加载 {code_file_path}")
            else:
                logger.warning(f"代码文件不存在: {code_file_path}")
        except Exception as e:
            logger.error(f"导入 {name} 的代码生成函数失败: {e}")

    meta = SkillMeta(
        name=name,
        display_name=display_name,
        description=description,
        category=category,
        version=version,
        tags=tags,
        skill_dir=str(skill_md_path.parent),
        source="local",
    )

    return Skill(meta=meta, generate_code=generate_code_func)


# ============================================================
# 全局单例
# ============================================================
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """获取全局 Skill 注册表"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
