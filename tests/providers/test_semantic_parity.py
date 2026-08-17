"""Golden semantics shared by OpenAI and Anthropic transport adapters."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from quenda.kernel.types import Message
from quenda.providers.api.anthropic_messages import AnthropicMessagesApi
from quenda.providers.api.openai_completions import OpenAICompletionsApi


class _AnthropicError(Exception):
    pass


def test_system_summary_and_resource_blocks_keep_the_same_order() -> None:
    messages = [
        Message(role="system", content="framework instructions"),
        Message(role="system", content="compressed summary"),
        Message(role="system", content="resource context"),
        Message(role="user", content="hello"),
    ]
    openai_request: dict[str, object] = {}
    anthropic_request: dict[str, object] = {}

    def openai_create(**kwargs: object) -> SimpleNamespace:
        openai_request.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="ok", tool_calls=None),
                finish_reason="stop",
            )],
            usage=None,
        )

    openai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=openai_create))
    )
    with patch("openai.OpenAI", return_value=openai_client):
        OpenAICompletionsApi().invoke(
            base_url="https://openai.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=messages,
            tools=[],
            timeout=30,
            max_retries=0,
        )

    def anthropic_create(**kwargs: object) -> SimpleNamespace:
        anthropic_request.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=None,
        )

    anthropic_client = SimpleNamespace(
        messages=SimpleNamespace(create=anthropic_create)
    )
    anthropic_sdk = SimpleNamespace(
        Anthropic=lambda **_kwargs: anthropic_client,
        RateLimitError=_AnthropicError,
        AuthenticationError=_AnthropicError,
        APIConnectionError=_AnthropicError,
        APIStatusError=_AnthropicError,
        APIError=_AnthropicError,
    )
    with patch.dict(sys.modules, {"anthropic": anthropic_sdk}):
        AnthropicMessagesApi().invoke(
            base_url="https://anthropic.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=messages,
            tools=[],
            timeout=30,
            max_retries=0,
        )

    expected = [
        "framework instructions",
        "compressed summary",
        "resource context",
    ]
    assert [
        item["content"]
        for item in openai_request["messages"]  # type: ignore[index,union-attr]
        if item["role"] == "system"
    ] == expected
    assert anthropic_request["system"] == "\n\n".join(expected)
