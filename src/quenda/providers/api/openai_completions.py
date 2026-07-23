"""
OpenAI Completions API implementation.

This is the most common API protocol, used by:
- OpenAI (GPT-4, GPT-3.5)
- DashScope (Qwen)
- JDCloud Coding
- OpenRouter
- Local vLLM
- Most OpenAI-compatible services
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING, override

from quenda.kernel.types import Message, ModelResponse, StreamChunk, ToolCall, UsageStats
from quenda.kernel.tool import Tool
from quenda.providers.api.base import Api
from quenda.providers.api.converters import (
    convert_messages_to_openai,
    convert_tools_to_openai,
)
from quenda.providers.errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ToolCallDecodeError,
)
from quenda.providers.retry import retry_with_backoff

if TYPE_CHECKING:
    pass


class OpenAICompletionsApi(Api):
    """
    OpenAI chat completions API implementation.

    Handles communication with OpenAI-compatible endpoints.
    """

    @property
    def id(self) -> str:
        return "openai-completions"

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
        """Invoke the model via OpenAI completions API."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI-compatible APIs. "
                "Install with: pip install openai"
            )

        @retry_with_backoff(max_retries=max_retries)
        def _invoke() -> ModelResponse:
            # Build client
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout or 30.0,
                default_headers=headers if headers else None,
            )

            # Convert messages and tools
            openai_messages = convert_messages_to_openai(messages)
            openai_tools = convert_tools_to_openai(tools) if tools else None

            try:
                # Make request
                response = client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    tools=openai_tools,
                    tool_choice="auto" if openai_tools else None,
                )

                # Convert response
                return self._convert_response(response)

            except openai.RateLimitError as e:
                retry_after = None
                if hasattr(e, "response") and e.response is not None:
                    retry_after_str = e.response.headers.get("retry-after")
                    if retry_after_str:
                        try:
                            retry_after = float(retry_after_str)
                        except ValueError:
                            pass
                raise RateLimitError(str(e), retry_after=retry_after)

            except openai.APIConnectionError as e:
                raise NetworkError(f"Connection failed: {e}")

            except openai.AuthenticationError as e:
                raise AuthenticationError(f"Authentication failed: {e}")

            except openai.APIStatusError as e:
                if e.status_code == 401:
                    raise AuthenticationError(f"Authentication failed: {e}")
                elif e.status_code == 429:
                    raise RateLimitError(str(e))
                elif e.status_code >= 500:
                    raise APIError(f"Server error: {e}")
                else:
                    raise APIError(f"API error: {e}")

            except openai.APIError as e:
                raise APIError(f"OpenAI API error: {e}")

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
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI-compatible APIs. "
                "Install with: pip install openai"
            )

        # Build client
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout or 30.0,
            default_headers=headers if headers else None,
        )

        # Convert messages and tools
        openai_messages = convert_messages_to_openai(messages)
        openai_tools = convert_tools_to_openai(tools) if tools else None

        try:
            # Make streaming request
            stream = client.chat.completions.create(
                model=model,
                messages=openai_messages,
                tools=openai_tools,
                tool_choice="auto" if openai_tools else None,
                stream=True,
            )

            # Track tool calls across chunks
            tool_calls_buffer: dict[int, dict] = {}

            for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle content
                if delta.content:
                    yield StreamChunk(content=delta.content, is_final=False)

                # Handle reasoning_content (Kimi-K2.5 puts response here)
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    yield StreamChunk(content=delta.reasoning_content, is_final=False)

                # Handle tool calls (streamed incrementally)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index

                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc.id:
                            tool_calls_buffer[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                # Check for finish
                if chunk.choices[0].finish_reason:
                    # Yield final tool calls if any
                    if tool_calls_buffer:
                        final_tool_calls = []
                        for idx in sorted(tool_calls_buffer.keys()):
                            tc_data = tool_calls_buffer[idx]
                            args = self._decode_tool_arguments(
                                tc_data["arguments"],
                                tool_call_id=tc_data["id"],
                                tool_name=tc_data["name"],
                            )
                            final_tool_calls.append(
                                ToolCall(
                                    id=tc_data["id"],
                                    name=tc_data["name"],
                                    arguments=args,
                                )
                            )
                        yield StreamChunk(tool_calls=final_tool_calls, is_final=True)
                    else:
                        yield StreamChunk(is_final=True)

        except openai.RateLimitError as e:
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                retry_after_str = e.response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        pass
            raise RateLimitError(str(e), retry_after=retry_after)

        except openai.APIConnectionError as e:
            raise NetworkError(f"Connection failed: {e}")

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")

        except openai.APIStatusError as e:
            if e.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {e}")
            elif e.status_code == 429:
                raise RateLimitError(str(e))
            else:
                raise APIError(f"API error: {e}")

        except openai.APIError as e:
            raise APIError(f"OpenAI API error: {e}")

    def _convert_response(self, response) -> ModelResponse:
        """Convert OpenAI response to Quenda format."""
        choice = response.choices[0]
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = self._decode_tool_arguments(
                    tc.function.arguments,
                    tool_call_id=tc.id,
                    tool_name=tc.function.name,
                )
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        # Handle content - some models (like Kimi) put reasoning in reasoning_content
        content = choice.message.content
        if not content and hasattr(choice.message, 'reasoning_content'):
            # Kimi-K2.5 puts the actual response in reasoning_content
            content = choice.message.reasoning_content

        # Extract usage statistics
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = UsageStats(
                input_tokens=getattr(response.usage, 'prompt_tokens', 0) or 0,
                output_tokens=getattr(response.usage, 'completion_tokens', 0) or 0,
                cached_input_tokens=None,  # OpenAI doesn't expose this
                reasoning_tokens=getattr(response.usage, 'completion_tokens_details', None) and
                    getattr(response.usage.completion_tokens_details, 'reasoning_tokens', None),
            )

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage=usage,
        )

    def _decode_tool_arguments(
        self,
        raw_arguments: str | None,
        *,
        tool_call_id: str | None,
        tool_name: str | None,
    ) -> dict:
        """Decode provider tool-call arguments into a dict."""
        if not raw_arguments:
            return {}

        try:
            args = json.loads(raw_arguments)
        except json.JSONDecodeError as e:
            raise ToolCallDecodeError(
                f"Invalid JSON arguments for tool call `{tool_name or '<unknown>'}`: {e}",
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                raw_arguments=raw_arguments,
                error_position=e.pos,
            ) from e

        if not isinstance(args, dict):
            raise ToolCallDecodeError(
                f"Tool call `{tool_name or '<unknown>'}` arguments must decode to an object.",
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                raw_arguments=raw_arguments,
                error_position=None,
            )
        return args
