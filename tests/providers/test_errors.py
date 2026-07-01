"""
Tests for provider error types.
"""

import pytest

from kora.providers.errors import (
    KoraError,
    ProviderError,
    APIError,
    RateLimitError,
    NetworkError,
    AuthenticationError,
    ModelNotFoundError,
    UnsupportedFeatureError,
)


class TestErrorHierarchy:
    """Tests for error inheritance."""

    def test_kora_error_is_exception(self) -> None:
        """KoraError should inherit from Exception."""
        assert issubclass(KoraError, Exception)

    def test_provider_error_inherits_kora_error(self) -> None:
        """ProviderError should inherit from KoraError."""
        assert issubclass(ProviderError, KoraError)

    def test_api_error_inherits_provider_error(self) -> None:
        """APIError should inherit from ProviderError."""
        assert issubclass(APIError, ProviderError)

    def test_rate_limit_error_inherits_api_error(self) -> None:
        """RateLimitError should inherit from APIError."""
        assert issubclass(RateLimitError, APIError)

    def test_network_error_inherits_api_error(self) -> None:
        """NetworkError should inherit from APIError."""
        assert issubclass(NetworkError, APIError)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_basic_rate_limit_error(self) -> None:
        """Test creating a basic rate limit error."""
        error = RateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert error.retry_after is None

    def test_rate_limit_error_with_retry_after(self) -> None:
        """Test rate limit error with retry_after value."""
        error = RateLimitError("Rate limit exceeded", retry_after=5.0)
        assert error.retry_after == 5.0

    def test_rate_limit_error_with_int_retry_after(self) -> None:
        """Test rate limit error with integer retry_after."""
        error = RateLimitError("Rate limit exceeded", retry_after=10)
        assert error.retry_after == 10


class TestUnsupportedFeatureError:
    """Tests for UnsupportedFeatureError."""

    def test_basic_unsupported_feature_error(self) -> None:
        """Test creating an unsupported feature error."""
        error = UnsupportedFeatureError("Feature not supported")
        assert str(error) == "Feature not supported"
        assert error.feature is None

    def test_unsupported_feature_error_with_feature(self) -> None:
        """Test unsupported feature error with feature name."""
        error = UnsupportedFeatureError(
            "Streaming not supported",
            feature="streaming",
        )
        assert error.feature == "streaming"


class TestErrorCatching:
    """Tests for catching errors by base types."""

    def test_catch_rate_limit_as_api_error(self) -> None:
        """RateLimitError should be catchable as APIError."""
        error = RateLimitError("Rate limited")
        with pytest.raises(APIError):
            raise error

    def test_catch_network_as_provider_error(self) -> None:
        """NetworkError should be catchable as ProviderError."""
        error = NetworkError("Connection failed")
        with pytest.raises(ProviderError):
            raise error

    def test_catch_auth_as_kora_error(self) -> None:
        """AuthenticationError should be catchable as KoraError."""
        error = AuthenticationError("Invalid API key")
        with pytest.raises(KoraError):
            raise error
