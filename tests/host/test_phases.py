"""Tests for Host follow-up phase coordination."""

from dataclasses import dataclass, field

from quenda.host.phases import (
    FollowupPhaseDecision,
    run_followup_phases,
)
from quenda.runtime.events import ModelResponded, RunCompleted, RunStarted


@dataclass
class FakeSession:
    """Small fake session for follow-up phase tests."""

    phases: list[list]
    send_calls: list[str] = field(default_factory=list)
    checkpoint_value: int = 0
    rollback_calls: list[int] = field(default_factory=list)

    def checkpoint(self) -> int:
        return self.checkpoint_value

    def rollback_to(self, checkpoint: int) -> None:
        self.rollback_calls.append(checkpoint)

    def send_collecting_sync(self, message: str, *, model=None, on_event=None) -> tuple[str, list]:
        self.send_calls.append(message)
        events = self.phases[len(self.send_calls) - 1]
        if on_event is not None:
            for event in events:
                on_event(event)
        final = ""
        for event in events:
            if isinstance(event, RunCompleted) and event.final_content:
                final = event.final_content
        return final, events


class TestRunFollowupPhases:
    """Tests for the generic follow-up phase coordinator."""

    def test_returns_first_visible_phase_when_no_followup(self) -> None:
        session = FakeSession(phases=[[
            RunStarted(user_message="hello"),
            ModelResponded(content="hello back"),
            RunCompleted(final_content="hello back"),
        ]])

        result = run_followup_phases(session, "hello", lambda events: None)

        assert result.completed is True
        assert result.phases_run == 1
        assert result.hidden_phases == 0
        assert session.send_calls == ["hello"]
        assert session.rollback_calls == []

    def test_rolls_back_hidden_phase_and_continues(self) -> None:
        session = FakeSession(phases=[
            [
                RunStarted(user_message="first"),
                ModelResponded(
                    content="intermediate",
                    tool_call_details=[{
                        "id": "call_1",
                        "name": "request_skill_activation",
                        "arguments": {"skill_name": "code-review"},
                    }],
                ),
                RunCompleted(final_content="intermediate"),
            ],
            [
                RunStarted(user_message="followup"),
                ModelResponded(content="final answer"),
                RunCompleted(final_content="final answer"),
            ],
        ])

        def inspector(events: list) -> FollowupPhaseDecision | None:
            first_model = next(
                (event for event in events if isinstance(event, ModelResponded)),
                None,
            )
            if first_model and first_model.tool_call_details:
                return FollowupPhaseDecision(
                    next_message="followup",
                    rollback_to_checkpoint=True,
                )
            return None

        result = run_followup_phases(session, "first", inspector)

        assert result.completed is True
        assert result.phases_run == 2
        assert result.hidden_phases == 1
        assert session.send_calls == ["first", "followup"]
        assert session.rollback_calls == [0]
        assert any(
            isinstance(event, RunCompleted) and event.final_content == "final answer"
            for event in result.final_events
        )

    def test_forwards_events_to_optional_handler(self) -> None:
        session = FakeSession(phases=[[
            RunStarted(user_message="hello"),
            ModelResponded(content="hello back"),
            RunCompleted(final_content="hello back"),
        ]])
        seen: list[str] = []

        result = run_followup_phases(
            session,
            "hello",
            lambda events: None,
            on_event=lambda event: seen.append(event.type),
        )

        assert result.completed is True
        assert seen == ["run_started", "model_responded", "run_completed"]
