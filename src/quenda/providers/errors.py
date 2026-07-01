"""
Custom exception types for Quenda providers.

This module defines a hierarchy of exceptions for handling errors
in the provider layer.
"""

from __future__ import annotations


class QuendaError(Exception):
    """
    Base exception for all Quenda errors.

    All custom exceptions in Quenda inherit from this class.
    """

    pass


class ProviderError(QuendaError):
    """
    Base exception for provider-related errors.

    This includes errors from model providers, API communication,
    authentication, and model configuration.
    """

    pass


class AuthenticationError(ProviderError):
    """
    Authentication failed.

    Raised when:
    - API key is invalid or expired
    - Authentication credentials are missing
    - Authorization is denied
    """

    pass


class APIError(ProviderError):
    """
    Base exception for API communication errors.

    This covers errors that occur during communication with
    model provider APIs.
    """

    pass


class RateLimitError(APIError):
    """
    Rate limit exceeded.

    Raised when the API returns a rate limit error (e.g., HTTP 429).
    Supports the `retry_after` attribute for knowing when to retry.

    Attributes:
        retry_after: Suggested wait time in seconds before retrying.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NetworkError(APIError):
    """
    Network connectivity issues.

    Raised when:
    - Connection to the API fails
    - Request times out
    - DNS resolution fails
    - Other network-level errors occur
    """

    pass


class ModelNotFoundError(ProviderError):
    """
    Model not found in provider.

    Raised when attempting to use a model that doesn't exist
    in the provider's catalog.
    """

    pass


class UnsupportedFeatureError(ProviderError):
    """
    Feature not supported by model.

    Raised when attempting to use a feature (e.g., tool calling,
    vision, streaming) that the model doesn't support.
    """

    def __init__(
        self,
        message: str,
        feature: str | None = None,
    ) -> None:
        super().__init__(message)
        self.feature = feature


__all__ = [
    "QuendaError",
    "ProviderError",
    "AuthenticationError",
    "APIError",
    "RateLimitError",
    "NetworkError",
    "ModelNotFoundError",
    "UnsupportedFeatureError",
]
