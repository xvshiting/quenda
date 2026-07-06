"""
Custom exception types for Quenda providers.

This module defines a hierarchy of exceptions for handling errors
in the provider layer.
"""

from __future__ import annotations

from collections.abc import Sequence


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

    Attributes:
        feature: The unsupported feature name (legacy, single feature).
        missing_capabilities: Set of required capabilities not supported by the model.
        model_id: The model that failed the capability check.
        configured_capability_models: Mapping of capability -> configured model name
            (used to suggest alternatives to the user).
    """

    def __init(
        self,
        message: str,
        feature: str | None = None,
        missing_capabilities: set[str] | None = None,
        model_id: str | None = None,
        configured_capability_models: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.feature = feature
        self.missing_capabilities = missing_capabilities
        self.model_id = model_id
        self.configured_capability_models = configured_capability_models

    @classmethod
    def for_missing_capabilities(
        cls,
        model_id: str,
        missing: set[str],
        configured_capability_models: dict[str, str] | None = None,
    ) -> "UnsupportedFeatureError":
        """
        Create an error for missing capabilities with helpful suggestions.

        Args:
            model_id: The model that doesn't support the required capabilities.
            missing: Set of capability names that are missing.
            configured_capability_models: Mapping of capability -> configured model name.

        Returns:
            UnsupportedFeatureError with a clear message.
        """
        missing_str = ", ".join(sorted(missing))

        # Build suggestion if capability models are configured
        suggestions = []
        if configured_capability_models:
            for cap in sorted(missing):
                if cap in configured_capability_models:
                    suggestions.append(f"  - {cap}: {configured_capability_models[cap]}")

        suggestion_str = ""
        if suggestions:
            suggestion_str = f"\n\nConfigured models for these capabilities:\n" + "\n".join(suggestions)

        message = (
            f"Model `{model_id}` does not support required capabilities: {missing_str}.\n\n"
            f"Remove the model pin or select a model that supports these capabilities."
            f"{suggestion_str}"
        )

        return cls(
            message=message,
            missing_capabilities=missing,
            model_id=model_id,
            configured_capability_models=configured_capability_models,
        )


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
