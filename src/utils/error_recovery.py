"""
错误恢复模块
提供 LLM 调用重试、优雅降级、全局异常处理等生产化能力。

策略：
1. LLM 调用失败 → 指数退避重试（最多 3 次）
2. 沙箱执行失败 → 已有 Debugger 自修复循环
3. 数据解析失败 → 友好错误提示 + 建议
4. 全局异常 → 捕获并记录，返回用户友好消息
"""
from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable | None = None,
):
    """
    指数退避重试装饰器。

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调（接收 attempt, exception）

    Usage:
        @retry_with_backoff(max_retries=3)
        def call_llm(...):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"[重试] {func.__name__} 第 {attempt + 1} 次失败: {e}, "
                            f"{delay:.1f}s 后重试"
                        )
                        if on_retry:
                            on_retry(attempt + 1, e)
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[重试耗尽] {func.__name__} 经过 {max_retries} 次重试仍失败: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    *args,
    fallback: T = None,
    error_prefix: str = "操作失败",
    **kwargs,
) -> tuple[T | None, str | None]:
    """
    安全执行函数，捕获所有异常。

    Args:
        func: 要执行的函数
        fallback: 失败时的默认返回值
        error_prefix: 错误消息前缀

    Returns:
        (result, None) 成功时
        (fallback, error_message) 失败时
    """
    try:
        result = func(*args, **kwargs)
        return result, None
    except Exception as e:
        error_msg = f"{error_prefix}: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return fallback, error_msg


def graceful_degrade(
    primary: Callable[..., T],
    fallback: Callable[..., T],
    *args,
    **kwargs,
) -> T:
    """
    优雅降级：先尝试主函数，失败则执行降级函数。

    Args:
        primary: 主函数
        fallback: 降级函数

    Returns:
        主函数或降级函数的结果
    """
    try:
        return primary(*args, **kwargs)
    except Exception as e:
        logger.warning(f"[降级] {primary.__name__} 失败: {e}, 使用降级方案")
        return fallback(*args, **kwargs)


class ErrorContext:
    """
    错误上下文管理器。
    收集操作过程中的警告和错误，统一处理。

    Usage:
        ctx = ErrorContext("数据分析")
        with ctx:
            result = do_something()
        if ctx.has_errors:
            print(ctx.error_summary)
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self._start_time: float = 0

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self._start_time
        if exc_type:
            self.errors.append(f"{exc_type.__name__}: {exc_val}")
            logger.error(
                f"[{self.operation_name}] 失败 ({elapsed:.1f}s): {exc_val}"
            )
            return True  # 抑制异常
        elif self.warnings:
            logger.warning(
                f"[{self.operation_name}] 完成（有 {len(self.warnings)} 个警告, {elapsed:.1f}s）"
            )
        else:
            logger.info(f"[{self.operation_name}] 完成 ({elapsed:.1f}s)")
        return False

    def warn(self, message: str):
        """记录警告"""
        self.warnings.append(message)
        logger.warning(f"[{self.operation_name}] 警告: {message}")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def error_summary(self) -> str:
        """生成用户友好的错误摘要"""
        if not self.errors:
            return ""
        lines = [f"⚠️ {self.operation_name}遇到问题："]
        for err in self.errors:
            lines.append(f"  • {err}")
        if self.warnings:
            lines.append(f"\n还有 {len(self.warnings)} 个警告。")
        return "\n".join(lines)


def user_friendly_error(error: Exception) -> str:
    """
    将技术异常转换为用户友好的错误消息。
    """
    error_str = str(error)

    # API 相关
    if "DEEPSEEK_API_KEY" in error_str or "api_key" in error_str.lower():
        return "❌ AI 服务未配置。请在 .env 文件中设置 DEEPSEEK_API_KEY。"

    if "rate limit" in error_str.lower() or "429" in error_str:
        return "⏳ AI 服务请求过于频繁，请稍等几秒再试。"

    if "timeout" in error_str.lower():
        return "⏰ 请求超时。请检查网络连接或稍后再试。"

    if "connection" in error_str.lower():
        return "🌐 网络连接失败。请检查网络连接是否正常。"

    # 数据相关
    if "encoding" in error_str.lower() or "codec" in error_str.lower():
        return "📄 文件编码识别失败。建议将文件另存为 UTF-8 编码后重新上传。"

    if "no such file" in error_str.lower() or "filenotfound" in error_str.lower():
        return "📁 文件未找到。请重新上传数据文件。"

    # 通用
    return f"❌ 发生错误: {error_str[:200]}"
