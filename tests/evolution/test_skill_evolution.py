"""Behavior tests for quarantined, revisioned Skill evolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from quenda.evolution import (
    SkillEvolutionStore,
    SkillFileChange,
    SkillProposal,
)


def _make_skill(root: Path, *, body: str = "Original instructions.\n") -> Path:
    skill = root / "skills" / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Demonstrate Skill evolution.\n"
        'version: "1.0.0"\n'
        "---\n\n"
        f"{body}",
        encoding="utf-8",
    )
    return skill


def _proposal(
    store: SkillEvolutionStore,
    *changes: SkillFileChange,
    reason: str = "Improve the instructions from observed failures",
) -> SkillProposal:
    return SkillProposal(
        skill_name="demo-skill",
        base_revision=store.current_revision(),
        changes=changes,
        reason=reason,
        evidence_refs=("run:run-1",),
        confidence=0.9,
    )


def test_stage_validates_in_quarantine_without_mutating_active_skill(
    tmp_path: Path,
) -> None:
    skill = _make_skill(tmp_path)
    original = (skill / "SKILL.md").read_text(encoding="utf-8")
    store = SkillEvolutionStore(skill, tmp_path / "state")
    proposal = _proposal(
        store,
        SkillFileChange("SKILL.md", original.replace("Original", "Improved")),
    )

    staged = store.stage(proposal)

    assert staged.validation.valid
    assert staged.status == "validated"
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == original
    candidate = store.candidate_path(proposal.id)
    assert "Improved instructions" in (candidate / "SKILL.md").read_text()
    assert candidate.is_relative_to(tmp_path / "state")
    assert SkillEvolutionStore(skill, tmp_path / "state").proposals() == [staged]


def test_stage_rejects_unsafe_paths_and_keeps_them_outside_candidate(
    tmp_path: Path,
) -> None:
    skill = _make_skill(tmp_path)
    store = SkillEvolutionStore(skill, tmp_path / "state")
    proposal = _proposal(store, SkillFileChange("../escape.txt", "nope"))

    staged = store.stage(proposal)

    assert not staged.validation.valid
    assert "skill.path_invalid" in {issue.code for issue in staged.validation.issues}
    assert not (tmp_path / "escape.txt").exists()
    with pytest.raises(ValueError, match="validation"):
        store.commit(proposal.id, actor="agent", approved_by="alice")


def test_python_scripts_are_compiled_not_run_and_require_explicit_review(
    tmp_path: Path,
) -> None:
    skill = _make_skill(tmp_path)
    store = SkillEvolutionStore(skill, tmp_path / "state")
    marker = tmp_path / "must-not-exist"
    proposal = _proposal(
        store,
        SkillFileChange(
            "scripts/check.py",
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        ),
    )

    staged = store.stage(proposal)

    assert staged.validation.valid
    assert staged.validation.requires_executable_review
    assert not marker.exists()
    with pytest.raises(PermissionError, match="approval"):
        store.commit(proposal.id, actor="agent")
    assert not marker.exists()


def test_invalid_python_and_probable_secrets_fail_validation(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    store = SkillEvolutionStore(skill, tmp_path / "state")
    proposal = _proposal(
        store,
        SkillFileChange("scripts/broken.py", "if:\n"),
        SkillFileChange("references/private.md", "api_key = super-secret-value-123"),
    )

    staged = store.stage(proposal)

    codes = {issue.code for issue in staged.validation.issues}
    assert "skill.python_invalid" in codes
    assert "skill.possible_secret" in codes


def test_commit_uses_cas_and_records_an_immutable_revision(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    store = SkillEvolutionStore(skill, tmp_path / "state")
    original = (skill / "SKILL.md").read_text(encoding="utf-8")
    proposal = _proposal(
        store,
        SkillFileChange("SKILL.md", original.replace("Original", "Improved")),
    )
    store.stage(proposal)
    (skill / "notes.md").write_text("concurrent edit", encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed"):
        store.commit(proposal.id, actor="agent", approved_by="alice")

    fresh = _proposal(
        store,
        SkillFileChange("SKILL.md", original.replace("Original", "Improved")),
    )
    store.stage(fresh)
    revision = store.commit(fresh.id, actor="agent", approved_by="alice")

    assert revision.previous_revision == fresh.base_revision
    assert revision.approved_by == "alice"
    assert revision.content_revision == store.current_revision()
    assert store.history() == [revision]
    assert "Improved instructions" in (skill / "SKILL.md").read_text()


def test_rollback_restores_a_snapshot_as_a_new_audited_revision(
    tmp_path: Path,
) -> None:
    skill = _make_skill(tmp_path)
    store = SkillEvolutionStore(skill, tmp_path / "state")
    original_revision = store.current_revision()
    original = (skill / "SKILL.md").read_text(encoding="utf-8")
    proposal = _proposal(
        store,
        SkillFileChange("SKILL.md", original.replace("Original", "Improved")),
    )
    store.stage(proposal)
    committed = store.commit(proposal.id, actor="agent", approved_by="alice")

    rollback = store.rollback(
        original_revision,
        reason="Restore known-good Skill",
        actor="agent",
        approved_by="alice",
    )

    assert store.current_revision() == original_revision
    assert rollback.previous_revision == committed.content_revision
    assert rollback.rollback_of == original_revision
    assert len(store.history()) == 2
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == original
