"""
Anthropic Messages API implementation.

This implements the Anthropic Claude API protocol, which has some key
differences from OpenAI's API:
- System message is a separate parameter, not in messages
- Tool calls use content blocks
- max_tokens is required
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING, override

from quenda.kernel.types import Message, ModelResponse, StreamChunk, ToolCall, UsageStats
from quenda.kernel.tool import Tool
from quenda.providers.api.base import Api
from quenda.providers.errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from quenda.providers.retry import retry_with_backoff

if TYPE_CHECKING:
    pass


class AnthropicMessagesApi(Api):
    """
    Anthropic Messages API implementation.

    Handles communication with Anthropic's Claude API.
    """

    @property
    def id(self) -> str:
        return "anthropic-messages"

    @override
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
        """Invoke the model via Anthropic Messages API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for Anthropic API. "
                "Install with: pip install anthropic"
            )

        @retry_with_backoff(max_retries=max_retries)
        def _invoke() -> ModelResponse:
            # Build client
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url if base_url != "https://api.anthropic.com/v1" else None,
                timeout=timeout or 30.0,
                default_headers=headers if headers else None,
            )

            # Convert messages to Anthropic format
            anthropic_messages, system = self._convert_messages(messages)

            # Convert tools
            anthropic_tools = self._convert_tools(tools) if tools else None

            # Build request kwargs
            request_kwargs = {
                "model": model,
                "max_tokens": 4096,
                "messages": anthropic_messages,
            }

            if system:
                request_kwargs["system"] = system

            if anthropic_tools:
                request_kwargs["tools"] = anthropic_tools

            try:
                response = client.messages.create(**request_kwargs)
                return self._convert_response(response)

            except anthropic.RateLimitError as e:
                raise RateLimitError(str(e))

            except anthropic.AuthenticationError as e:
                raise AuthenticationError(f"Authentication failed: {e}")

            except anthropic.APIConnectionError as e:
                raise NetworkError(f"Connection failed: {e}")

            except anthropic.APIStatusError as e:
                if e.status_code == 401:
                    raise AuthenticationError(f"Authentication failed: {e}")
                elif e.status_code == 429:
                    raise RateLimitError(str(e))
                else:
                    raise APIError(f"API error: {e}")

            except anthropic.APIError as e:
                raise APIError(f"Anthropic API error: {e}")

        return _invoke()

    @override
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
        """Invoke the model with streaming response."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for Anthropic API. "
                "Install with: pip install anthropic"
            )

        # Build client
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.anthropic.com/v1" else None,
            timeout=timeout or 30.0,
            default_headers=headers if headers else None,
        )

        # Convert messages
        anthropic_messages, system = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools) if tools else None

        # Build request kwargs
        request_kwargs = {
            "model": model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
        }

        if system:
            request_kwargs["system"] = system

        if anthropic_tools:
            request_kwargs["tools"] = anthropic_tools

        try:
            with client.messages.stream(**request_kwargs) as stream:
                for text in stream.text_stream:
                    yield StreamChunk(content=text, is_final=False)

                # Get final message for tool calls
                final_message = stream.get_final_message()
                tool_calls = self._extract_tool_calls(final_message)

                if tool_calls:
                    yield StreamChunk(tool_calls=tool_calls, is_final=True)
                else:
                    yield StreamChunk(is_final=True)

        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e))

        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")

        except anthropic.APIConnectionError as e:
            raise NetworkError(f"Connection failed: {e}")

        except anthropic.APIStatusError as e:
            if e.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {e}")
            elif e.status_code == 429:
                raise RateLimitError(str(e))
            else:
                raise APIError(f"API error: {e}")

        except anthropic.APIError as e:
            raise APIError(f"Anthropic API error: {e}")

    def _convert_messages(
        self,
        messages: list[Message],
    ) -> tuple[list[dict], str | None]:
        """
        Convert Kora messages to Anthropic format.

        Returns:
            Tuple of (anthropic_messages, system_prompt)
        """
        anthropic_messages = []
        system_prompt = None

        for msg in messages:
            if msg.role == "system":
                # System message goes as separate parameter
                if isinstance(msg.content, str):
                    system_prompt = msg.content
                continue

            if isinstance(msg.content, str):
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            else:
                # Handle tool calls and results
                items = list(msg.content)

                if items and hasattr(items[0], "__class__"):
                    item_type = items[0].__class__.__name__

                    if item_type == "ToolCall":
                        # Assistant message with tool calls
                        content_blocks = []
                        for tc in items:
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            })
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": content_blocks,
                        })

                        # Add tool result placeholders
                        for tc in items:
                            anthropic_messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tc.id,
                                    "content": "",
                                }],
                            })

                    elif item_type == "ToolResult":
                        # Tool results
                        content_blocks = []
                        for tr in items:
                            content_blocks.append({
                                "type": "tool_result",
                                "tool_use_id": tr.call_id,
                                "content": tr.content,
                                "is_error": tr.is_error,
                            })
                        anthropic_messages.append({
                            "role": "user",
                            "content": content_blocks,
                        })

        return anthropic_messages, system_prompt

    def _convert_tools(self, tools: list[Tool]) -> list[dict]:
        """Convert Kora tools to Anthropic format."""
        converted_tools = []
        for tool in tools:
            # Inject _summary parameter into the schema
            parameters = dict(tool.parameters)

            if "properties" not in parameters:
                parameters["properties"] = {}

            # Add _summary parameter
            parameters["properties"]["_summary"] = {
                "type": "string",
                "description": "Brief description of what this tool call is doing (e.g., 'reading config file', 'running tests'). Shown to user for visibility.",
            }

            converted_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": parameters,
            })

        return converted_tools

    def _convert_response(self, response) -> ModelResponse:
        """Convert Anthropic response to Kora format."""
        tool_calls = []
        content = None

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        # Determine stop reason
        stop_reason = "end_turn"
        if tool_calls:
            stop_reason = "tool_use"
        elif response.stop_reason == "max_tokens":
            stop_reason = "max_tokens"

        # Extract usage statistics
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = UsageStats(
                input_tokens=getattr(response.usage, 'input_tokens', 0) or 0,
                output_tokens=getattr(response.usage, 'output_tokens', 0) or 0,
                cached_input_tokens=getattr(response.usage, 'cache_read_input_tokens', None),
                reasoning_tokens=None,  # Anthropic doesn't expose this directly
            )

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
        )

    def _extract_tool_calls(self, message) -> list[ToolCall]:
        """Extract tool calls from Anthropic message."""
        tool_calls = []

        for block in message.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        return tool_calls
