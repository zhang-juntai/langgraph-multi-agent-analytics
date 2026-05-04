"""
Skill 注册体系测试
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.skills.base import (
    Skill, SkillMeta, SkillCategory, SkillRegistry, get_registry,
    _parse_skill_md,
)
from src.skills.builtin_skills import register_builtin_skills


class TestSkillRegistry:
    """测试 Skill 注册表"""

    def test_register_and_get(self):
        """注册后应能获取 Skill"""
        registry = SkillRegistry()
        skill = Skill(
            meta=SkillMeta(
                name="test_skill",
                display_name="测试技能",
                description="测试用",
                category=SkillCategory.UTILITY,
            ),
            generate_code=lambda: "print('test')",
        )
        registry.register(skill)
        assert registry.get("test_skill") is not None
        assert registry.get("test_skill").meta.name == "test_skill"

    def test_get_nonexistent(self):
        """获取不存在的 Skill 应返回 None"""
        registry = SkillRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        """应能列出所有 Skill"""
        registry = SkillRegistry()
        for i in range(3):
            registry.register(Skill(
                meta=SkillMeta(
                    name=f"skill_{i}",
                    display_name=f"技能{i}",
                    description=f"描述{i}",
                    category=SkillCategory.ANALYSIS,
                ),
                generate_code=lambda: "pass",
            ))
        assert len(registry.list_all()) == 3

    def test_list_by_category(self):
        """应能按分类过滤"""
        registry = SkillRegistry()
        registry.register(Skill(
            meta=SkillMeta(name="a", display_name="A", description="", category=SkillCategory.ANALYSIS),
            generate_code=lambda: "pass",
        ))
        registry.register(Skill(
            meta=SkillMeta(name="v", display_name="V", description="", category=SkillCategory.VISUALIZATION),
            generate_code=lambda: "pass",
        ))
        assert len(registry.list_by_category(SkillCategory.ANALYSIS)) == 1
        assert len(registry.list_by_category(SkillCategory.VISUALIZATION)) == 1

    def test_search(self):
        """应能模糊搜索"""
        registry = SkillRegistry()
        registry.register(Skill(
            meta=SkillMeta(
                name="correlation_analysis",
                display_name="相关性分析",
                description="计算Pearson相关系数",
                category=SkillCategory.ANALYSIS,
                tags=["相关性", "pearson"],
            ),
            generate_code=lambda: "pass",
        ))
        assert len(registry.search("相关性")) == 1
        assert len(registry.search("pearson")) == 1
        assert len(registry.search("不存在")) == 0

    def test_version_override(self):
        """同名 Skill 注册应覆盖旧版"""
        registry = SkillRegistry()
        skill_v1 = Skill(
            meta=SkillMeta(name="s", display_name="S", description="v1", category=SkillCategory.UTILITY, version="1.0"),
            generate_code=lambda: "v1",
        )
        skill_v2 = Skill(
            meta=SkillMeta(name="s", display_name="S", description="v2", category=SkillCategory.UTILITY, version="2.0"),
            generate_code=lambda: "v2",
        )
        registry.register(skill_v1)
        registry.register(skill_v2)
        assert registry.count == 1
        assert registry.get("s").meta.version == "2.0"

    def test_skill_descriptions(self):
        """应能生成描述文本"""
        registry = SkillRegistry()
        registry.register(Skill(
            meta=SkillMeta(name="test", display_name="测试", description="测试描述", category=SkillCategory.ANALYSIS),
            generate_code=lambda: "pass",
        ))
        desc = registry.get_skill_descriptions()
        assert "测试" in desc
        assert "测试描述" in desc


class TestBuiltinSkills:
    """测试内置 Skill"""

    def test_builtin_skills_registered(self):
        """内置 Skill 应已注册"""
        registry = get_registry()
        assert registry.count >= 5  # 至少 5 个内置 Skill

    def test_describe_statistics_generates_code(self):
        """描述统计 Skill 应能生成代码"""
        registry = get_registry()
        skill = registry.get("describe_statistics")
        assert skill is not None
        code = skill.generate_code()
        assert "describe" in code
        assert "isnull" in code or "缺失值" in code

    def test_correlation_generates_code(self):
        """相关性分析 Skill 应能生成代码"""
        registry = get_registry()
        skill = registry.get("correlation_analysis")
        assert skill is not None
        code = skill.generate_code()
        assert "corr" in code
        assert "heatmap" in code

    def test_distribution_generates_code(self):
        """分布分析 Skill 应能生成代码"""
        registry = get_registry()
        skill = registry.get("distribution_analysis")
        assert skill is not None
        code = skill.generate_code()
        assert "hist" in code
        assert "skew" in code


class TestSkillMdFormat:
    """测试 SKILL.md 格式的加载"""

    def test_parse_skill_md(self, tmp_path):
        """应能解析标准 SKILL.md 文件"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "display_name: 测试技能\n"
            "description: 这是一个测试 Skill\n"
            "version: 2.0.0\n"
            "category: analysis\n"
            "tags: [测试, test, demo]\n"
            "---\n\n"
            "# 测试技能\n\n"
            "## 使用说明\n"
            "这里是完整的使用指令。\n",
            encoding="utf-8",
        )

        skill = _parse_skill_md(skill_md)
        assert skill is not None
        assert skill.meta.name == "test-skill"
        assert skill.meta.display_name == "测试技能"
        assert skill.meta.description == "这是一个测试 Skill"
        assert skill.meta.version == "2.0.0"
        assert skill.meta.category == SkillCategory.ANALYSIS
        assert "测试" in skill.meta.tags
        assert skill.meta.source == "local"

    def test_parse_skill_md_minimal(self, tmp_path):
        """最小化 SKILL.md 也应能解析"""
        skill_dir = tmp_path / "minimal"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: minimal\n"
            "description: Minimal skill\n"
            "---\n\n"
            "Instructions here.\n",
            encoding="utf-8",
        )

        skill = _parse_skill_md(skill_md)
        assert skill is not None
        assert skill.meta.name == "minimal"
        assert skill.meta.category == SkillCategory.UTILITY  # 默认

    def test_progressive_disclosure(self, tmp_path):
        """完整指令应延迟加载"""
        skill_dir = tmp_path / "lazy"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: lazy\n"
            "description: Short desc\n"
            "---\n\n"
            "# Full Instructions\n"
            "These are the full instructions that should only load when needed.\n",
            encoding="utf-8",
        )

        skill = _parse_skill_md(skill_md)
        assert skill is not None
        # 元信息可用
        assert skill.meta.description == "Short desc"
        # 完整指令需要显式访问才加载
        full = skill.full_instructions
        assert "Full Instructions" in full
        assert "only load when needed" in full

    def test_load_from_directory(self, tmp_path):
        """应能从目录批量加载 Skill"""
        # 创建 2 个 Skill 目录
        for name in ["skill-a", "skill-b"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name} desc\n---\n\n# {name}\n",
                encoding="utf-8",
            )

        registry = SkillRegistry()
        loaded = registry.load_from_directory(tmp_path)
        assert loaded == 2
        assert registry.get("skill-a") is not None
        assert registry.get("skill-b") is not None

    def test_load_nonexistent_directory(self):
        """不存在的目录不应崩溃"""
        registry = SkillRegistry()
        loaded = registry.load_from_directory("/nonexistent/path")
        assert loaded == 0

    def test_example_skill_loads(self):
        """示例 SKILL.md Skill 应能加载"""
        example_dir = ROOT / "skills" / "examples"
        if not example_dir.exists():
            pytest.skip("示例 Skill 目录不存在")

        registry = SkillRegistry()
        loaded = registry.load_from_directory(example_dir)
        assert loaded >= 1

        ts = registry.get("time-series-analysis")
        if ts:
            assert "时间序列" in ts.meta.display_name
            assert ts.full_instructions  # 应有完整指令


