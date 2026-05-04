"""
长会话上下文管理
解决长对话中 LLM token 超限的问题。

策略：
1. 滑动窗口：只保留最近 N 条消息
2. 消息摘要：对旧消息进行压缩摘要
3. 关键信息提取：保留数据集描述和关键分析结果
4. 分层上下文：系统提示(固定) + 摘要(压缩) + 近期消息(完整)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_WINDOW_SIZE = 10        # 保留最近 N 条完整消息
DEFAULT_MAX_TOKENS = 8000       # 近似 token 上限
CHARS_PER_TOKEN = 2.5           # 中文约 2.5 字符/token


def trim_messages(
    messages: list,
    window_size: int = DEFAULT_WINDOW_SIZE,
    max_chars: int = None,
) -> list:
    """
    滑动窗口截断消息。

    保留策略：
    1. 第一条消息（通常是系统初始交互）
    2. 最近 window_size 条消息

    Args:
        messages: 原始消息列表
        window_size: 保留的最近消息数
        max_chars: 最大字符数限制

    Returns:
        截断后的消息列表
    """
    if len(messages) <= window_size:
        return messages

    max_chars = max_chars or int(DEFAULT_MAX_TOKENS * CHARS_PER_TOKEN)

    # 保留第一条 + 最近 N 条
    result = [messages[0]] + messages[-window_size:]

    # 检查总字符数
    total_chars = sum(
        len(m.content) if hasattr(m, "content") else len(str(m))
        for m in result
    )

    # 如果仍超长，继续裁剪
    while total_chars > max_chars and len(result) > 3:
        removed = result.pop(1)  # 删除最旧的（保留第一条）
        removed_len = len(removed.content) if hasattr(removed, "content") else len(str(removed))
        total_chars -= removed_len

    return result


def summarize_old_messages(
    messages: list,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> tuple[str, list]:
    """
    将旧消息压缩为摘要文本 + 保留近期消息。

    Args:
        messages: 原始消息列表
        window_size: 保留的完整消息数

    Returns:
        (summary_text, recent_messages)
        summary_text: 旧消息的摘要（可注入系统提示词）
        recent_messages: 保留的近期消息
    """
    if len(messages) <= window_size:
        return "", messages

    old_messages = messages[:-window_size]
    recent_messages = messages[-window_size:]

    # 提取旧消息中的关键信息
    key_points = []
    for msg in old_messages:
        content = msg.content if hasattr(msg, "content") else str(msg)
        role = msg.type if hasattr(msg, "type") else "unknown"

        # 提取用户的关键需求
        if role == "human" and len(content) > 10:
            key_points.append(f"用户: {content[:100]}")

        # 提取分析结果摘要
        if role == "ai" and any(kw in content for kw in ["✅", "📊", "📈", "统计", "结果"]):
            # 截取前 150 字符作为摘要
            key_points.append(f"分析: {content[:150]}")

    if key_points:
        summary = "## 历史对话摘要\n\n" + "\n".join(f"- {p}" for p in key_points[-10:])
    else:
        summary = f"（前 {len(old_messages)} 条消息已压缩）"

    return summary, recent_messages


def build_optimized_context(
    messages: list,
    datasets: list[dict] | None = None,
    memory_context: str = "",
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> dict[str, Any]:
    """
    构建优化后的完整上下文。

    Returns:
        {
            "summary": str,          # 历史摘要
            "recent_messages": list,  # 近期消息
            "dataset_context": str,   # 数据集描述
            "memory_context": str,    # 记忆上下文
            "total_chars": int,       # 总字符数
        }
    """
    summary, recent = summarize_old_messages(messages, window_size)

    # 数据集描述
    dataset_context = ""
    if datasets:
        parts = []
        for ds in datasets:
            parts.append(
                f"- {ds.get('file_name', '?')}: "
                f"{ds.get('num_rows', '?')}行 × {ds.get('num_cols', '?')}列, "
                f"列=[{', '.join(ds.get('columns', [])[:10])}]"
            )
        dataset_context = "已加载数据集:\n" + "\n".join(parts)

    total_chars = (
        len(summary)
        + sum(len(m.content) if hasattr(m, "content") else len(str(m)) for m in recent)
        + len(dataset_context)
        + len(memory_context)
    )

    return {
        "summary": summary,
        "recent_messages": recent,
        "dataset_context": dataset_context,
        "memory_context": memory_context,
        "total_chars": total_chars,
        "estimated_tokens": int(total_chars / CHARS_PER_TOKEN),
    }
