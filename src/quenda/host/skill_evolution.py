"""Host seam for discovering and governing Skill evolution stores."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from quenda.evolution import (
    SkillEvolutionStore,
    SkillFileChange,
    SkillProposal,
    SkillValidationIssue,
    StagedSkillProposal,
)
from quenda.host.skill import SkillDiscovery
from quenda.runtime.permission import (
    DenyPermissionPolicy,
    PermissionKind,
    PermissionLifetime,
    PermissionPolicy,
    PermissionRequest,
    PermissionScope,
)


class SkillEvolutionManager:
    """Resolve Skills and govern their revision workflow through one interface."""

    def __init__(
        self,
        discovery: SkillDiscovery,
        *,
        state_root: Path | str,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self.discovery = discovery
        self.state_root = Path(state_root).expanduser().resolve()
        self.permission_policy = permission_policy or DenyPermissionPolicy()

    def active_path(self, skill_name: str) -> Path:
        """Resolve the currently winning package for a Skill name."""
        skill = self.discovery.get_skill(skill_name)
        if skill is None:
            raise KeyError(f"Unknown Skill: {skill_name}")
        return skill.path.resolve()

    def inspect(self, skill_name: str | None = None) -> dict[str, Any]:
        """Return content-free revision and queue metadata."""
        if skill_name is None:
            return {
                "skills": [
                    {
                        "skill_name": skill.name,
                        "source": skill.source,
                        "active_path": str(skill.path.resolve()),
                        "revision": self._store(skill.name).current_revision(),
                    }
                    for skill in self.discovery.discover_skills()
                ]
            }
        store = self._store(skill_name)
        return {
            "skill_name": skill_name,
            "active_path": str(store.skill_path),
            "revision": store.current_revision(),
            "proposals": [self._proposal_summary(item) for item in store.proposals()],
            "history": [revision.to_dict() for revision in store.history()],
        }

    def propose(
        self,
        skill_name: str,
        changes: dict[str, str | None],
        *,
        reason: str,
        evidence_refs: tuple[str, ...] = (),
        confidence: float = 1.0,
        risk: Literal["low", "medium", "high"] = "low",
        source_run_id: str = "",
    ) -> dict[str, Any]:
        """Stage a content-free, statically evaluated proposal summary."""
        store = self._store(skill_name)
        proposal = SkillProposal(
            skill_name=skill_name,
            base_revision=store.current_revision(),
            changes=tuple(
                SkillFileChange(path=path, content=content)
                for path, content in sorted(changes.items())
            ),
            reason=reason,
            evidence_refs=evidence_refs,
            confidence=confidence,
            risk=risk,
            source_run_id=source_run_id,
        )
        return self._proposal_summary(store.stage(proposal))

    def commit(
        self,
        skill_name: str,
        *,
        proposal_id: str,
        expected_revision: str,
        actor: str = "quenda-host",
    ) -> dict[str, Any]:
        """Approve and activate a validated proposal at an explicit write point."""
        store = self._store(skill_name)
        staged = self._find_proposal(store, proposal_id)
        if staged.proposal.base_revision != expected_revision:
            return self._outcome(
                "conflict",
                skill_name,
                proposal_id=proposal_id,
                base_revision=staged.proposal.base_revision,
                message="expected_revision does not match the staged proposal",
            )
        decision = self.permission_policy.decide(
            self._permission_request(
                action="commit",
                store=store,
                proposal_id=proposal_id,
                base_revision=expected_revision,
                changed_paths=[change.path for change in staged.proposal.changes],
            )
        )
        if not decision.allowed:
            return self._outcome(
                "denied",
                skill_name,
                proposal_id=proposal_id,
                base_revision=expected_revision,
                message=decision.reason or "Skill evolution commit denied",
            )
        revision = store.commit(
            proposal_id,
            actor=actor,
            approved_by="host-permission",
        )
        return self._outcome(
            "committed",
            skill_name,
            proposal_id=proposal_id,
            base_revision=revision.previous_revision,
            revision=revision.content_revision,
        )

    def rollback(
        self,
        skill_name: str,
        *,
        revision: str,
        expected_revision: str,
        reason: str,
        actor: str = "quenda-host",
    ) -> dict[str, Any]:
        """Approve activation of an immutable historical snapshot."""
        store = self._store(skill_name)
        decision = self.permission_policy.decide(
            self._permission_request(
                action="rollback",
                store=store,
                proposal_id=None,
                base_revision=expected_revision,
                changed_paths=[],
                target_revision=revision,
            )
        )
        if not decision.allowed:
            return self._outcome(
                "denied",
                skill_name,
                base_revision=expected_revision,
                revision=revision,
                message=decision.reason or "Skill rollback denied",
            )
        committed = store.rollback(
            revision,
            reason=reason,
            actor=actor,
            approved_by="host-permission",
            expected_revision=expected_revision,
        )
        return self._outcome(
            "rolled_back",
            skill_name,
            base_revision=committed.previous_revision,
            revision=committed.content_revision,
        )

    def _store(self, skill_name: str) -> SkillEvolutionStore:
        return SkillEvolutionStore(
            self.active_path(skill_name),
            self.state_root / skill_name,
        )

    @staticmethod
    def _find_proposal(
        store: SkillEvolutionStore,
        proposal_id: str,
    ) -> StagedSkillProposal:
        for staged in store.proposals():
            if staged.proposal.id == proposal_id:
                return staged
        raise KeyError(f"Unknown Skill proposal: {proposal_id}")

    @staticmethod
    def _proposal_summary(staged: StagedSkillProposal) -> dict[str, Any]:
        proposal = staged.proposal
        return {
            "status": staged.status,
            "skill_name": proposal.skill_name,
            "proposal_id": proposal.id,
            "base_revision": proposal.base_revision,
            "candidate_revision": staged.validation.candidate_revision,
            "changed_paths": [change.path for change in proposal.changes],
            "reason": proposal.reason,
            "evidence_refs": list(proposal.evidence_refs),
            "confidence": proposal.confidence,
            "risk": proposal.risk,
            "requires_executable_review": (staged.validation.requires_executable_review),
            "issues": [asdict_issue(issue) for issue in staged.validation.issues],
            "proposed_at": proposal.proposed_at.isoformat(),
            "expires_at": (
                proposal.expires_at.isoformat() if proposal.expires_at is not None else None
            ),
        }

    @staticmethod
    def _outcome(
        status: str,
        skill_name: str,
        *,
        proposal_id: str | None = None,
        base_revision: str | None = None,
        revision: str | None = None,
        message: str = "",
    ) -> dict[str, Any]:
        return {
            "status": status,
            "skill_name": skill_name,
            "proposal_id": proposal_id,
            "base_revision": base_revision,
            "revision": revision,
            "message": message,
        }

    @staticmethod
    def _permission_request(
        *,
        action: Literal["commit", "rollback"],
        store: SkillEvolutionStore,
        proposal_id: str | None,
        base_revision: str,
        changed_paths: list[str],
        target_revision: str | None = None,
    ) -> PermissionRequest:
        return PermissionRequest(
            kind=PermissionKind.SKILL_EVOLUTION_WRITE,
            resource=str(store.skill_path),
            scope=PermissionScope.DIRECTORY,
            reason=f"{action.capitalize()} a revision of Skill {store.skill_path.name}",
            lifetime=PermissionLifetime.RUN,
            tool_name="apply_skill_evolution",
            tool_args={
                "action": action,
                "proposal_id": proposal_id,
                "base_revision": base_revision,
                "target_revision": target_revision,
                "changed_paths": changed_paths,
            },
            cacheable=False,
        )


def asdict_issue(issue: SkillValidationIssue) -> dict[str, str]:
    """Serialize validation findings without exposing candidate content."""
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
    }


__all__ = ["SkillEvolutionManager"]
