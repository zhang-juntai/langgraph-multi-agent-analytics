"""
Skill 验证器 - 数据要求检查

功能：
1. 检查 Skill 是否适用于当前数据
2. 验证数据要求（行数、列类型等）
3. 提供清晰的错误信息
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.skills.base import Skill, SkillCategory
from src.skills.selector import DataContext

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    can_execute: bool
    reason: str
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SkillValidator:
    """
    Skill 验证器

    检查 Skill 是否可以在当前数据上下文中执行。
    """

    def can_execute(
        self,
        skill: Skill,
        data_context: DataContext | dict[str, Any],
    ) -> ValidationResult:
        """
        检查 Skill 是否可以执行

        Args:
            skill: 要检查的 Skill
            data_context: 数据上下文

        Returns:
            ValidationResult 包含是否可执行和原因
        """
        if isinstance(data_context, dict):
            data_context = DataContext(**data_context)

        meta = skill.meta
        warnings = []

        # 1. 检查数据是否为空
        if data_context.row_count == 0:
            return ValidationResult(
                can_execute=False,
                reason="数据为空，无法执行分析",
                warnings=["请先加载数据"]
            )

        # 2. 检查数值列要求
        if meta.category == SkillCategory.ANALYSIS:
            if "statistics" in meta.name or "correlation" in meta.name or "distribution" in meta.name:
                if not data_context.has_numeric:
                    return ValidationResult(
                        can_execute=False,
                        reason=f"Skill '{meta.display_name}' 需要数值列，但当前数据没有数值列",
                        warnings=["检查是否有数值列被误识别为字符串"]
                    )

        # 3. 检查分类列要求
        if "categorical" in meta.name or "category" in meta.tags:
            if not data_context.has_categorical:
                warnings.append("没有分类列，分析结果可能有限")

        # 4. 检查最小行数
        min_rows = getattr(meta, 'min_rows', 1)
        if data_context.row_count < min_rows:
            return ValidationResult(
                can_execute=False,
                reason=f"数据行数不足：需要至少 {min_rows} 行，当前 {data_context.row_count} 行"
            )

        # 5. 可执行
        return ValidationResult(
            can_execute=True,
            reason="验证通过",
            warnings=warnings
        )

    def validate_batch(
        self,
        skills: list[Skill],
        data_context: DataContext,
    ) -> tuple[list[Skill], list[tuple[Skill, str]]]:
        """
        批量验证 Skills

        Args:
            skills: 要验证的 Skill 列表
            data_context: 数据上下文

        Returns:
            (可执行的Skills, 不可执行的Skills及原因)
        """
        executable = []
        rejected = []

        for skill in skills:
            result = self.can_execute(skill, data_context)
            if result.can_execute:
                executable.append(skill)
                if result.warnings:
                    logger.info(f"Skill {skill.meta.name} 警告: {result.warnings}")
            else:
                rejected.append((skill, result.reason))
                logger.debug(f"Skill {skill.meta.name} 被拒绝: {result.reason}")

        return executable, rejected


def validate_skill_for_data(
    skill: Skill,
    state: dict,
) -> ValidationResult:
    """
    便捷函数：验证 Skill 是否适用于 State 中的数据

    Args:
        skill: 要验证的 Skill
        state: AnalysisState

    Returns:
        ValidationResult
    """
    from src.skills.selector import build_data_context_from_state

    data_context = build_data_context_from_state(state)
    validator = SkillValidator()
    return validator.can_execute(skill, data_context)
