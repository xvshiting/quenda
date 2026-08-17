"""Behavior tests for policy-controlled, revisioned memory evolution."""

from pathlib import Path

import pytest

from quenda.evolution import (
    MemoryEvolutionPolicy,
    MemoryEvolutionStore,
    MemoryProposal,
    MemoryTarget,
    MemoryWriteMode,
)


def test_apply_requires_approval_and_records_revision(tmp_path: Path) -> None:
    memory = tmp_path / "MEMORY.md"
    memory.write_text("# Memory\n\nOriginal.\n", encoding="utf-8")
    store = MemoryEvolutionStore(
        tmp_path,
        policy=MemoryEvolutionPolicy(write_mode=MemoryWriteMode.REVIEW),
    )
    original_revision = store.current_revision(MemoryTarget.CORE_MEMORY)
    proposal = MemoryProposal(
        target=MemoryTarget.CORE_MEMORY,
        proposed_content="# Memory\n\nPrefer concise answers.\n",
        reason="The user explicitly stated this preference",
        expected_revision=original_revision,
        source_run_id="run-1",
    )

    with pytest.raises(PermissionError):
        store.apply(proposal, approved_by="")

    revision = store.apply(proposal, approved_by="alice")

    assert memory.read_text(encoding="utf-8") == proposal.proposed_content
    assert revision.previous_revision == original_revision
    assert revision.source_run_id == "run-1"
    assert revision.approved_by == "alice"
    assert revision.automatic is False
    assert store.history() == [revision]


def test_default_policy_can_commit_validated_proposal_automatically(
    tmp_path: Path,
) -> None:
    store = MemoryEvolutionStore(tmp_path)
    proposal = MemoryProposal(
        target=MemoryTarget.SOUL,
        proposed_content="# Soul\n\nBe candid and pragmatic.\n",
        reason="Repeated successful interaction pattern",
        source_run_id="run-auto",
    )

    revision = store.apply(proposal, actor="default-evolution-policy")

    assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == (
        proposal.proposed_content
    )
    assert revision.committed_by == "default-evolution-policy"
    assert revision.approved_by is None
    assert revision.automatic is True


def test_disabled_policy_blocks_even_valid_proposals(tmp_path: Path) -> None:
    store = MemoryEvolutionStore(
        tmp_path,
        policy=MemoryEvolutionPolicy(write_mode=MemoryWriteMode.DISABLED),
    )
    proposal = MemoryProposal(
        target=MemoryTarget.CORE_MEMORY,
        proposed_content="# Memory\n\nKeep this.\n",
        reason="valid but disabled",
    )

    with pytest.raises(PermissionError, match="disabled"):
        store.apply(proposal)


def test_stale_proposal_cannot_overwrite_newer_memory(tmp_path: Path) -> None:
    memory = tmp_path / "MEMORY.md"
    memory.write_text("one", encoding="utf-8")
    store = MemoryEvolutionStore(tmp_path)
    stale_revision = store.current_revision(MemoryTarget.CORE_MEMORY)
    memory.write_text("two", encoding="utf-8")

    proposal = MemoryProposal(
        target=MemoryTarget.CORE_MEMORY,
        proposed_content="three",
        reason="stale proposal",
        expected_revision=stale_revision,
    )

    with pytest.raises(RuntimeError, match="changed"):
        store.apply(proposal, approved_by="alice")
    assert memory.read_text(encoding="utf-8") == "two"


def test_validator_rejects_probable_credentials(tmp_path: Path) -> None:
    store = MemoryEvolutionStore(tmp_path)
    proposal = MemoryProposal(
        target=MemoryTarget.USER_PROFILE,
        proposed_content="api_key = super-secret-token-value",
        reason="unsafe",
    )

    report = store.validate(proposal)

    assert not report.valid
    assert {issue.code for issue in report.issues} == {"memory.possible_secret"}
    with pytest.raises(ValueError, match="possible_secret"):
        store.apply(proposal, approved_by="alice")


def test_rollback_restores_snapshot_as_a_new_revision(tmp_path: Path) -> None:
    memory = tmp_path / "MEMORY.md"
    memory.write_text("version zero", encoding="utf-8")
    store = MemoryEvolutionStore(tmp_path)

    first = store.apply(
        MemoryProposal(
            target=MemoryTarget.CORE_MEMORY,
            proposed_content="version one",
            reason="first change",
            expected_revision=store.current_revision(MemoryTarget.CORE_MEMORY),
        ),
        approved_by="alice",
    )
    second = store.apply(
        MemoryProposal(
            target=MemoryTarget.CORE_MEMORY,
            proposed_content="version two",
            reason="second change",
            expected_revision=first.content_revision,
        ),
        approved_by="alice",
    )

    rollback = store.rollback(
        MemoryTarget.CORE_MEMORY,
        first.content_revision,
        approved_by="alice",
        reason="restore known-good memory",
    )

    assert memory.read_text(encoding="utf-8") == "version one"
    assert rollback.previous_revision == second.content_revision
    assert rollback.rollback_of == first.content_revision
    assert len(store.history(MemoryTarget.CORE_MEMORY)) == 3


def test_first_apply_archives_preexisting_content_for_rollback(tmp_path: Path) -> None:
    memory = tmp_path / "MEMORY.md"
    memory.write_text("original", encoding="utf-8")
    store = MemoryEvolutionStore(tmp_path)
    original_revision = store.current_revision(MemoryTarget.CORE_MEMORY)
    assert original_revision is not None
    store.apply(
        MemoryProposal(
            target=MemoryTarget.CORE_MEMORY,
            proposed_content="updated",
            reason="update",
            expected_revision=original_revision,
        ),
        approved_by="alice",
    )

    store.rollback(
        MemoryTarget.CORE_MEMORY,
        original_revision,
        approved_by="alice",
        reason="restore original",
    )

    assert memory.read_text(encoding="utf-8") == "original"