class TestCodeExtraction:
    """测试代码提取（从 LLM 响应）"""

    def test_clean_code(self):
        """纯代码直接返回"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response("import pandas as pd\nprint('hello')")
        assert "import pandas" in result

    def test_python_markdown_block(self):
        """```python ... ``` 格式"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response(
            "```python\nimport pandas as pd\nprint(df.head())\n```"
        )
        assert "import pandas" in result
        assert "```" not in result

    def test_deepseek_think_tags(self):
        """DeepSeek <think> 标签应被移除"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response(
            "<think>\nLet me analyze...\n</think>\n\n"
            "```python\nimport pandas as pd\nprint(df.head())\n```"
        )
        assert "import pandas" in result
        assert "<think>" not in result

    def test_text_around_code_block(self):
        """代码块前后的文字应被忽略"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response(
            "I will analyze the data.\n\n"
            "```python\nimport pandas as pd\nprint(df.head())\n```\n\n"
            "This shows the results."
        )
        assert "import pandas" in result
        assert "I will analyze" not in result

    def test_plain_backtick_block(self):
        """无语言标记的 ``` 代码块"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response(
            "```\nimport pandas as pd\nprint(df.head())\n```"
        )
        assert "import pandas" in result

    def test_multiple_code_blocks(self):
        """多个代码块应取最长的"""
        from src.agents.code_generator import _extract_code_from_response
        result = _extract_code_from_response(
            "```python\nimport pandas as pd\n```\n\n"
            "```python\nimport pandas as pd\n"
            "df_stats = df.describe()\n"
            "print(df_stats)\n```"
        )
        assert "describe" in result  # 应取第二个更长的块

    def test_debugger_uses_same_extraction(self):
        """Debugger 的代码提取应与 CodeGenerator 一致"""
        from src.agents.debugger import _extract_code
        result = _extract_code(
            "<think>fixing...</think>\n\n"
            "```python\nprint('fixed')\n```"
        )
        assert "print('fixed')" in result
        assert "<think>" not in result
