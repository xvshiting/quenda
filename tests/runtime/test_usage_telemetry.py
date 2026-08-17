"""Provider usage remains observable after Runtime aggregation."""

from __future__ import annotations

import pytest

from quenda.kernel import Message, ModelResponse, Tool
from quenda.kernel.types import UsageStats
from quenda.runtime import AgentConfig, ModelResponded, Run, SessionState


class UsageModel:
    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        return ModelResponse(
            content="done",
            usage=UsageStats(
                input_tokens=100,
                output_tokens=20,
                cached_input_tokens=70,
                cache_creation_input_tokens=10,
                reasoning_tokens=5,
            ),
        )


@pytest.mark.asyncio
async def test_model_event_and_session_keep_cache_usage() -> None:
    session = SessionState.create("usage-agent")
    run = Run.create(AgentConfig(name="usage-agent"), session, UsageModel())  # type: ignore[arg-type]

    events = await run.execute_to_completion("hello")
    responded = next(event for event in events if isinstance(event, ModelResponded))

    assert responded.input_tokens == 100
    assert responded.cached_input_tokens == 70
    assert responded.cache_creation_input_tokens == 10
    assert responded.reasoning_tokens == 5
    assert session.usage.total_input_tokens == 100
    assert session.usage.total_cached_input_tokens == 70
    assert session.usage.total_cache_creation_input_tokens == 10
    assert session.usage.total_tokens == 120
