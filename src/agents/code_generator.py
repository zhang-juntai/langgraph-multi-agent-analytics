"""
CodeGenerator Agent — 代码架构师
职责：
1. 根据用户的自然语言需求，调用 LLM 动态生成 Python 分析代码
2. 将 Skill Registry 的信息注入提示词，增强代码质量
3. 在沙箱中执行生成的代码
4. 返回执行结果

核心主张：开发层不包含任何数据分析算法，100% 由 LLM 生成。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from src.graph.state import AnalysisState
from src.utils.llm import get_llm
from src.sandbox.factory import execute_in_sandbox
from src.skills.base import get_registry

logger = logging.getLogger(__name__)

# ============================================================
# CodeGenerator 系统提示词
# ============================================================
CODE_GEN_SYSTEM_PROMPT = """你是一个专业的 Python 数据分析代码生成器。

## 你的职责
根据用户的自然语言需求，生成可直接执行的 Python 代码。

## 执行环境
- 数据已经通过 pandas 加载为 DataFrame，变量名为 `df`
- 如果有多个数据集，它们以文件名（去扩展名）作为变量名
- 已导入的库：pandas as pd, numpy as np, matplotlib, seaborn, plotly
- matplotlib 的 plt.show() 会自动保存图表
- 中文字体已配置

## 当前数据集信息
{dataset_info}

## 可用的分析技能（参考）
{skill_descriptions}

## 代码规范
1. 只输出纯 Python 代码，不要 markdown 标记，不要 ```python ```
2. 代码必须自包含，不需要额外导入
3. 使用 print() 输出关键结果，便于用户查看
4. 如果生成图表，务必调用 plt.show()
5. 中文注释说明每一步
6. 处理可能的异常（如空值、类型不匹配）
7. 代码要简洁高效，避免不必要的循环

## 注意
- 如果用户需求不明确，做最合理的默认处理
- 如果数据类型不匹配，先做类型转换
- 数值分析前先处理缺失值（dropna 或 fillna）
"""


def _build_dataset_info(state: AnalysisState) -> str:
    """构建数据集描述信息，注入到提示词中"""
    datasets = state.get("datasets", [])
    if not datasets:
        return "暂无数据集"

    active_idx = state.get("active_dataset_index", 0)
    parts = []

    for i, ds in enumerate(datasets):
        marker = " (当前活跃)" if i == active_idx else ""
        parts.append(
            f"### 数据集 {i+1}: {ds.get('file_name', '未知')}{marker}\n"
            f"- 行数: {ds.get('num_rows', '?')}\n"
            f"- 列数: {ds.get('num_cols', '?')}\n"
            f"- 列名: {', '.join(ds.get('columns', []))}\n"
            f"- 数据类型: {ds.get('dtypes', {})}\n"
            f"- 缺失值: {ds.get('missing_info', {})}\n"
            f"- 预览:\n```\n{ds.get('preview', '无预览')}\n```"
        )

    # 添加表间关系信息
    session_id = state.get("session_id", "")
    if session_id and len(datasets) > 1:
        try:
            from src.storage.relationship_discovery import get_relationship_discovery
            discovery = get_relationship_discovery()
            relations_info = discovery.format_relations_for_prompt(session_id)
            parts.append(f"\n{relations_info}")
        except Exception as e:
            logger.debug(f"获取关系信息失败: {e}")

    return "\n\n".join(parts)


def _extract_code_from_response(content: str) -> str:
    """
    从 LLM 响应中提取纯 Python 代码。

    处理多种响应格式：
    - 纯代码（无 markdown 标记）
    - ```python ... ``` 代码块
    - <think>...</think> + 代码块（DeepSeek）
    - 文字说明 + 代码块 + 文字说明
    - 多个代码块（提取最大的一个）
    """
    import re

    content = content.strip()

    # 1. 移除 DeepSeek <think>...</think> 标签
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 2. 提取 markdown 代码块（支持 ```python 和 ``` 两种格式）
    #    优先找 ```python 块，其次找任意 ``` 块
    python_blocks = re.findall(
        r"```(?:python|py)\s*\n(.*?)```", content, re.DOTALL
    )
    if python_blocks:
        # 取最长的代码块（最可能是完整代码）
        return max(python_blocks, key=len).strip()

    plain_blocks = re.findall(
        r"```\s*\n(.*?)```", content, re.DOTALL
    )
    if plain_blocks:
        return max(plain_blocks, key=len).strip()

    # 3. 没有代码块标记，返回原始内容（去掉前后空白）
    return content.strip()


def code_generator_node(state: AnalysisState) -> dict[str, Any]:
    """
    CodeGenerator Node：根据用户需求生成并执行分析代码

    工作流程：
    1. 构建带有数据集上下文的提示词
    2. 调用 LLM 生成代码
    3. 在沙箱中执行代码
    4. 返回执行结果

    读取：state["messages"], state["datasets"], state["session_id"]
    写入：state["current_code"], state["code_result"], state["messages"], state["figures"]
    """
    llm = get_llm()
    messages = state.get("messages", [])
    datasets = state.get("datasets", [])
    session_id = state.get("session_id", "")

    # === 数据验证：拒绝幻觉 ===
    if not datasets:
        return {
            "messages": [
                AIMessage(content="❌ **请先上传数据文件**\n\n我无法在没有数据的情况下进行分析。请上传 CSV、Excel 或 JSON 文件后，再告诉我你想做什么分析。")
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

    # 构建系统提示词
    dataset_info = _build_dataset_info(state)
    registry = get_registry()
    skill_descriptions = registry.get_skill_descriptions()

    system_prompt = CODE_GEN_SYSTEM_PROMPT.format(
        dataset_info=dataset_info,
        skill_descriptions=skill_descriptions,
    )

    # 构建 LLM 消息列表
    llm_messages = [SystemMessage(content=system_prompt)]

    # 提取最近的用户消息作为需求
    recent = messages[-4:] if len(messages) > 4 else messages
    llm_messages.extend(recent)

    # 调用 LLM 生成代码
    try:
        response = llm.invoke(llm_messages)
        generated_code = _extract_code_from_response(response.content)

        if not generated_code:
            return {
                "messages": [AIMessage(content="⚠️ 代码生成失败，请重新描述你的需求。")],
                "error": "代码为空",
            }

        logger.info(f"LLM 生成代码: {len(generated_code)} 字符")

        # 在沙箱中执行（传递 session_id 以从数据库获取文件）
        result = execute_in_sandbox(
            code=generated_code,
            datasets=valid_datasets,
        )

        # 构建用户可见的回复
        code_display = f"```python\n{generated_code}\n```"

        if result["success"]:
            stdout = result.get("stdout", "").strip()
            figures = result.get("figures", [])

            parts = [f"✅ 代码已生成并执行成功\n\n**生成的代码:**\n{code_display}"]
            if stdout:
                parts.append(f"\n**执行结果:**\n```\n{stdout}\n```")
            if figures:
                parts.append(f"\n📈 生成了 {len(figures)} 张图表")

            reply = "\n".join(parts)
            all_figures = list(state.get("figures", [])) + figures
        else:
            stderr = result.get("stderr", "未知错误")
            reply = (
                f"⚠️ 代码执行出错\n\n**生成的代码:**\n{code_display}\n\n"
                f"**错误信息:**\n```\n{stderr}\n```\n\n"
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
        logger.error(f"CodeGenerator 调用失败: {e}")
        return {
            "messages": [
                AIMessage(content=f"❌ 代码生成过程出错: {str(e)}")
            ],
            "error": str(e),
        }
