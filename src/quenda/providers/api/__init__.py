"""
API implementations for Quenda providers.
"""

from quenda.providers.api.base import Api
from quenda.providers.api.registry import (
    ApiRegistry,
    build_default_api_registry,
    get_api_registry,
    register_default_apis,
)
from quenda.providers.api.openai_completions import OpenAICompletionsApi
from quenda.providers.api.anthropic_messages import AnthropicMessagesApi
from quenda.providers.api.converters import (
    convert_messages_to_openai,
    convert_tools_to_openai,
)

__all__ = [
    "Api",
    "ApiRegistry",
    "build_default_api_registry",
    "get_api_registry",
    "register_default_apis",
    "OpenAICompletionsApi",
    "AnthropicMessagesApi",
    "convert_messages_to_openai",
    "convert_tools_to_openai",
]
