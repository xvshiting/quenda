"""
Provider registry for Kora.

The registry manages available providers and provides model lookup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quenda.providers.provider import Provider, ProviderSpec

if TYPE_CHECKING:
    from quenda.providers.auth import AuthResolver
    from quenda.providers.api.registry import ApiRegistry
    from quenda.providers.model import Model, ModelSpec


class ProviderRegistry:
    """
    Registry for providers.

    Manages provider configurations and provides lookup by provider ID
    and model ID.

    Usage:
        registry = ProviderRegistry()

        # Register a provider
        registry.register(ProviderSpec(
            id="dashscope",
            name="DashScope",
            base_url="https://...",
            models=(ModelSpec(id="qwen-max", name="Qwen Max"),),
        ))

        # Get a model
        model = registry.get_model("dashscope", "qwen-max")
    """

    def __init__(
        self,
        auth: AuthResolver | None = None,
        api_registry: ApiRegistry | None = None,
    ) -> None:
        self._specs: dict[str, ProviderSpec] = {}
        self._providers: dict[str, Provider] = {}
        self._auth = auth
        self._api_registry = api_registry

    def register(self, spec: ProviderSpec) -> None:
        """Register a provider specification."""
        self._specs[spec.id] = spec
        # Clear cached provider if exists
        if spec.id in self._providers:
            del self._providers[spec.id]

    def unregister(self, provider_id: str) -> bool:
        """Unregister a provider. Returns True if it existed."""
        if provider_id in self._specs:
            del self._specs[provider_id]
            self._providers.pop(provider_id, None)
            return True
        return False

    def get_provider(self, provider_id: str) -> Provider | None:
        """Get a provider by ID."""
        if provider_id not in self._specs:
            return None

        # Use cached provider if available
        if provider_id in self._providers:
            return self._providers[provider_id]

        # Create provider instance
        spec = self._specs[provider_id]
        provider = Provider(
            spec=spec,
            auth=self._auth,
            api_registry=self._api_registry,
        )
        self._providers[provider_id] = provider
        return provider

    def get_model(self, provider_id: str, model_id: str) -> Model:
        """
        Get a model by provider ID and model ID.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier

        Returns:
            Model instance

        Raises:
            KeyError: If provider or model not found
        """
        provider = self.get_provider(provider_id)
        if provider is None:
            available = list(self._specs.keys())
            raise KeyError(
                f"Provider '{provider_id}' not found. "
                f"Available providers: {available}"
            )
        return provider.get_model(model_id)

    def has_provider(self, provider_id: str) -> bool:
        """Check if a provider is registered."""
        return provider_id in self._specs

    def list_providers(self) -> list[str]:
        """List all registered provider IDs."""
        return list(self._specs.keys())

    def list_all_models(self) -> list[tuple[str, str]]:
        """List all (provider_id, model_id) pairs."""
        result = []
        for provider_id, spec in self._specs.items():
            for model in spec.models:
                result.append((provider_id, model.id))
        return result


# Global registry
_global_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    global _global_registry
    if _global_registry is None:
        from quenda.providers.api import get_api_registry
        _global_registry = ProviderRegistry(api_registry=get_api_registry())
        _register_default_providers(_global_registry)
    return _global_registry


def _register_default_providers(registry: ProviderRegistry) -> None:
    """Register built-in providers."""
    from quenda.providers.builtins import (
        AGNES_SPEC,
        ANTHROPIC_SPEC,
        CEREBRAS_SPEC,
        COHERE_SPEC,
        DASHSCOPE_SPEC,
        DEEPSEEK_ANTHROPIC_SPEC,
        DEEPSEEK_SPEC,
        FIREWORKS_SPEC,
        GOOGLE_SPEC,
        GROQ_SPEC,
        JDCLOUD_SPEC,
        MINIMAX_SPEC,
        MISTRAL_SPEC,
        MOONSHOT_SPEC,
        NVIDIA_SPEC,
        OLLAMA_SPEC,
        OPENAI_SPEC,
        OPENROUTER_SPEC,
        PERPLEXITY_SPEC,
        SILICONFLOW_SPEC,
        STEPFUN_SPEC,
        TENCENT_SPEC,
        TOGETHER_SPEC,
        VOLCENGINE_SPEC,
        XAI_SPEC,
        XIAOMI_SPEC,
        ZHIPU_SPEC,
    )

    registry.register(AGNES_SPEC)
    registry.register(ANTHROPIC_SPEC)
    registry.register(CEREBRAS_SPEC)
    registry.register(COHERE_SPEC)
    registry.register(DASHSCOPE_SPEC)
    registry.register(DEEPSEEK_SPEC)
    registry.register(DEEPSEEK_ANTHROPIC_SPEC)
    registry.register(FIREWORKS_SPEC)
    registry.register(GOOGLE_SPEC)
    registry.register(GROQ_SPEC)
    registry.register(JDCLOUD_SPEC)
    registry.register(MINIMAX_SPEC)
    registry.register(MISTRAL_SPEC)
    registry.register(MOONSHOT_SPEC)
    registry.register(NVIDIA_SPEC)
    registry.register(OLLAMA_SPEC)
    registry.register(OPENAI_SPEC)
    registry.register(OPENROUTER_SPEC)
    registry.register(PERPLEXITY_SPEC)
    registry.register(SILICONFLOW_SPEC)
    registry.register(STEPFUN_SPEC)
    registry.register(TENCENT_SPEC)
    registry.register(TOGETHER_SPEC)
    registry.register(VOLCENGINE_SPEC)
    registry.register(XAI_SPEC)
    registry.register(XIAOMI_SPEC)
    registry.register(ZHIPU_SPEC)
