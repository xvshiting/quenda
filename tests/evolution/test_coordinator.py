"""Behavior tests for the post-Run evolution seam."""

from pathlib import Path

import pytest

from quenda.evolution import (
    DefaultEvolutionTriggerPolicy,
    EvolutionTriggerConfig,
    MemoryEvolutionCoordinator,
    MemoryEvolutionPolicy,
    MemoryEvolutionStore,
    MemoryProposal,
    MemoryTarget,
    MemoryWriteMode,
)
from quenda.kernel.types import Message
from quenda.runtime.events import RunCompleted
from quenda.runtime.ports.after_run import AfterRunContext
from quenda.runtime.session import SessionState


class StaticGenerator:
    def __init__(self, proposals: list[MemoryProposal]) -> None:
        self.proposals = proposals
        self.calls = 0

    def generate(self, context: AfterRunContext) -> list[MemoryProposal]:
        self.calls += 1
        return self.proposals


def context_with_user_message(text: str, *, turns: int = 1) -> AfterRunContext:
    state = SessionState.create("test-agent", session_id="session-1")
    for index in range(turns):
        state.messages.extend(
            [
                Message(role="user", content=text if index == turns - 1 else "hello"),
                Message(role="assistant", content="response"),
            ]
        )
    return AfterRunContext(
        session_id=state.id,
        agent_name=state.agent_name,
        messages=tuple(state.messages),
        completed=RunCompleted(
            run_id="run-1",
            session_id=state.id,
            final_content="response",
        ),
    )


def test_default_trigger_uses_explicit_signal_or_periodic_turn() -> None:
    policy = DefaultEvolutionTriggerPolicy(
        EvolutionTriggerConfig(every_n_user_turns=5)
    )

    assert policy.should_trigger(context_with_user_message("请记住我喜欢简洁回答"))
    assert policy.should_trigger(context_with_user_message("ordinary", turns=5))
    assert not policy.should_trigger(context_with_user_message("ordinary", turns=4))


@pytest.mark.asyncio
async def test_automatic_mode_commits_high_confidence_proposal(
    tmp_path: Path,
) -> None:
    store = MemoryEvolutionStore(tmp_path)
    proposal = MemoryProposal(
        target=MemoryTarget.USER_PROFILE,
        proposed_content="# User\n\n- Prefer concise answers.\n",
        reason="Explicit preference",
        confidence=0.95,
    )
    generator = StaticGenerator([proposal])
    coordinator = MemoryEvolutionCoordinator(store, generator)

    events = await coordinator.process(
        context_with_user_message("Please remember that I prefer concise answers")
    )

    assert (tmp_path / "USER.md").read_text(encoding="utf-8") == (
        proposal.proposed_content
    )
    assert events[0].committed_count == 1
    assert events[0].staged_count == 0
    assert store.history()[0].automatic is True


@pytest.mark.asyncio
async def test_review_mode_stages_without_mutating_target(tmp_path: Path) -> None:
    store = MemoryEvolutionStore(
        tmp_path,
        policy=MemoryEvolutionPolicy(write_mode=MemoryWriteMode.REVIEW),
    )
    proposal = MemoryProposal(
        target=MemoryTarget.IDENTITY,
        proposed_content="# Identity\n\nCode reviewer.\n",
        reason="Stable role",
        confidence=0.9,
    )
    coordinator = MemoryEvolutionCoordinator(store, StaticGenerator([proposal]))

    events = await coordinator.process(
        context_with_user_message("Remember that your role is code reviewer")
    )

    assert not (tmp_path / "IDENTITY.md").exists()
    assert store.pending() == [proposal]
    assert events[0].staged_count == 1


@pytest.mark.asyncio
async def test_disabled_mode_does_not_call_generator(tmp_path: Path) -> None:
    store = MemoryEvolutionStore(
        tmp_path,
        policy=MemoryEvolutionPolicy(write_mode=MemoryWriteMode.DISABLED),
    )
    generator = StaticGenerator([])
    coordinator = MemoryEvolutionCoordinator(store, generator)

    events = await coordinator.process(
        context_with_user_message("Please remember this")
    )

    assert generator.calls == 0
    assert events[0].triggered is False


@pytest.mark.asyncio
async def test_low_confidence_proposal_is_rejected(tmp_path: Path) -> None:
    store = MemoryEvolutionStore(tmp_path)
    proposal = MemoryProposal(
        target=MemoryTarget.CORE_MEMORY,
        proposed_content="# Memory\n\nMaybe the user likes Rust.\n",
        reason="Weak inference",
        confidence=0.4,
    )
    coordinator = MemoryEvolutionCoordinator(store, StaticGenerator([proposal]))

    events = await coordinator.process(
        context_with_user_message("Remember this uncertain guess")
    )

    assert not (tmp_path / "MEMORY.md").exists()
    assert events[0].rejected_count == 1
