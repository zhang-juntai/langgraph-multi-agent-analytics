"""
Skills 模块

自动加载内置 Skills。
"""
from src.skills.base import (
    Skill,
    SkillMeta,
    SkillCategory,
    SkillRegistry,
    get_registry,
)
from src.skills.selector import (
    SkillSelector,
    DataContext,
    build_data_context_from_state,
)

# 自动加载内置 Skills
from src.skills.builtin_skills import register_builtin_skills

# 模块导入时自动注册
_builtin_registry = register_builtin_skills()

__all__ = [
    "Skill",
    "SkillMeta",
    "SkillCategory",
    "SkillRegistry",
    "get_registry",
    "SkillSelector",
    "DataContext",
    "build_data_context_from_state",
    "register_builtin_skills",
]
