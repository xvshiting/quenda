"""Behavioral tests for the Anthropic Messages transport boundary."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from quenda.kernel.types import Message, ToolCall, ToolResult
from quenda.providers.api.anthropic_messages import AnthropicMessagesApi


class _AnthropicError(Exception):
    """Stand-in for the optional SDK's exception hierarchy."""


def test_invoke_preserves_every_system_instruction_block_in_order() -> None:
    """Provider-specific wire formatting must not discard Runtime context."""
    request: dict[str, object] = {}

    def create(**kwargs: object) -> SimpleNamespace:
        request.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=None,
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    anthropic = SimpleNamespace(
        Anthropic=lambda **_kwargs: client,
        RateLimitError=_AnthropicError,
        AuthenticationError=_AnthropicError,
        APIConnectionError=_AnthropicError,
        APIStatusError=_AnthropicError,
        APIError=_AnthropicError,
    )

    with patch.dict(sys.modules, {"anthropic": anthropic}):
        AnthropicMessagesApi().invoke(
            base_url="https://api.anthropic.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=[
                Message(role="system", content="framework instructions"),
                Message(role="system", content="compressed summary"),
                Message(role="system", content="resource context"),
                Message(role="user", content="hello"),
            ],
            tools=[],
            timeout=30,
            max_retries=0,
        )

    assert request["system"] == (
        "framework instructions\n\ncompressed summary\n\nresource context"
    )


def test_invoke_normalizes_anthropic_cache_usage_to_total_input() -> None:
    def create(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=SimpleNamespace(
                input_tokens=20,
                cache_read_input_tokens=70,
                cache_creation_input_tokens=10,
                output_tokens=15,
            ),
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    anthropic = SimpleNamespace(
        Anthropic=lambda **_kwargs: client,
        RateLimitError=_AnthropicError,
        AuthenticationError=_AnthropicError,
        APIConnectionError=_AnthropicError,
        APIStatusError=_AnthropicError,
        APIError=_AnthropicError,
    )

    with patch.dict(sys.modules, {"anthropic": anthropic}):
        result = AnthropicMessagesApi().invoke(
            base_url="https://api.anthropic.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=[Message(role="user", content="hello")],
            tools=[],
            timeout=30,
            max_retries=0,
        )

    assert result.usage is not None
    assert result.usage.input_tokens == 100
    assert result.usage.cached_input_tokens == 70
    assert result.usage.cache_creation_input_tokens == 10


def test_invoke_sends_each_tool_result_once_with_its_real_content() -> None:
    """A replayed tool call must not be paired with a synthetic empty result."""
    request: dict[str, object] = {}

    def create(**kwargs: object) -> SimpleNamespace:
        request.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=None,
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    anthropic = SimpleNamespace(
        Anthropic=lambda **_kwargs: client,
        RateLimitError=_AnthropicError,
        AuthenticationError=_AnthropicError,
        APIConnectionError=_AnthropicError,
        APIStatusError=_AnthropicError,
        APIError=_AnthropicError,
    )

    with patch.dict(sys.modules, {"anthropic": anthropic}):
        AnthropicMessagesApi().invoke(
            base_url="https://api.anthropic.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=[
                Message(role="user", content="inspect status"),
                Message(
                    role="assistant",
                    content=[ToolCall(id="call-1", name="status", arguments={})],
                ),
                Message(
                    role="user",
                    content=[
                        ToolResult(
                            call_id="call-1",
                            name="status",
                            content="ready",
                        )
                    ],
                ),
            ],
            tools=[],
            timeout=30,
            max_retries=0,
        )

    assert request["messages"] == [
        {"role": "user", "content": "inspect status"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "status",
                    "input": {},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "content": "ready",
                    "is_error": False,
                }
            ],
        },
    ]
