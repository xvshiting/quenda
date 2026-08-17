"""Buffered streaming preserves the synchronous Model contract."""

from __future__ import annotations

import asyncio
import threading

import pytest

from quenda.kernel.types import Message, StreamChunk, ToolCall, UsageStats
from quenda.providers.api.registry import ApiRegistry
from quenda.providers.errors import APIError, NetworkError
from quenda.providers.model import ModelSpec
from quenda.providers.observability import register_cancellation_callback
from quenda.providers.provider import Provider, ProviderSpec
from quenda.runtime import (
    AgentConfig,
    ModelResponded,
    ModelResponseDelta,
    Run,
    RunInterrupted,
    SessionState,
)
from quenda.runtime.cancellation import CancellationToken


class RecordingStreamingApi:
    def __init__(self) -> None:
        self.invoke_calls = 0
        self.stream_calls = 0
        self.max_retries: int | None = None

    def invoke(self, **kwargs):
        self.invoke_calls += 1
        raise AssertionError("streaming models must not use the blocking transport")

    def invoke_stream(self, **kwargs):
        self.stream_calls += 1
        self.max_retries = kwargs["max_retries"]
        yield StreamChunk(content="hello ")
        yield StreamChunk(content="world")
        yield StreamChunk(
            tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"q": "x"})],
            is_final=True,
            stop_reason="tool_use",
            usage=UsageStats(input_tokens=12, output_tokens=2),
        )


class TextStreamingApi(RecordingStreamingApi):
    def invoke_stream(self, **kwargs):
        self.stream_calls += 1
        self.max_retries = kwargs["max_retries"]
        yield StreamChunk(content="hello ")
        yield StreamChunk(content="world")
        yield StreamChunk(is_final=True, stop_reason="end_turn")


class InterruptedStreamingApi(RecordingStreamingApi):
    def invoke_stream(self, **kwargs):
        self.stream_calls += 1
        yield StreamChunk(content="partial")
        raise NetworkError("connection reset")


class CancellableStreamingApi(RecordingStreamingApi):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.closed = threading.Event()

    def invoke_stream(self, **kwargs):
        self.stream_calls += 1
        unregister = register_cancellation_callback(self.closed.set)
        try:
            self.started.set()
            yield StreamChunk(content="started")
            self.closed.wait(timeout=5)
            yield StreamChunk(content="must-not-be-visible")
        finally:
            unregister()


def _model(api: RecordingStreamingApi, *, streaming: bool = True, max_retries: int = 0):
    registry = ApiRegistry()
    registry.register("test-api", api)  # type: ignore[arg-type]
    spec = ModelSpec(id="test-model", name="Test Model", streaming=streaming)
    provider = Provider(
        ProviderSpec(
            id="test-provider",
            name="Test Provider",
            base_url="http://127.0.0.1:8080/v1",
            api="test-api",
            api_key="no-key",
            models=(spec,),
            max_retries=max_retries,
        ),
        api_registry=registry,
    )
    return provider.get_model("test-model")


def test_streaming_model_buffers_chunks_into_existing_response_contract() -> None:
    api = RecordingStreamingApi()

    response = _model(api).invoke([Message(role="user", content="hi")], tools=[])

    assert response.content == "hello world"
    assert response.stop_reason == "tool_use"
    assert response.tool_calls[0].name == "lookup"
    assert response.usage == UsageStats(input_tokens=12, output_tokens=2)
    assert api.stream_calls == 1
    assert api.invoke_calls == 0


def test_zero_max_retries_is_forwarded_to_streaming_transport() -> None:
    api = RecordingStreamingApi()

    _model(api, max_retries=0).invoke(
        [Message(role="user", content="hi")], tools=[]
    )

    assert api.max_retries == 0


@pytest.mark.asyncio
async def test_runtime_emits_deltas_before_the_final_response() -> None:
    model = _model(TextStreamingApi())
    run = Run.create(
        AgentConfig(name="stream-agent"),
        SessionState.create("stream-agent"),
        model,
    )

    events = await run.execute_to_completion("hi")

    deltas = [event.content for event in events if isinstance(event, ModelResponseDelta)]
    final_index = next(i for i, event in enumerate(events) if isinstance(event, ModelResponded))
    delta_indices = [i for i, event in enumerate(events) if isinstance(event, ModelResponseDelta)]
    assert deltas == ["hello ", "world"]
    assert max(delta_indices) < final_index


def test_stream_does_not_retry_after_visible_output() -> None:
    api = InterruptedStreamingApi()

    with pytest.raises(APIError, match="after output started"):
        _model(api, max_retries=3).invoke(
            [Message(role="user", content="hi")], tools=[]
        )

    assert api.stream_calls == 1


@pytest.mark.asyncio
async def test_cancelling_run_closes_active_stream_without_retrying() -> None:
    api = CancellableStreamingApi()
    token = CancellationToken()
    run = Run.create(
        AgentConfig(name="cancel-agent"),
        SessionState.create("cancel-agent"),
        _model(api),
        cancellation_token=token,
    )

    task = asyncio.create_task(run.execute_to_completion("hi"))
    assert await asyncio.to_thread(api.started.wait, 1)
    token.cancel()
    events = await asyncio.wait_for(task, timeout=1)

    assert api.closed.is_set()
    assert api.stream_calls == 1
    assert any(isinstance(event, RunInterrupted) for event in events)
    assert not any(
        isinstance(event, ModelResponseDelta)
        and event.content == "must-not-be-visible"
        for event in events
    )
