"""
错误恢复模块测试
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.error_recovery import (
    retry_with_backoff,
    safe_execute,
    graceful_degrade,
    ErrorContext,
    user_friendly_error,
)


class TestRetryWithBackoff:
    """测试重试装饰器"""

    def test_success_no_retry(self):
        """成功时不重试"""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def always_ok():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_ok()
        assert result == "ok"
        assert call_count == 1

    def test_retry_then_success(self):
        """失败后重试成功"""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("暂时失败")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3

    def test_all_retries_exhausted(self):
        """重试耗尽后抛出异常"""
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fail():
            raise ValueError("永远失败")

        with pytest.raises(ValueError, match="永远失败"):
            always_fail()


class TestSafeExecute:
    """测试安全执行"""

    def test_success(self):
        """成功时返回结果"""
        result, err = safe_execute(lambda: 42)
        assert result == 42
        assert err is None

    def test_failure_returns_fallback(self):
        """失败时返回 fallback"""
        def bad():
            raise RuntimeError("boom")

        result, err = safe_execute(bad, fallback="默认值")
        assert result == "默认值"
        assert "boom" in err


class TestGracefulDegrade:
    """测试优雅降级"""

    def test_primary_success(self):
        """主函数成功时使用主函数"""
        result = graceful_degrade(
            primary=lambda: "主方案",
            fallback=lambda: "降级方案",
        )
        assert result == "主方案"

    def test_fallback_on_failure(self):
        """主函数失败时降级"""
        def bad_primary():
            raise RuntimeError("主方案失败")

        result = graceful_degrade(
            primary=bad_primary,
            fallback=lambda: "降级方案",
        )
        assert result == "降级方案"


class TestErrorContext:
    """测试错误上下文"""

    def test_success(self):
        """成功执行无错误"""
        ctx = ErrorContext("测试操作")
        with ctx:
            x = 1 + 1
        assert not ctx.has_errors

    def test_captures_exception(self):
        """异常应被捕获"""
        ctx = ErrorContext("测试操作")
        with ctx:
            raise ValueError("测试异常")
        assert ctx.has_errors
        assert "测试异常" in ctx.error_summary

    def test_warnings(self):
        """警告应被记录"""
        ctx = ErrorContext("测试操作")
        with ctx:
            ctx.warn("小问题1")
            ctx.warn("小问题2")
        assert len(ctx.warnings) == 2
        assert not ctx.has_errors


class TestUserFriendlyError:
    """测试用户友好错误消息"""

    def test_api_key_error(self):
        """API key 错误"""
        msg = user_friendly_error(ValueError("DEEPSEEK_API_KEY must be set"))
        assert "配置" in msg or "API" in msg

    def test_rate_limit(self):
        """限流错误"""
        msg = user_friendly_error(Exception("rate limit exceeded 429"))
        assert "频繁" in msg

    def test_timeout(self):
        """超时错误"""
        msg = user_friendly_error(Exception("Connection timeout"))
        assert "超时" in msg

    def test_encoding_error(self):
        """编码错误"""
        msg = user_friendly_error(Exception("codec can't decode byte"))
        assert "编码" in msg or "UTF-8" in msg

    def test_generic_error(self):
        """通用错误"""
        msg = user_friendly_error(RuntimeError("something broke"))
        assert "something broke" in msg
