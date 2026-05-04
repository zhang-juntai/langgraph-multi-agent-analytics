"""
DataProfiler Agent — 数据探索专家 (v5 - 动态 Skill 发现)

职责：
1. 根据用户意图动态选择分析 Skills
2. 在沙箱中执行生成的代码
3. 汇总分析结果返回给用户

核心升级（v5）：
- 不再硬编码 Skill 列表
- 使用 SkillSelector 动态发现
- 根据数据上下文智能选择
- 支持新增 Skill 自动参与分析
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage

from src.graph.state import AnalysisState
from src.sandbox.factory import execute_in_sandbox
from src.skills.selector import SkillSelector, build_data_context_from_state

logger = logging.getLogger(__name__)


def data_profiler_node(state: AnalysisState) -> dict[str, Any]:
    """
    DataProfiler Node：智能数据探索分析 (v5)

    工作流程：
    1. 检查是否有已加载的数据集
    2. 构建数据上下文
    3. 使用 SkillSelector 动态选择相关 Skills
    4. 生成并执行分析代码
    5. 返回结果（失败时触发 Debugger）

    读取：state["datasets"], state["active_dataset_index"], state["intent"], state["session_id"]
    写入：state["messages"], state["code_result"], state["figures"]
    """
    datasets = state.get("datasets", [])
    active_idx = state.get("active_dataset_index", 0)
    intent = state.get("intent", "")
    session_id = state.get("session_id", "")

    # === 数据验证：拒绝幻觉 ===
    if not datasets:
        return {
            "messages": [
                AIMessage(
                    content="❌ **暂无数据集**\n\n请先上传数据文件（CSV、Excel、JSON），然后我才能进行探索分析。"
                )
            ],
            "error": "无数据集 - 请上传文件",
        }

    # 验证数据集有有效的存储信息
    valid_datasets = []
    for ds in datasets:
        if ds.get("file_storage_id") or ds.get("file_path"):
            valid_datasets.append(ds)

    if not valid_datasets:
        return {
            "messages": [
                AIMessage(content="❌ **数据集无效**\n\n上传的文件可能已损坏或丢失。请重新上传数据文件。")
            ],
            "error": "数据集无有效存储信息",
        }

    # 当前活跃数据集
    active_ds = valid_datasets[min(active_idx, len(valid_datasets) - 1)]

    # === v5 核心升级：动态 Skill 发现 ===
    selector = SkillSelector()
    data_context = build_data_context_from_state(state)

    # 根据意图和数据上下文选择 Skills
    selected_skills = selector.select_skills_for_intent(
        intent=intent or "数据探索分析",
        data_context=data_context,
        max_skills=5,  # 最多执行 5 个 Skills
    )

    # 如果没有匹配到任何 Skill，使用默认分析技能
    if not selected_skills:
        logger.info("未匹配到特定 Skill，使用默认分析技能")
        # 获取所有分析类 Skills
        all_analysis = selector.get_analysis_skills()
        selected_skills = all_analysis[:3]  # 取前 3 个

    # 记录选择的 Skills
    skill_names = [s.meta.name for s in selected_skills]
    logger.info(f"DataProfiler 选中 Skills: {skill_names}")

    # 执行选中的 Skills
    all_results = []
    all_figures = []
    all_codes = []
    failed_skills = []
    accumulated_stderr = []

    for skill in selected_skills:
        if skill.generate_code is None:
            logger.debug(f"Skill {skill.meta.name} 无代码生成器，跳过")
            continue

        # 生成代码
        code = skill.generate_code()
        all_codes.append(f"# === {skill.meta.display_name} ===\n{code}")

        # 在沙箱中执行（传递 session_id 以从数据库获取文件）
        result = execute_in_sandbox(
            code=code,
            datasets=valid_datasets,
        )

        if result["success"]:
            output = result.get("stdout", "").strip()
            if output:
                all_results.append(f"### {skill.meta.display_name}\n\n```\n{output}\n```")
            figures = result.get("figures", [])
            all_figures.extend(figures)
            if figures:
                all_results.append(f"📈 生成了 {len(figures)} 张图表")
        else:
            stderr = result.get("stderr", "未知错误")
            all_results.append(
                f"### {skill.meta.display_name}\n\n⚠️ 执行出现问题: {stderr[:200]}"
            )
            failed_skills.append(skill.meta.name)
            accumulated_stderr.append(f"[{skill.meta.name}] {stderr}")

    # 汇总结果
    if all_results:
        summary = (
            f"## 🔍 数据探索分析: {active_ds['file_name']}\n\n"
            f"**分析技能**: {', '.join(skill_names)}\n\n"
            + "\n\n".join(all_results)
        )
    else:
        summary = "分析未产生结果，请检查数据集格式。"

    # 如果有失败，添加提示
    if failed_skills:
        summary += f"\n\n---\n⚠️ 有 {len(failed_skills)} 个分析任务失败，正在尝试修复..."

    # 构建完整代码记录
    full_code = "\n\n".join(all_codes)

    # 判断是否需要触发 Debugger
    has_failures = len(failed_skills) > 0
    combined_stderr = "\n".join(accumulated_stderr) if accumulated_stderr else ""

    return {
        "messages": [AIMessage(content=summary)],
        "current_code": full_code,
        "code_result": {
            "code": full_code,
            "stdout": "\n".join(all_results),
            "stderr": combined_stderr,
            "success": not has_failures,
            "figures": all_figures,
            "dataframes": {},
        },
        "figures": list(state.get("figures", [])) + all_figures,
        "needs_debug": has_failures,
        "retry_count": 0 if has_failures else state.get("retry_count", 0),
    }
