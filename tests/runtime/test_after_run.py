"""Runtime contract for isolated after-Run Host maintenance."""

import pytest

from quenda.kernel.types import Message, ModelResponse
from quenda.runtime.agent import Agent
from quenda.runtime.events import EvolutionCompleted, EvolutionFailed


class StaticModel:
    def invoke(self, messages: list[Message], *, tools: list[object]) -> ModelResponse:
        return ModelResponse(content="done")


class RecordingHandler:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def process(self, context):
        self.calls += 1
        if self.fail:
            raise RuntimeError("maintenance unavailable")
        return [EvolutionCompleted(triggered=True, committed_count=1)]


@pytest.mark.asyncio
async def test_successful_run_invokes_after_run_handler_and_emits_event() -> None:
    handler = RecordingHandler()
    agent = Agent("test", model=StaticModel(), after_run_handler=handler)
    session = agent.open_session()
    events = []

    result = await session.send("hello", on_event=events.append)

    assert result == "done"
    assert handler.calls == 1
    assert isinstance(events[-1], EvolutionCompleted)
    assert events[-1].run_id


@pytest.mark.asyncio
async def test_after_run_failure_is_observable_but_does_not_fail_run() -> None:
    handler = RecordingHandler(fail=True)
    agent = Agent("test", model=StaticModel(), after_run_handler=handler)
    session = agent.open_session()
    events = []

    result = await session.send("hello", on_event=events.append)

    assert result == "done"
    assert isinstance(events[-1], EvolutionFailed)
    assert events[-1].error_message == "maintenance unavailable"
