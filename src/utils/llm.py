"""
LLM 客户端封装
统一管理模型初始化，支持 DeepSeek 和 OpenAI 兼容接口切换。
"""
from __future__ import annotations

from functools import lru_cache

from langchain_deepseek import ChatDeepSeek
from configs.settings import settings


@lru_cache(maxsize=1)
def get_llm(
    model: str | None = None,
    temperature: float | None = None,
) -> ChatDeepSeek:
    """
    获取 LLM 实例（单例缓存）

    Args:
        model: 模型名称，默认使用配置文件中的 DEEPSEEK_MODEL
        temperature: 生成温度，默认使用配置文件中的 LLM_TEMPERATURE

    Returns:
        ChatDeepSeek 实例，已支持 tool calling
    """
    return ChatDeepSeek(
        model=model or settings.DEEPSEEK_MODEL,
        temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
        max_retries=settings.LLM_MAX_RETRIES,
        api_key=settings.DEEPSEEK_API_KEY,
    )


def get_llm_uncached(
    model: str | None = None,
    temperature: float | None = None,
) -> ChatDeepSeek:
    """
    获取不带缓存的 LLM 实例（用于需要不同参数的场景）
    """
    return ChatDeepSeek(
        model=model or settings.DEEPSEEK_MODEL,
        temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
        max_retries=settings.LLM_MAX_RETRIES,
        api_key=settings.DEEPSEEK_API_KEY,
    )
