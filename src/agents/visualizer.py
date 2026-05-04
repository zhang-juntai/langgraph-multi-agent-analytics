"""
Visualizer Agent — 可视化专家
职责：
1. 根据用户的自然语言需求，调用 LLM 生成可视化代码
2. 利用 Skill Registry 中的可视化 Skill 增强代码质量
3. 在沙箱中执行，返回图表路径
4. 自动选择最合适的图表类型

核心原则：开发层不包含任何可视化绘图代码，100% 由 LLM 生成。

支持图表类型（由 LLM 自动选择）：
- 折线图、柱状图、散点图、饼图
- 热力图、箱线图、小提琴图
- 多子图组合、双 Y 轴
- 交互式图表（plotly）
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from src.graph.state import AnalysisState
from src.utils.llm import get_llm
from src.sandbox.factory import execute_in_sandbox
from src.skills.base import get_registry
from src.agents.code_generator import _extract_code_from_response

logger = logging.getLogger(__name__)

# ============================================================
# Visualizer 系统提示词
# ============================================================
VIZ_SYSTEM_PROMPT = """你是一个专业的数据可视化代码生成器。

## 你的职责
根据用户的可视化需求，生成高质量的 Python 可视化代码。

## 执行环境
- 数据已经通过 pandas 加载为 DataFrame，变量名为 `df`
- 已导入的库：pandas as pd, numpy as np
- matplotlib, seaborn, plotly 可直接 import
- matplotlib 的 plt.show() 会自动保存图表
- 中文字体配置：plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]

## 当前数据集信息
{dataset_info}

## 可用的可视化技能（参考）
{skill_descriptions}

## 代码规范
1. 只输出纯 Python 代码，不要 markdown 标记
2. 优先使用 matplotlib + seaborn，需要交互时用 plotly
3. 每张图表都要：
   - 设置中文标题
   - 添加轴标签
   - 设置合理的颜色方案
   - 调用 plt.tight_layout() 避免遮挡
   - 最后调用 plt.show()
4. 中文字体配置放在代码开头
5. 处理可能的缺失值（dropna）
6. 如果数据列太多，自动选择最重要的几列
7. 使用 print() 输出对图表的文字说明

## 图表选择指南
- 趋势/时间序列 → 折线图
- 类别比较 → 柱状图 / 水平柱状图
- 分布 → 直方图 / 箱线图 / 小提琴图
- 关系/相关性 → 散点图 / 热力图
- 占比 → 饼图（类别 ≤ 8 个时）
- 多变量 → 成对图 / 多子图
"""


def _build_dataset_info(state: AnalysisState) -> str:
    """构建数据集描述信息"""
    datasets = state.get("datasets", [])
    if not datasets:
        return "暂无数据集"

    active_idx = state.get("active_dataset_index", 0)
    ds = datasets[min(active_idx, len(datasets) - 1)]

    return (
        f"文件: {ds.get('file_name', '未知')}\n"
        f"行数: {ds.get('num_rows', '?')}, 列数: {ds.get('num_cols', '?')}\n"
        f"列名: {', '.join(ds.get('columns', []))}\n"
        f"数据类型: {ds.get('dtypes', {})}\n"
        f"预览:\n```\n{ds.get('preview', '无预览')}\n```"
    )


def visualizer_node(state: AnalysisState) -> dict[str, Any]:
    """
    Visualizer Node：根据用户需求生成可视化图表

    工作流程：
    1. 构建带有数据集上下文 + Skill 参考的提示词
    2. 调用 LLM 生成可视化代码
    3. 在沙箱中执行
    4. 返回图表路径和说明

    读取：state["messages"], state["datasets"]
    写入：state["current_code"], state["code_result"], state["messages"], state["figures"]
    """
    messages = state.get("messages", [])
    datasets = state.get("datasets", [])

    if not datasets:
        return {
            "messages": [
                AIMessage(content="❌ 请先上传数据文件，然后告诉我你想画什么图。")
            ],
            "error": "无数据集",
        }

    llm = get_llm()

    # 构建系统提示词
    dataset_info = _build_dataset_info(state)
    registry = get_registry()

    # 搜索可视化相关 Skill
    viz_skills = registry.search("可视化") + registry.search("visualization")
    viz_descs = "\n".join(
        f"- {s.display_name}: {s.description}" for s in viz_skills
    ) if viz_skills else "无特定可视化 Skill"

    system_prompt = VIZ_SYSTEM_PROMPT.format(
        dataset_info=dataset_info,
        skill_descriptions=viz_descs,
    )

    # 构建 LLM 消息
    llm_messages = [SystemMessage(content=system_prompt)]
    recent = messages[-4:] if len(messages) > 4 else messages
    llm_messages.extend(recent)

    try:
        response = llm.invoke(llm_messages)
        generated_code = _extract_code_from_response(response.content)

        if not generated_code:
            return {
                "messages": [AIMessage(content="⚠️ 可视化代码生成失败，请重新描述你的需求。")],
                "error": "代码为空",
            }

        logger.info(f"Visualizer 生成代码: {len(generated_code)} 字符")

        # 在沙箱中执行
        result = execute_in_sandbox(
            code=generated_code,
            datasets=datasets,
        )

        code_display = f"```python\n{generated_code}\n```"

        if result["success"]:
            stdout = result.get("stdout", "").strip()
            figures = result.get("figures", [])

            parts = [f"📊 可视化已生成\n\n**代码:**\n{code_display}"]
            if stdout:
                parts.append(f"\n**说明:**\n{stdout}")
            if figures:
                parts.append(f"\n📈 生成了 {len(figures)} 张图表")

            reply = "\n".join(parts)
            all_figures = list(state.get("figures", [])) + figures
        else:
            stderr = result.get("stderr", "未知错误")
            reply = (
                f"⚠️ 可视化代码执行出错\n\n**代码:**\n{code_display}\n\n"
                f"**错误:**\n```\n{stderr}\n```\n\n"
                f"正在尝试自动修复..."
            )
            all_figures = list(state.get("figures", []))

        return {
            "messages": [AIMessage(content=reply)],
            "current_code": generated_code,
            "code_result": result,
            "figures": all_figures,
            "retry_count": 0 if result["success"] else state.get("retry_count", 0),
        }

    except Exception as e:
        logger.error(f"Visualizer 调用失败: {e}")
        return {
            "messages": [AIMessage(content=f"❌ 可视化生成失败: {str(e)}")],
            "error": str(e),
        }
