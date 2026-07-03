"""
Provider Tool Codec Protocol.

Defines the bidirectional conversion between Quenda's internal tool format
and provider-specific formats.

## Architecture

Quenda Internal Format (clean, stable):
- Message(role="assistant", content=[ToolCall(...)])
- Message(role="user", content=[ToolResult(...)])

Provider Format (varies by provider):
- OpenAI: native tool_calls / tool messages
- Anthropic: native tool_use / tool_result blocks
- Kimi-style: JSON in content text

The codec is responsible for:
1. Outbound: Encode Quenda tool calls/results into provider-compatible format
2. Inbound: Decode provider response into Quenda tool calls/content

## Design Principle

The outbound format should "teach" the model what format to output.
For text-based providers, the historical tool calls should look like
what we want the model to output next.

Example for my-kimi-completions:
- Outbound assistant tool call -> JSON: {"name": "read_file", "arguments": {...}}
- Inbound JSON response -> ToolCall
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from quenda.kernel.types import Message, ModelResponse, ToolCall, ToolResult
from quenda.kernel.tool import Tool

if TYPE_CHECKING:
    pass


@dataclass
class EncodedMessage:
    """
    A message encoded for a specific provider.

    This is the format sent to the provider's API.
    """
    role: str
    content: str | None
    # For providers that support native tool calls
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    # Additional provider-specific fields
    extra: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API serialization."""
        result = {"role": self.role}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.extra:
            result.update(self.extra)
        return result


class ProviderToolCodec(ABC):
    """
    Abstract base class for provider tool codecs.

    A codec handles bidirectional conversion between Quenda's internal
    tool format and provider-specific formats.

    Responsibilities:
    1. encode_history: Convert Quenda messages to provider format
    2. decode_response: Convert provider response to Quenda format

    For standard providers (OpenAI, Anthropic), the codec can be thin
    since they support native tool calling.

    For non-standard providers (Kimi-style), the codec manages a
    text-based tool calling protocol.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for this codec."""
        ...

    @abstractmethod
    def encode_history(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
    ) -> list[EncodedMessage]:
        """
        Encode Quenda messages for the provider.

        This converts Quenda's internal format (ToolCall/ToolResult in content)
        into the format the provider expects.

        For text-based providers, the encoded format should "teach" the model
        what format to output. Historical tool calls should look like what
        we want the model to output next.

        Args:
            messages: Quenda messages to encode
            tools: Available tools (for generating tool descriptions)

        Returns:
            List of provider-compatible messages
        """
        ...

    @abstractmethod
    def decode_response(
        self,
        content: str | None,
        native_tool_calls: list[dict] | None = None,
        tools: list[Tool] | None = None,
    ) -> ModelResponse:
        """
        Decode provider response into Quenda format.

        This converts the provider's response (either native tool_calls
        or text content) into Quenda's ModelResponse with ToolCall objects.

        Args:
            content: The text content from the provider's response
            native_tool_calls: Native tool calls if provider supports them
            tools: Available tools (for validation and argument parsing)

        Returns:
            Quenda ModelResponse with content and/or tool_calls
        """
        ...

    def get_tool_instructions(self, tools: list[Tool]) -> str | None:
        """
        Generate tool usage instructions for the system prompt.

        For text-based providers, this injects instructions about how
        to format tool calls in the output.

        For native-tool providers, this can return None since the
        provider handles tool calling natively.

        Args:
            tools: Available tools

        Returns:
            Tool instructions string, or None if not needed
        """
        return None
