"""
Provider specification for Kora.

A Provider represents a model service provider (e.g., DashScope, JDCloud, OpenRouter).
It owns authentication, base URL, and a list of available models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from kora.providers.model import ModelSpec

if TYPE_CHECKING:
    from kora.providers.api.registry import ApiRegistry
    from kora.providers.auth import AuthResolver
    from kora.providers.model import Model


@dataclass(frozen=True)
class ProviderSpec:
    """
    Configuration specification for a Provider.

    This is a pure data class that can be loaded from:
    - Python code
    - YAML/JSON configuration
    - Plugin discovery
    - Dynamic model discovery

    Attributes:
        id: Unique provider identifier (e.g., "dashscope", "jdcloud")
        name: Human-readable name (e.g., "DashScope", "JD Cloud")
        base_url: API base URL
        api: Default API protocol (e.g., "openai-completions")
        api_key: API key (can be env var pattern like "${DASHSCOPE_API_KEY}")
        headers: Additional headers for all requests
        models: List of models offered by this provider
        timeout: Default request timeout in seconds
        max_retries: Maximum retry attempts
    """

    # Identity
    id: str
    name: str

    # Connection
    base_url: str
    api: str = "openai-completions"

    # Authentication
    api_key: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)

    # Models
    models: tuple[ModelSpec, ...] = ()

    # Settings
    timeout: float | None = None
    max_retries: int | None = None

    # Metadata
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ProviderSpec(id={self.id!r}, name={self.name!r}, models={len(self.models)})"


class Provider:
    """
    Runtime Provider that wraps ProviderSpec with authentication resolution.

    A Provider is responsible for:
    - Managing authentication
    - Providing access to models
    - Resolving effective API configuration for each model

    Usage:
        provider = Provider(spec, auth_resolver, api_registry)
        model = provider.get_model("qwen-max")
        response = model.invoke(messages, tools=tools)
    """

    def __init__(
        self,
        spec: ProviderSpec,
        auth: AuthResolver | None = None,
        api_registry: ApiRegistry | None = None,
    ) -> None:
        from kora.providers.auth import EnvAuthResolver

        self.spec = spec
        self.auth = auth or EnvAuthResolver()
        self._api_registry = api_registry

        # Build model lookup
        self._models: dict[str, ModelSpec] = {
            model.id: model for model in spec.models
        }

    @property
    def id(self) -> str:
        """Provider ID."""
        return self.spec.id

    @property
    def name(self) -> str:
        """Provider name."""
        return self.spec.name

    def get_model(self, model_id: str) -> Model:
        """
        Get a model by ID.

        Args:
            model_id: The model identifier (e.g., "qwen-max")

        Returns:
            A Model instance bound to this provider.

        Raises:
            KeyError: If model_id not found in this provider.
        """
        from kora.providers.model import Model

        if model_id not in self._models:
            available = list(self._models.keys())
            raise KeyError(
                f"Model '{model_id}' not found in provider '{self.id}'. "
                f"Available models: {available}"
            )

        spec = self._models[model_id]
        return Model(provider=self, spec=spec)

    def list_models(self) -> list[ModelSpec]:
        """List all models offered by this provider."""
        return list(self._models.values())

    def has_model(self, model_id: str) -> bool:
        """Check if a model is available."""
        return model_id in self._models

    def resolve_api(self, model: ModelSpec) -> str:
        """Resolve the effective API protocol for a model."""
        return model.api or self.spec.api

    def resolve_base_url(self, model: ModelSpec) -> str:
        """Resolve the effective base URL for a model."""
        return model.base_url or self.spec.base_url

    def resolve_headers(self, model: ModelSpec) -> dict[str, str]:
        """Resolve effective headers for a model."""
        return {**self.spec.headers, **model.headers}

    def resolve_api_key(self) -> str | None:
        """
        Resolve the API key.

        Returns:
            The resolved API key value, or None if not configured.

        Raises:
            AuthenticationError: If API key is configured but environment variable is not set.
        """
        if not self.spec.api_key:
            return None

        resolved = self.auth.resolve(self.spec.api_key)
        if resolved is None:
            # Extract env var name from pattern like "${DEEPSEEK_API_KEY}"
            from kora.providers.errors import AuthenticationError

            if self.spec.api_key.startswith("${") and self.spec.api_key.endswith("}"):
                env_var = self.spec.api_key[2:-1]
                raise AuthenticationError(
                    f"API key not found for provider '{self.id}'. "
                    f"Please set the environment variable: export {env_var}='your-api-key'"
                )
            else:
                raise AuthenticationError(
                    f"API key not found for provider '{self.id}'. "
                    f"Please configure a valid API key."
                )

        return resolved

    def __repr__(self) -> str:
        return f"Provider(id={self.id!r}, models={len(self._models)})"
