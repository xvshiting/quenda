"""
Tests for retry mechanism.
"""

import pytest
from unittest.mock import Mock

from quenda.providers.errors import RateLimitError, NetworkError
from quenda.providers.retry import retry_with_backoff, retry_with_backoff_async


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_no_retry_on_success(self) -> None:
        """Should not retry on successful call."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_retryable_error(self) -> None:
        """Should retry on retryable exceptions."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Connection failed")
            return "success"

        result = failing_then_success()
        assert result == "success"
        assert call_count == 3

    def test_no_retry_on_non_retryable_error(self) -> None:
        """Should not retry on non-retryable exceptions."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            failing_func()

        assert call_count == 1

    def test_max_retries_exceeded(self) -> None:
        """Should raise after max retries exceeded."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Connection failed")

        with pytest.raises(NetworkError, match="Connection failed"):
            always_failing()

        # 1 initial + 2 retries = 3 total calls
        assert call_count == 3

    def test_retry_with_rate_limit_retry_after(self) -> None:
        """Should use retry_after from RateLimitError."""
        call_count = 0

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limited", retry_after=0.02)
            return "success"

        result = rate_limited()
        assert result == "success"
        assert call_count == 2

    def test_custom_retryable_exceptions(self) -> None:
        """Should respect custom retryable exceptions."""
        call_count = 0

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 2


class TestRetryWithBackoffAsync:
    """Tests for retry_with_backoff_async decorator."""

    @pytest.mark.asyncio
    async def test_async_no_retry_on_success(self) -> None:
        """Should not retry on successful async call."""
        call_count = 0

        @retry_with_backoff_async(max_retries=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_on_retryable_error(self) -> None:
        """Should retry on retryable exceptions in async."""
        call_count = 0

        @retry_with_backoff_async(max_retries=3, base_delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Connection failed")
            return "success"

        result = await failing_then_success()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_max_retries_exceeded(self) -> None:
        """Should raise after max retries exceeded in async."""
        call_count = 0

        @retry_with_backoff_async(max_retries=2, base_delay=0.01)
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Connection failed")

        with pytest.raises(NetworkError, match="Connection failed"):
            await always_failing()

        assert call_count == 3
