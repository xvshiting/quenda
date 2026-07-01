"""
Host-level follow-up phase coordination.

These helpers let Host run one or more hidden phases, inspect emitted
runtime events, and decide whether to continue with a synthetic
follow-up message or reveal the current phase to the user.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.kernel.model import Model
    from quenda.runtime.events import AnyEvent
    from quenda.runtime.session import Session


@dataclass(frozen=True)
class FollowupPhaseDecision:
    """
    Host decision after inspecting one collected phase.

    Attributes:
        next_message: Synthetic follow-up message for the next hidden phase.
            If None, the current phase becomes the visible result.
        rollback_to_checkpoint: Whether to discard messages written by the
            current hidden phase before continuing.
    """

    next_message: str | None = None
    rollback_to_checkpoint: bool = False


@dataclass(frozen=True)
class FollowupPhaseResult:
    """Result of running a follow-up phase sequence."""

    final_events: list[AnyEvent]
    phases_run: int
    hidden_phases: int
    completed: bool


def run_followup_phases(
    session: Session,
    initial_message: str,
    inspector: Callable[[list[AnyEvent]], FollowupPhaseDecision | None],
    *,
    model: Model | None = None,
    on_event: Callable[[AnyEvent], None] | None = None,
    max_phases: int = 5,
) -> FollowupPhaseResult:
    """
    Run one or more phases and let Host decide whether to continue.

    The initial phase and all follow-up phases are executed through the same
    Session. Intermediate phases may be rolled back so they do not remain in
    persisted conversation history.
    """
    checkpoint = session.checkpoint()
    pending_message = initial_message
    hidden_phases = 0
    final_events: list[AnyEvent] = []

    for phase_index in range(max_phases):
        _, events = session.send_collecting_sync(
            pending_message,
            model=model,
            on_event=on_event,
        )
        final_events = events

        decision = inspector(events)
        if decision is None or decision.next_message is None:
            return FollowupPhaseResult(
                final_events=final_events,
                phases_run=phase_index + 1,
                hidden_phases=hidden_phases,
                completed=True,
            )

        if decision.rollback_to_checkpoint:
            session.rollback_to(checkpoint)
        hidden_phases += 1
        pending_message = decision.next_message

    return FollowupPhaseResult(
        final_events=final_events,
        phases_run=max_phases,
        hidden_phases=hidden_phases,
        completed=False,
    )


__all__ = [
    "FollowupPhaseDecision",
    "FollowupPhaseResult",
    "run_followup_phases",
]
