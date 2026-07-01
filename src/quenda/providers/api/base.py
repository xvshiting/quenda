"""
Base API protocol for Quenda providers.

An API defines the communication protocol (e.g., OpenAI completions, Anthropic messages).
Multiple providers can share the same API implementation.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from quenda.kernel.tool import Tool
    from quenda.kernel.types import Message, ModelResponse, StreamChunk


class Api(Protocol):
    """
    Protocol for API implementations.

    An API handles the actual communication with a model service.
    Providers delegate to APIs based on the configured protocol.

    Common APIs:
    - openai-completions: OpenAI chat completions API
    - openai-responses: OpenAI responses API
    - anthropic-messages: Anthropic messages API
    """

    @property
    def id(self) -> str:
        """API identifier (e.g., "openai-completions")."""
        ...

    def invoke(
        self,
        *,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str],
        model: str,
        messages: list[Message],
        tools: list[Tool],
        timeout: float | None,
        max_retries: int = 3,
    ) -> ModelResponse:
        """
        Invoke the model synchronously.

        Args:
            base_url: API base URL
            api_key: API key for authentication
            headers: Additional headers
            model: Model identifier
            messages: Conversation history
            tools: Available tools
            timeout: Request timeout
            max_retries: Maximum retry attempts for transient errors

        Returns:
            ModelResponse with content and/or tool calls
        """
        ...

    def invoke_stream(
        self,
        *,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str],
        model: str,
        messages: list[Message],
        tools: list[Tool],
        timeout: float | None,
        max_retries: int = 3,
    ) -> Generator[StreamChunk, None, None]:
        """
        Invoke the model with streaming response.

        Args:
            base_url: API base URL
            api_key: API key for authentication
            headers: Additional headers
            model: Model identifier
            messages: Conversation history
            tools: Available tools
            timeout: Request timeout
            max_retries: Maximum retry attempts for transient errors

        Yields:
            StreamChunk objects containing partial responses
        """
        ...
