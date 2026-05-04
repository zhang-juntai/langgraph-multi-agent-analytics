"""
Skill 选择器 - 智能动态发现与选择

核心功能：
1. 根据用户意图关键词匹配 Skill
2. 根据数据特征（列类型、行数等）筛选 Skill
3. 对匹配的 Skill 进行排序
4. 支持自定义匹配规则

设计原则：
- 不硬编码 Skill 名称
- 新增 Skill 自动参与匹配
- 可扩展的匹配逻辑
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from src.skills.base import Skill, SkillCategory, SkillRegistry, get_registry

logger = logging.getLogger(__name__)


@dataclass
class DataContext:
    """数据上下文 - 描述当前数据集的特征"""
    row_count: int = 0
    column_count: int = 0
    has_numeric: bool = False
    has_categorical: bool = False
    has_datetime: bool = False
    column_names: list[str] = None
    numeric_columns: list[str] = None
    categorical_columns: list[str] = None
    missing_values: bool = False
    duplicate_rows: bool = False

    def __post_init__(self):
        if self.column_names is None:
            self.column_names = []
        if self.numeric_columns is None:
            self.numeric_columns = []
        if self.categorical_columns is None:
            self.categorical_columns = []


# 意图关键词到 Skill 能力的映射
INTENT_KEYWORDS = {
    # 分析类
    "analysis": {
        "keywords": ["分析", "统计", "概览", "探索", "analysis", "statistics", "overview", "profile"],
        "capabilities": ["describe", "statistics", "distribution", "correlation"],
    },
    # 排名/排序
    "ranking": {
        "keywords": ["排名", "排序", "top", "rank", "order", "最高", "最低", "最大", "最小"],
        "capabilities": ["rank", "sort", "top", "group_by", "count"],
    },
    # 占比/比例
    "proportion": {
        "keywords": ["占比", "比例", "百分比", "分布", "proportion", "percentage", "ratio", "share"],
        "capabilities": ["percentage", "ratio", "distribution", "group_by"],
    },
    # 对比
    "comparison": {
        "keywords": ["对比", "比较", "差异", "compare", "difference", "vs", "versus"],
        "capabilities": ["compare", "group_by", "aggregate"],
    },
    # 趋势
    "trend": {
        "keywords": ["趋势", "变化", "增长", "下降", "trend", "growth", "change", "time"],
        "capabilities": ["trend", "time_series", "line"],
    },
    # 可视化
    "visualization": {
        "keywords": ["图表", "可视化", "画图", "plot", "chart", "visual", "展示"],
        "capabilities": ["plot", "chart", "visualize", "figure"],
    },
    # 数据加载
    "load": {
        "keywords": ["加载", "上传", "导入", "读取", "load", "upload", "import", "read"],
        "capabilities": ["load", "parse", "read"],
    },
    # 数据清洗
    "clean": {
        "keywords": ["清洗", "处理", "缺失", "空值", "clean", "missing", "null", "na"],
        "capabilities": ["clean", "transform", "fill", "drop"],
    },
    # 异常检测
    "outlier": {
        "keywords": ["异常", "离群", "outlier", "anomaly", "异常值"],
        "capabilities": ["outlier", "anomaly", "detect"],
    },
    # 分类分析
    "categorical": {
        "keywords": ["分类", "分组", "聚合", "category", "group", "aggregate", "按"],
        "capabilities": ["group_by", "categorical", "count", "aggregate"],
    },
}


class SkillSelector:
    """
    智能 Skill 选择器

    根据用户意图和数据上下文，从 Skill Registry 中选择最合适的 Skills。
    """

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or get_registry()

    def select_skills_for_intent(
        self,
        intent: str,
        data_context: DataContext | dict[str, Any] | None = None,
        max_skills: int = 5,
    ) -> list[Skill]:
        """
        根据意图和数据上下文选择最合适的 Skills

        Args:
            intent: 用户意图描述（如 "各大区订单数排名"）
            data_context: 数据上下文（可选）
            max_skills: 最多返回的 Skill 数量

        Returns:
            排序后的 Skill 列表
        """
        if isinstance(data_context, dict):
            data_context = DataContext(**data_context)

        # 1. 获取所有可用 Skills
        all_skills = [self.registry.get(name) for name in self.registry._skills.keys()]
        all_skills = [s for s in all_skills if s is not None]

        # 2. 计算每个 Skill 的匹配分数
        scored_skills = []
        for skill in all_skills:
            score = self._calculate_relevance_score(skill, intent, data_context)
            if score > 0:
                scored_skills.append((skill, score))

        # 3. 按分数排序
        scored_skills.sort(key=lambda x: x[1], reverse=True)

        # 4. 返回前 N 个
        selected = [s[0] for s in scored_skills[:max_skills]]

        logger.info(
            f"Skill 选择: intent='{intent[:30]}...' -> "
            f"{len(selected)} skills: {[s.meta.name for s in selected]}"
        )

        return selected

    def _calculate_relevance_score(
        self,
        skill: Skill,
        intent: str,
        data_context: DataContext | None,
    ) -> float:
        """
        计算 Skill 与意图的相关性分数

        分数组成：
        - 意图关键词匹配: 0-50 分
        - 数据上下文匹配: 0-30 分
        - 类别优先级: 0-20 分
        """
        score = 0.0
        intent_lower = intent.lower()
        meta = skill.meta

        # 1. 意图关键词匹配 (0-50)
        intent_score = self._match_intent_keywords(intent_lower, meta)
        score += intent_score

        # 2. 数据上下文匹配 (0-30)
        if data_context:
            context_score = self._match_data_context(skill, data_context)
            score += context_score

        # 3. 类别优先级 (0-20)
        category_score = self._category_priority(meta.category, intent_lower)
        score += category_score

        return score

    def _match_intent_keywords(self, intent: str, meta) -> float:
        """基于意图关键词匹配"""
        score = 0.0

        # 检查意图类型
        for intent_type, config in INTENT_KEYWORDS.items():
            keywords = config["keywords"]
            capabilities = config["capabilities"]

            # 检查意图是否包含关键词
            keyword_match = any(kw in intent for kw in keywords)
            if not keyword_match:
                continue

            # 检查 Skill 是否有对应能力
            skill_tags_lower = [t.lower() for t in meta.tags]
            skill_desc_lower = meta.description.lower()

            for cap in capabilities:
                if cap in skill_tags_lower or cap in skill_desc_lower:
                    score += 15  # 每个能力匹配得 15 分
                    break

            # 直接检查 Skill 名称和描述
            if any(kw in meta.name.lower() for kw in keywords):
                score += 10
            if any(kw in meta.display_name.lower() for kw in keywords):
                score += 10

        # 检查标签直接匹配
        for tag in meta.tags:
            if tag.lower() in intent:
                score += 5

        return min(score, 50)  # 上限 50 分

    def _match_data_context(self, skill: Skill, ctx: DataContext) -> float:
        """基于数据上下文匹配"""
        score = 0.0
        meta = skill.meta

        # 检查数据要求
        # 这里可以扩展读取 SKILL.md 中的 data_requirements

        # 如果 Skill 需要数值列，检查是否有
        if "statistics" in meta.name or "correlation" in meta.name or "distribution" in meta.name:
            if ctx.has_numeric:
                score += 15
            else:
                score -= 10  # 惩罚：缺少所需数据类型

        # 如果 Skill 是分类分析，检查是否有分类列
        if "categorical" in meta.name or "category" in meta.tags:
            if ctx.has_categorical:
                score += 15
            else:
                score -= 5

        # 如果 Skill 是数据加载，但数据已存在
        if meta.category == SkillCategory.UTILITY and "load" in meta.name:
            if ctx.row_count > 0:
                score -= 20  # 数据已加载，不需要再加载

        return max(score, 0)  # 不给负分

    def _category_priority(self, category: SkillCategory, intent: str) -> float:
        """基于类别优先级给分"""
        # 分析类意图优先分析类 Skill
        if any(kw in intent for kw in ["分析", "统计", "analysis", "statistics"]):
            if category == SkillCategory.ANALYSIS:
                return 20

        # 可视化意图优先可视化 Skill
        if any(kw in intent for kw in ["图表", "可视化", "plot", "chart"]):
            if category == SkillCategory.VISUALIZATION:
                return 20

        # 加载意图优先工具类 Skill
        if any(kw in intent for kw in ["加载", "上传", "load", "upload"]):
            if category == SkillCategory.UTILITY:
                return 20

        return 10  # 默认 10 分

    def get_analysis_skills(self) -> list[Skill]:
        """获取所有分析类 Skills"""
        return [
            self.registry.get(name)
            for name in self.registry._skills.keys()
            if self.registry.get(name)
            and self.registry.get(name).meta.category == SkillCategory.ANALYSIS
        ]

    def get_skills_by_category(self, category: SkillCategory) -> list[Skill]:
        """按类别获取 Skills"""
        return [
            self.registry.get(name)
            for name in self.registry._skills.keys()
            if self.registry.get(name)
            and self.registry.get(name).meta.category == category
        ]


def build_data_context_from_state(state: dict) -> DataContext:
    """
    从 AnalysisState 构建 DataContext

    Args:
        state: AnalysisState 字典

    Returns:
        DataContext 对象
    """
    datasets = state.get("datasets", [])
    active_idx = state.get("active_dataset_index", 0)

    if not datasets:
        return DataContext()

    # 获取活跃数据集
    active_ds = datasets[min(active_idx, len(datasets) - 1)]

    # 提取数据特征
    ctx = DataContext(
        row_count=active_ds.get("row_count", 0),
        column_count=active_ds.get("column_count", 0),
        column_names=active_ds.get("columns", []),
    )

    # 从 dtypes 推断列类型
    dtypes = active_ds.get("dtypes", {})
    for col, dtype in dtypes.items():
        dtype_lower = dtype.lower()
        if "int" in dtype_lower or "float" in dtype_lower:
            ctx.has_numeric = True
            ctx.numeric_columns.append(col)
        elif "object" in dtype_lower or "category" in dtype_lower:
            ctx.has_categorical = True
            ctx.categorical_columns.append(col)
        elif "datetime" in dtype_lower or "date" in dtype_lower:
            ctx.has_datetime = True

    return ctx
