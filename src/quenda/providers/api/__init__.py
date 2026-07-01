"""
API implementations for Quenda providers.
"""

from quenda.providers.api.base import Api
from quenda.providers.api.registry import ApiRegistry, get_api_registry
from quenda.providers.api.openai_completions import OpenAICompletionsApi
from quenda.providers.api.anthropic_messages import AnthropicMessagesApi
from quenda.providers.api.converters import (
    convert_messages_to_openai,
    convert_tools_to_openai,
)

__all__ = [
    "Api",
    "ApiRegistry",
    "get_api_registry",
    "OpenAICompletionsApi",
    "AnthropicMessagesApi",
    "convert_messages_to_openai",
    "convert_tools_to_openai",
]
