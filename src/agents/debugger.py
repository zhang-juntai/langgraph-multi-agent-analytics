"""
Debugger Agent — 代码纠错专家
职责：
1. 当 CodeGenerator 生成的代码执行失败时，自动分析错误
2. 调用 LLM 修复代码
3. 在沙箱中重新执行
4. 如果连续修复失败超过阈值，降级到人工提示

设计原则：
- 独立于 CodeGenerator，形成"生成 → 执行 → 失败 → 修复 → 重试"闭环
- 最多重试 MAX_RETRIES 次，防止无限循环
- 修复时提供完整的错误上下文（原始代码 + stderr + 数据信息）
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from src.graph.state import AnalysisState
from src.utils.llm import get_llm
from src.sandbox.factory import execute_in_sandbox

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

DEBUGGER_SYSTEM_PROMPT = """你是一个 Python 代码调试专家。

## 你的职责
分析执行失败的代码和错误信息，生成修复后的完整代码。

## 执行环境
- 数据通过 pandas 加载，变量名为 `df`
- 已导入：pandas, numpy, matplotlib, seaborn
- 中文字体和 Agg 后端已配置
- plt.show() 会自动保存图表

## 当前数据集信息
{dataset_info}

## 修复规范
1. 只输出修复后的完整 Python 代码，不要 markdown 标记
2. 不要只修改出错的那一行，要给出完整可运行的代码
3. 常见问题处理：
   - 列名不存在 → 检查实际列名并修正
   - 类型错误 → 添加类型转换
   - 缺失值 → 添加 dropna() 或 fillna()
   - 编码问题 → 指定 encoding
   - 图表中文乱码 → 检查字体配置
4. 在修复代码的关键位置添加注释说明修复内容
"""


def _build_debug_context(state: AnalysisState) -> str:
    """构建调试上下文"""
    code_result = state.get("code_result", {})
    original_code = state.get("current_code", "")
    stderr = code_result.get("stderr", "未知错误")

    datasets = state.get("datasets", [])
    ds_info = ""
    if datasets:
        active_idx = state.get("active_dataset_index", 0)
        ds = datasets[min(active_idx, len(datasets) - 1)]
        ds_info = (
            f"文件: {ds.get('file_name', '?')}, "
            f"行: {ds.get('num_rows', '?')}, "
            f"列: {ds.get('columns', [])}, "
            f"类型: {ds.get('dtypes', {})}"
        )

    return (
        f"## 原始代码\n```python\n{original_code}\n```\n\n"
        f"## 错误信息\n```\n{stderr}\n```\n\n"
        f"## 数据集信息\n{ds_info}\n\n"
        f"请修复代码并输出完整的可运行版本。"
    )


def _extract_code(content: str) -> str:
    """
    从 LLM 响应中提取代码。
    复用 code_generator 中的健壮提取逻辑。
    """
    from src.agents.code_generator import _extract_code_from_response
    return _extract_code_from_response(content)


def debugger_node(state: AnalysisState) -> dict[str, Any]:
    """
    Debugger Node：自动修复执行失败的代码

    工作流程：
    1. 检查 retry_count 是否超限
    2. 构建调试上下文（原始代码 + 错误信息 + 数据信息）
    3. 调用 LLM 生成修复代码
    4. 在沙箱中执行修复后的代码
    5. 返回结果

    读取：state["current_code"], state["code_result"], state["retry_count"], state["datasets"]
    写入：state["current_code"], state["code_result"], state["messages"], state["retry_count"]
    """
    retry_count = state.get("retry_count", 0)

    # 检查重试次数
    if retry_count >= MAX_RETRIES:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"⚠️ 代码经过 {MAX_RETRIES} 次自动修复仍然失败。\n\n"
                        f"**最近的错误:**\n```\n{state.get('code_result', {}).get('stderr', '未知')}\n```\n\n"
                        f"建议：\n"
                        f"1. 请用更具体的语言描述你的需求\n"
                        f"2. 检查数据文件格式是否正确\n"
                        f"3. 尝试将复杂需求拆分为多个简单步骤"
                    )
                )
            ],
            "retry_count": 0,  # 重置
            "needs_retry": False,
        }

    llm = get_llm()
    datasets = state.get("datasets", [])

    # 构建调试上下文
    debug_context = _build_debug_context(state)

    # 数据集描述
    ds_info = ""
    if datasets:
        active_idx = state.get("active_dataset_index", 0)
        ds = datasets[min(active_idx, len(datasets) - 1)]
        ds_info = (
            f"文件: {ds.get('file_name', '?')}, "
            f"列: {ds.get('columns', [])}, "
            f"类型: {ds.get('dtypes', {})}"
        )

    system_prompt = DEBUGGER_SYSTEM_PROMPT.format(dataset_info=ds_info)

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=debug_context),
        ])

        fixed_code = _extract_code(response.content)

        if not fixed_code:
            return {
                "messages": [AIMessage(content="⚠️ 修复代码生成失败。")],
                "retry_count": retry_count + 1,
            }

        logger.info(f"Debugger 修复代码: {len(fixed_code)} 字符 (重试第 {retry_count + 1} 次)")

        # 执行修复后的代码
        result = execute_in_sandbox(
            code=fixed_code,
            datasets=datasets,
        )

        if result["success"]:
            stdout = result.get("stdout", "").strip()
            figures = result.get("figures", [])

            parts = [
                f"🔧 代码已自动修复并执行成功（第 {retry_count + 1} 次修复）\n\n"
                f"**修复后的代码:**\n```python\n{fixed_code}\n```"
            ]
            if stdout:
                parts.append(f"\n**执行结果:**\n```\n{stdout}\n```")
            if figures:
                parts.append(f"\n📈 生成了 {len(figures)} 张图表")

            return {
                "messages": [AIMessage(content="\n".join(parts))],
                "current_code": fixed_code,
                "code_result": result,
                "figures": list(state.get("figures", [])) + figures,
                "retry_count": 0,  # 成功后重置
            }
        else:
            stderr = result.get("stderr", "未知错误")
            return {
                "messages": [
                    AIMessage(
                        content=f"🔧 第 {retry_count + 1} 次修复后仍有错误: {stderr[:200]}\n继续修复..."
                    )
                ],
                "current_code": fixed_code,
                "code_result": result,
                "retry_count": retry_count + 1,
            }

    except Exception as e:
        logger.error(f"Debugger 调用失败: {e}")
        return {
            "messages": [AIMessage(content=f"❌ 自动修复过程出错: {str(e)}")],
            "retry_count": retry_count + 1,
            "error": str(e),
        }


def should_retry(state: AnalysisState) -> str:
    """
    条件路由函数：判断是否需要继续修复

    用于 CodeGenerator → Debugger 的循环控制。
    返回 "retry" 继续修复，"done" 结束。
    """
    code_result = state.get("code_result", {})
    retry_count = state.get("retry_count", 0)

    if state.get("needs_retry") is False:
        return "done"

    if not code_result:
        return "done"

    # 执行成功 → 结束
    if code_result.get("success", False):
        return "done"

    # 超过重试次数 → 结束
    if retry_count >= MAX_RETRIES:
        return "done"

    # 继续修复
    return "retry"
