"""
新技能体系测试

测试从目录加载的技能（SKILL.md + generate.py 格式）
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.skills.base import get_registry, SkillRegistry
from src.skills.builtin_skills import register_builtin_skills


class TestBuiltinSkillsFromDirectory:
    """测试从目录加载的内置技能"""

    def test_all_builtin_skills_loaded(self):
        """所有5个内置技能应该从目录成功加载"""
        registry = SkillRegistry()
        register_builtin_skills(registry)

        # 验证所有内置技能都已加载
        expected_skills = [
            "describe_statistics",
            "distribution_analysis",
            "correlation_analysis",
            "categorical_analysis",
            "outlier_detection",
        ]

        for skill_name in expected_skills:
            skill = registry.get(skill_name)
            assert skill is not None, f"{skill_name} 未加载"
            assert skill.generate_code is not None, f"{skill_name} 缺少 generate_code 函数"

    def test_describe_statistics_code_generation(self):
        """测试描述性统计技能的代码生成"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("describe_statistics")

        code = skill.generate_code()
        assert len(code) > 0
        assert "describe()" in code
        assert "isnull()" in code
        assert "nunique()" in code

    def test_distribution_analysis_code_generation(self):
        """测试分布分析技能的代码生成"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("distribution_analysis")

        code = skill.generate_code()
        assert len(code) > 0
        assert "hist(" in code
        assert "skew()" in code
        assert "kurtosis()" in code

    def test_correlation_analysis_code_generation(self):
        """测试相关性分析技能的代码生成"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("correlation_analysis")

        code = skill.generate_code()
        assert len(code) > 0
        assert "corr()" in code
        assert "heatmap" in code

    def test_categorical_analysis_code_generation(self):
        """测试分类变量分析技能的代码生成"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("categorical_analysis")

        code = skill.generate_code()
        assert len(code) > 0
        assert "value_counts()" in code
        assert "bar" in code

    def test_outlier_detection_code_generation(self):
        """测试异常值检测技能的代码生成"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("outlier_detection")

        code = skill.generate_code()
        assert len(code) > 0
        # quantile 可能在不同行，使用更宽松的检查
        assert "quantile" in code or ".quantile" in code
        assert "boxplot" in code


class TestSkillMetadata:
    """测试技能元信息"""

    def test_skill_metadata_from_skill_md(self):
        """技能元信息应该从 SKILL.md 正确解析"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("describe_statistics")

        assert skill.meta.name == "describe_statistics"
        assert skill.meta.display_name == "描述性统计分析"
        assert skill.meta.category.value == "analysis"
        assert "统计" in skill.meta.tags
        assert skill.meta.version == "2.0.0"

    def test_skill_source_is_local(self):
        """技能来源应该标记为 local"""
        registry = SkillRegistry()
        register_builtin_skills(registry)
        skill = registry.get("describe_statistics")

        assert skill.meta.source == "local"
        # 检查路径包含关键部分（处理完整路径）
        assert "describe_statistics" in skill.meta.skill_dir
        assert "skills" in skill.meta.skill_dir
        assert "builtin" in skill.meta.skill_dir


class TestCommunitySkills:
    """测试从 GitHub 下载的社区技能"""

    def test_anthropics_skills_loaded(self):
        """anthropics 技能应该能成功加载"""
        registry = SkillRegistry()
        register_builtin_skills(registry)

        loaded = registry.load_from_directory(ROOT / "skills" / "anthropics")
        assert loaded >= 1  # 至少加载一个技能

        # 验证 docx 技能已加载
        docx_skill = registry.get("docx")
        assert docx_skill is not None

    def test_hoodini_skills_loaded(self):
        """hoodini 技能应该能成功加载"""
        registry = SkillRegistry()
        register_builtin_skills(registry)

        loaded = registry.load_from_directory(ROOT / "skills" / "hoodini")
        assert loaded >= 1  # 至少加载一个技能

        # 验证 analytics-metrics 技能已加载
        analytics_skill = registry.get("analytics-metrics")
        assert analytics_skill is not None


class TestSkillIntegration:
    """集成测试"""

    def test_full_skill_loading_pipeline(self):
        """测试完整的技能加载流程"""
        registry = SkillRegistry()

        # 1. 加载内置技能
        register_builtin_skills(registry)
        builtin_count = registry.count
        assert builtin_count == 5

        # 2. 加载 anthropics 技能
        anthropic_count = registry.load_from_directory(ROOT / "skills" / "anthropics")
        assert anthropic_count >= 1

        # 3. 加载 hoodini 技能
        hoodini_count = registry.load_from_directory(ROOT / "skills" / "hoodini")
        assert hoodini_count >= 1

        # 4. 验证总技能数
        total_count = registry.count
        assert total_count == builtin_count + anthropic_count + hoodini_count

    def test_skill_descriptions_generation(self):
        """测试技能描述生成（用于 LLM 提示词）"""
        registry = SkillRegistry()
        register_builtin_skills(registry)

        descriptions = registry.get_skill_descriptions()
        assert len(descriptions) > 0
        assert "describe_statistics" in descriptions
        assert "distribution_analysis" in descriptions
