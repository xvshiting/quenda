"""Framework Tools for inspectable, governed Skill evolution."""

from __future__ import annotations

import json
from typing import Literal, cast, override

from quenda.host.skill_evolution import SkillEvolutionManager
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class InspectSkillEvolutionTool(Tool):
    """Inspect Skill revisions and proposals without candidate content."""

    def __init__(self, manager: SkillEvolutionManager) -> None:
        self._manager = manager

    @property
    @override
    def name(self) -> str:
        return "inspect_skill_evolution"

    @property
    @override
    def description(self) -> str:
        return (
            "Inspect available Skills, active revisions, staged proposal metadata, "
            "validation findings, and activation history. Candidate file contents "
            "are intentionally omitted."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Optional Skill name; omit to list available Skills.",
                }
            },
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        skill_name = kwargs.get("skill_name")
        if skill_name is not None and not isinstance(skill_name, str):
            return self._error("skill_name must be a string")
        try:
            result = self._manager.inspect(skill_name)
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            return self._error(str(error))
        return ToolResult(
            call_id="",
            name=self.name,
            content=json.dumps(result, ensure_ascii=False, sort_keys=True),
            result_summary="inspected",
        )

    def _error(self, message: str) -> ToolResult:
        return ToolResult(call_id="", name=self.name, content=message, is_error=True)


class ApplySkillEvolutionTool(Tool):
    """Stage, explicitly commit, or roll back one Skill revision."""

    def __init__(self, manager: SkillEvolutionManager) -> None:
        self._manager = manager

    @property
    @override
    def name(self) -> str:
        return "apply_skill_evolution"

    @property
    @override
    def description(self) -> str:
        return (
            "Stage a quarantined Skill proposal, commit a validated proposal, or "
            "roll back to a historical revision. Propose first. Commit and rollback "
            "require a non-cacheable Host approval and an expected active revision."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["propose", "commit", "rollback"],
                },
                "skill_name": {"type": "string"},
                "changes": {
                    "type": "object",
                    "description": (
                        "For propose: map package-relative paths to complete UTF-8 "
                        "replacement text, or null to delete a file."
                    ),
                    "additionalProperties": {"type": ["string", "null"]},
                },
                "reason": {"type": "string"},
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 1,
                },
                "risk": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "low",
                },
                "proposal_id": {"type": "string"},
                "expected_revision": {"type": "string"},
                "revision": {
                    "type": "string",
                    "description": "Historical target revision for rollback.",
                },
            },
            "required": ["action", "skill_name"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        action = kwargs.get("action")
        skill_name = kwargs.get("skill_name")
        if action not in {"propose", "commit", "rollback"}:
            return self._error("action must be propose, commit, or rollback")
        if not isinstance(skill_name, str) or not skill_name:
            return self._error("skill_name must be a non-empty string")
        try:
            if action == "propose":
                result = self._propose(skill_name, kwargs)
            elif action == "commit":
                result = self._commit(skill_name, kwargs)
            else:
                result = self._rollback(skill_name, kwargs)
        except (
            KeyError,
            OSError,
            PermissionError,
            RuntimeError,
            UnicodeError,
            ValueError,
        ) as error:
            return self._error(str(error))

        status = str(result["status"])
        return ToolResult(
            call_id="",
            name=self.name,
            content=json.dumps(result, ensure_ascii=False, sort_keys=True),
            is_error=status in {"conflict", "denied", "rejected"},
            display_hint=str(self._manager.active_path(skill_name)),
            result_summary=status,
            change_preview=_change_preview(result),
        )

    def _propose(self, skill_name: str, kwargs: dict[str, object]) -> dict[str, object]:
        raw_changes = kwargs.get("changes")
        reason = kwargs.get("reason")
        if not isinstance(raw_changes, dict) or not raw_changes:
            raise ValueError("changes must be a non-empty object")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        changes: dict[str, str | None] = {}
        for path, content in raw_changes.items():
            if not isinstance(path, str) or not (isinstance(content, str) or content is None):
                raise ValueError("changes values must be strings or null")
            changes[path] = content
        raw_evidence = kwargs.get("evidence_refs", [])
        if not isinstance(raw_evidence, list) or not all(
            isinstance(item, str) for item in raw_evidence
        ):
            raise ValueError("evidence_refs must be an array of strings")
        confidence = kwargs.get("confidence", 1.0)
        if not isinstance(confidence, int | float):
            raise ValueError("confidence must be a number")
        raw_risk = kwargs.get("risk", "low")
        if raw_risk not in {"low", "medium", "high"}:
            raise ValueError("risk must be low, medium, or high")
        return self._manager.propose(
            skill_name,
            changes,
            reason=reason,
            evidence_refs=tuple(raw_evidence),
            confidence=float(confidence),
            risk=cast(Literal["low", "medium", "high"], raw_risk),
        )

    def _commit(self, skill_name: str, kwargs: dict[str, object]) -> dict[str, object]:
        proposal_id = kwargs.get("proposal_id")
        expected = kwargs.get("expected_revision")
        if not isinstance(proposal_id, str) or not proposal_id:
            raise ValueError("proposal_id is required for commit")
        if not isinstance(expected, str) or not expected:
            raise ValueError("expected_revision is required for commit")
        return self._manager.commit(
            skill_name,
            proposal_id=proposal_id,
            expected_revision=expected,
        )

    def _rollback(self, skill_name: str, kwargs: dict[str, object]) -> dict[str, object]:
        revision = kwargs.get("revision")
        expected = kwargs.get("expected_revision")
        reason = kwargs.get("reason")
        if not isinstance(revision, str) or not revision:
            raise ValueError("revision is required for rollback")
        if not isinstance(expected, str) or not expected:
            raise ValueError("expected_revision is required for rollback")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required for rollback")
        return self._manager.rollback(
            skill_name,
            revision=revision,
            expected_revision=expected,
            reason=reason,
        )

    def _error(self, message: str) -> ToolResult:
        return ToolResult(call_id="", name=self.name, content=message, is_error=True)


def _change_preview(result: dict[str, object]) -> str:
    raw_paths = result.get("changed_paths")
    if not isinstance(raw_paths, list):
        return ""
    return "\n".join(f"M {path}" for path in raw_paths)


__all__ = ["ApplySkillEvolutionTool", "InspectSkillEvolutionTool"]
