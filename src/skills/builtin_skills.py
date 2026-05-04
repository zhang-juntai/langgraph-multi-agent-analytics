"""
内置技能加载器

从 skills/builtin/ 目录加载所有内置技能。
每个技能是一个独立的目录，包含 SKILL.md 和 generate.py 文件。
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.skills.base import SkillRegistry, get_registry

logger = logging.getLogger(__name__)


def register_builtin_skills(registry: SkillRegistry | None = None) -> SkillRegistry:
    """
    注册所有内置技能到注册表

    从 skills/builtin/ 目录加载所有技能，每个技能目录应包含：
    - SKILL.md: 技能描述文档
    - generate.py: 代码生成函数（可选）

    Args:
        registry: 技能注册表，如果为 None 则使用全局注册表

    Returns:
        技能注册表实例
    """
    reg = registry or get_registry()

    # 获取 builtin 目录路径
    builtin_dir = Path(__file__).parent.parent.parent / "skills" / "builtin"

    if not builtin_dir.exists():
        logger.warning(f"内置技能目录不存在: {builtin_dir}")
        return reg

    # 使用注册表的 load_from_directory 方法加载所有技能
    loaded = reg.load_from_directory(builtin_dir)

    if loaded > 0:
        logger.info(f"已从 {builtin_dir} 加载 {loaded} 个内置技能")
    else:
        logger.warning(f"未能从 {builtin_dir} 加载任何内置技能")

    return reg


# 模块导入时自动注册
register_builtin_skills()
