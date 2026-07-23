"""
API registry for Quenda providers.

The registry manages available API implementations.
Multiple providers can share the same API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.providers.api.base import Api


class ApiRegistry:
    """
    Registry for API implementations.

    APIs are protocol implementations (e.g., OpenAI completions, Anthropic messages).
    Providers reference APIs by ID to handle actual communication.

    Usage:
        registry = ApiRegistry()
        registry.register("openai-completions", OpenAICompletionsApi())
        registry.register("anthropic-messages", AnthropicMessagesApi())

        api = registry.get("openai-completions")
    """

    def __init__(self) -> None:
        self._apis: dict[str, Api] = {}

    def register(self, api_id: str, api: Api) -> None:
        """Register an API implementation."""
        self._apis[api_id] = api

    def get(self, api_id: str) -> Api | None:
        """Get an API by ID."""
        return self._apis.get(api_id)

    def has(self, api_id: str) -> bool:
        """Check if an API is registered."""
        return api_id in self._apis

    def list(self) -> list[str]:
        """List all registered API IDs."""
        return list(self._apis.keys())

    def unregister(self, api_id: str) -> bool:
        """Unregister an API. Returns True if it existed."""
        if api_id in self._apis:
            del self._apis[api_id]
            return True
        return False


# Global registry
_global_registry: ApiRegistry | None = None


def get_api_registry() -> ApiRegistry:
    """Get the global API registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = build_default_api_registry()
    return _global_registry


def build_default_api_registry() -> ApiRegistry:
    """Build a fresh API registry with built-in implementations."""
    registry = ApiRegistry()
    register_default_apis(registry)
    return registry


def register_default_apis(registry: ApiRegistry) -> None:
    """Register built-in API implementations."""
    from quenda.providers.api.openai_completions import OpenAICompletionsApi
    from quenda.providers.api.anthropic_messages import AnthropicMessagesApi
    from quenda.providers.api.my_kimi_completions import MyKimiCompletionsApi

    registry.register("openai-completions", OpenAICompletionsApi())
    registry.register("anthropic-messages", AnthropicMessagesApi())
    registry.register("my-kimi-completions", MyKimiCompletionsApi())


_register_default_apis = register_default_apis


__all__ = [
    "ApiRegistry",
    "build_default_api_registry",
    "get_api_registry",
    "register_default_apis",
]
