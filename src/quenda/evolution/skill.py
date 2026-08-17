"""Quarantined, revisioned evolution for Skill packages.

The active Skill directory is never edited while a proposal is being built or
validated.  A proposal becomes visible only through an explicit, audited
directory swap after validation, approval, and a compare-and-swap check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from uuid import uuid4

import yaml  # type: ignore[import-untyped]

from quenda.host.skill.models import SkillFrontmatter

SKILL_JOURNAL_SCHEMA_VERSION = "quenda.skill-journal/v1"
_PROCESS_LOCK = threading.RLock()
_REVISION = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[0-9a-f]{32}")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*[^\s]{12,}"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class SkillFileChange:
    """A complete text replacement, or deletion, within a Skill package."""

    path: str
    content: str | None


@dataclass(frozen=True)
class SkillProposal:
    """A candidate change based on one immutable active revision."""

    skill_name: str
    base_revision: str
    changes: tuple[SkillFileChange, ...]
    reason: str
    evidence_refs: tuple[str, ...] = ()
    confidence: float = 1.0
    risk: Literal["low", "medium", "high"] = "low"
    source_run_id: str = ""
    expires_at: datetime | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    proposed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["proposed_at"] = self.proposed_at.isoformat()
        payload["expires_at"] = self.expires_at.isoformat() if self.expires_at is not None else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SkillProposal:
        raw_changes = payload.get("changes", [])
        if not isinstance(raw_changes, list):
            raise ValueError("Skill proposal changes must be a list")
        raw_evidence = payload.get("evidence_refs", [])
        evidence = raw_evidence if isinstance(raw_evidence, list | tuple) else []
        raw_risk = str(payload.get("risk", "low"))
        if raw_risk not in {"low", "medium", "high"}:
            raise ValueError(f"Invalid Skill proposal risk: {raw_risk}")
        return cls(
            skill_name=str(payload["skill_name"]),
            base_revision=str(payload["base_revision"]),
            changes=tuple(
                SkillFileChange(
                    path=str(item["path"]),
                    content=(str(item["content"]) if item.get("content") is not None else None),
                )
                for item in raw_changes
                if isinstance(item, dict)
            ),
            reason=str(payload["reason"]),
            evidence_refs=tuple(str(item) for item in evidence),
            confidence=float(str(payload.get("confidence", 1.0))),
            risk=cast(Literal["low", "medium", "high"], raw_risk),
            source_run_id=str(payload.get("source_run_id", "")),
            expires_at=(
                datetime.fromisoformat(str(payload["expires_at"]))
                if payload.get("expires_at")
                else None
            ),
            id=str(payload["id"]),
            proposed_at=datetime.fromisoformat(str(payload["proposed_at"])),
        )


@dataclass(frozen=True)
class SkillValidationIssue:
    """One machine-readable finding from isolated static validation."""

    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class SkillValidationReport:
    """Persisted evaluator output for a quarantined proposal."""

    issues: tuple[SkillValidationIssue, ...] = ()
    candidate_revision: str | None = None
    requires_executable_review: bool = False

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SkillValidationReport:
        raw_issues = payload.get("issues", [])
        issue_items = raw_issues if isinstance(raw_issues, list | tuple) else []
        issues: list[SkillValidationIssue] = []
        for item in issue_items:
            if not isinstance(item, dict):
                continue
            raw_severity = str(item.get("severity", "error"))
            if raw_severity not in {"error", "warning"}:
                raise ValueError(f"Invalid Skill validation severity: {raw_severity}")
            issues.append(
                SkillValidationIssue(
                    code=str(item["code"]),
                    message=str(item["message"]),
                    severity=cast(Literal["error", "warning"], raw_severity),
                )
            )
        return cls(
            issues=tuple(issues),
            candidate_revision=(
                str(payload["candidate_revision"]) if payload.get("candidate_revision") else None
            ),
            requires_executable_review=bool(payload.get("requires_executable_review", False)),
        )


@dataclass(frozen=True)
class StagedSkillProposal:
    """A proposal plus its durable evaluator result and lifecycle status."""

    proposal: SkillProposal
    validation: SkillValidationReport
    status: Literal["rejected", "validated", "committed"]

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal": self.proposal.to_dict(),
            "validation": self.validation.to_dict(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> StagedSkillProposal:
        proposal = payload.get("proposal")
        validation = payload.get("validation")
        if not isinstance(proposal, dict) or not isinstance(validation, dict):
            raise ValueError("Invalid staged Skill proposal")
        raw_status = str(payload["status"])
        if raw_status not in {"rejected", "validated", "committed"}:
            raise ValueError(f"Invalid staged Skill status: {raw_status}")
        return cls(
            proposal=SkillProposal.from_dict(proposal),
            validation=SkillValidationReport.from_dict(validation),
            status=cast(Literal["rejected", "validated", "committed"], raw_status),
        )


@dataclass(frozen=True)
class SkillRevision:
    """One append-only activation record."""

    id: str
    skill_name: str
    content_revision: str
    previous_revision: str
    proposal_id: str
    reason: str
    committed_by: str
    approved_by: str
    committed_at: datetime
    source_run_id: str = ""
    rollback_of: str | None = None
    schema_version: str = SKILL_JOURNAL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["committed_at"] = self.committed_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SkillRevision:
        return cls(
            id=str(payload["id"]),
            skill_name=str(payload["skill_name"]),
            content_revision=str(payload["content_revision"]),
            previous_revision=str(payload["previous_revision"]),
            proposal_id=str(payload["proposal_id"]),
            reason=str(payload["reason"]),
            committed_by=str(payload["committed_by"]),
            approved_by=str(payload["approved_by"]),
            committed_at=datetime.fromisoformat(str(payload["committed_at"])),
            source_run_id=str(payload.get("source_run_id", "")),
            rollback_of=(str(payload["rollback_of"]) if payload.get("rollback_of") else None),
            schema_version=str(payload.get("schema_version", SKILL_JOURNAL_SCHEMA_VERSION)),
        )


class SkillEvolutionStore:
    """Stage, validate, activate, and roll back one Skill through one interface."""

    def __init__(
        self,
        skill_path: Path | str,
        state_root: Path | str,
        *,
        max_files: int = 256,
        max_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self.skill_path = Path(skill_path).expanduser().resolve()
        self.state_root = Path(state_root).expanduser().resolve()
        if self.state_root == self.skill_path or self.state_root.is_relative_to(self.skill_path):
            raise ValueError("Skill evolution state must be outside the active Skill")
        if max_files <= 0 or max_bytes <= 0:
            raise ValueError("Skill evolution limits must be positive")
        self.max_files = max_files
        self.max_bytes = max_bytes
        self.pending_root = self.state_root / "pending"
        self.revisions_root = self.state_root / "revisions"
        self.journal_path = self.state_root / "journal.jsonl"
        self.lock_path = self.state_root / "write.lock"

    def current_revision(self) -> str:
        """Return the content-addressed revision of the active package."""
        return _directory_revision(self.skill_path)

    def candidate_path(self, proposal_id: str) -> Path:
        """Return a quarantined candidate path for inspection."""
        _require_identifier(proposal_id)
        return self.pending_root / proposal_id / "candidate"

    def pin_current(self) -> tuple[str, Path]:
        """Archive and return the active package as an immutable epoch snapshot."""
        revision = self.current_revision()
        report = self._validate_snapshot(self.skill_path)
        if not report.valid or report.candidate_revision != revision:
            codes = ", ".join(issue.code for issue in report.issues)
            raise ValueError(f"Cannot pin invalid Skill package: {codes}")
        self._store_snapshot(self.skill_path, revision)
        return revision, self.snapshot_path(revision)

    def snapshot_path(self, revision: str) -> Path:
        """Resolve a known immutable revision after checking its identifier."""
        if not _REVISION.fullmatch(revision):
            raise ValueError("Invalid Skill revision identifier")
        path = self.revisions_root / revision
        if not path.is_dir():
            raise KeyError(f"Unknown Skill revision: {revision}")
        return path

    def proposals(
        self,
        *,
        status: Literal["rejected", "validated", "committed"] | None = None,
    ) -> list[StagedSkillProposal]:
        """List durable proposals in stable creation order after a restart."""
        if not self.pending_root.is_dir():
            return []
        staged: list[StagedSkillProposal] = []
        for path in sorted(self.pending_root.glob("*/proposal.json")):
            item = StagedSkillProposal.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if status is None or item.status == status:
                staged.append(item)
        return sorted(staged, key=lambda item: (item.proposal.proposed_at, item.proposal.id))

    def stage(self, proposal: SkillProposal) -> StagedSkillProposal:
        """Build and statically evaluate a candidate outside the active package."""
        if proposal.skill_name != self._active_skill_name():
            report = SkillValidationReport(
                issues=(
                    SkillValidationIssue(
                        "skill.name_mismatch",
                        "Proposal target does not match the active Skill name",
                    ),
                )
            )
            return self._persist_stage(proposal, report)
        if not _REVISION.fullmatch(proposal.base_revision):
            report = SkillValidationReport(
                issues=(
                    SkillValidationIssue(
                        "skill.revision_invalid",
                        "Proposal base revision is not a SHA-256 identifier",
                    ),
                )
            )
            return self._persist_stage(proposal, report)

        current = self.current_revision()
        if current != proposal.base_revision:
            report = SkillValidationReport(
                issues=(
                    SkillValidationIssue(
                        "skill.base_changed",
                        "Active Skill changed before the proposal was staged",
                    ),
                )
            )
            return self._persist_stage(proposal, report)

        self._store_snapshot(self.skill_path, current)
        candidate = self.candidate_path(proposal.id)
        if candidate.parent.exists():
            shutil.rmtree(candidate.parent)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.skill_path, candidate, symlinks=True)

        path_issues: list[SkillValidationIssue] = []
        seen_paths: set[str] = set()
        for change in proposal.changes:
            relative = _safe_relative_path(change.path)
            if relative is None:
                path_issues.append(
                    SkillValidationIssue(
                        "skill.path_invalid",
                        f"Change path must stay inside the Skill: {change.path!r}",
                    )
                )
                continue
            normalized = relative.as_posix()
            if normalized in seen_paths:
                path_issues.append(
                    SkillValidationIssue(
                        "skill.path_duplicate",
                        f"Change path appears more than once: {normalized}",
                    )
                )
                continue
            seen_paths.add(normalized)
            target = candidate.joinpath(*relative.parts)
            if change.content is None:
                if target.is_dir():
                    path_issues.append(
                        SkillValidationIssue(
                            "skill.directory_delete_unsupported",
                            f"Delete files individually instead of deleting {normalized}",
                        )
                    )
                else:
                    target.unlink(missing_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(target, change.content)

        report = self._validate_candidate(proposal, candidate, path_issues)
        return self._persist_stage(proposal, report)

    def commit(
        self,
        proposal_id: str,
        *,
        actor: str,
        approved_by: str | None = None,
    ) -> SkillRevision:
        """Activate one validated proposal after approval and a CAS check."""
        actor = actor.strip()
        approver = (approved_by or "").strip()
        if not actor:
            raise ValueError("Skill evolution actor is required")
        if not approver:
            raise PermissionError("Skill evolution commit requires explicit approval")
        staged = self._load_stage(proposal_id)
        if not staged.validation.valid:
            raise ValueError("Skill proposal failed validation")
        if staged.status == "committed":
            raise ValueError("Skill proposal was already committed")
        if staged.proposal.expires_at is not None and staged.proposal.expires_at <= datetime.now(
            UTC
        ):
            raise ValueError("Skill proposal has expired")

        candidate = self.candidate_path(proposal_id)
        fresh_report = self._validate_candidate(staged.proposal, candidate, [])
        if not fresh_report.valid or (
            fresh_report.candidate_revision != staged.validation.candidate_revision
        ):
            raise RuntimeError("Quarantined Skill candidate changed after validation")

        with self._write_lock():
            previous = self.current_revision()
            if previous != staged.proposal.base_revision:
                raise RuntimeError(
                    "Active Skill changed after this proposal was created; review it again"
                )
            content_revision = fresh_report.candidate_revision
            if content_revision is None or content_revision == previous:
                raise ValueError("Skill proposal does not change the active package")
            self._store_snapshot(self.skill_path, previous)
            self._store_snapshot(candidate, content_revision)
            self._activate_snapshot(candidate)
            revision = SkillRevision(
                id=uuid4().hex,
                skill_name=staged.proposal.skill_name,
                content_revision=content_revision,
                previous_revision=previous,
                proposal_id=proposal_id,
                reason=staged.proposal.reason.strip(),
                committed_by=actor,
                approved_by=approver,
                committed_at=datetime.now(UTC),
                source_run_id=staged.proposal.source_run_id,
            )
            self._append_journal(revision)
            self._write_stage(
                StagedSkillProposal(
                    proposal=staged.proposal,
                    validation=fresh_report,
                    status="committed",
                )
            )
            return revision

    def rollback(
        self,
        content_revision: str,
        *,
        reason: str,
        actor: str,
        approved_by: str | None = None,
        expected_revision: str | None = None,
    ) -> SkillRevision:
        """Activate a known snapshot as a new, explicitly approved revision."""
        if not _REVISION.fullmatch(content_revision):
            raise ValueError("Invalid Skill revision identifier")
        actor = actor.strip()
        approver = (approved_by or "").strip()
        if not actor:
            raise ValueError("Skill evolution actor is required")
        if not approver:
            raise PermissionError("Skill rollback requires explicit approval")
        snapshot = self.revisions_root / content_revision
        if not snapshot.is_dir():
            raise KeyError(f"Unknown Skill revision: {content_revision}")

        with self._write_lock():
            previous = self.current_revision()
            if expected_revision is not None and previous != expected_revision:
                raise RuntimeError("Active Skill changed while rollback approval was pending")
            if previous == content_revision:
                raise ValueError("Requested Skill revision is already active")
            report = self._validate_snapshot(snapshot)
            if not report.valid or report.candidate_revision != content_revision:
                raise RuntimeError("Stored Skill revision failed integrity validation")
            self._store_snapshot(self.skill_path, previous)
            self._activate_snapshot(snapshot)
            revision = SkillRevision(
                id=uuid4().hex,
                skill_name=self._active_skill_name(),
                content_revision=content_revision,
                previous_revision=previous,
                proposal_id=f"rollback-{uuid4().hex}",
                reason=reason.strip(),
                committed_by=actor,
                approved_by=approver,
                committed_at=datetime.now(UTC),
                rollback_of=content_revision,
            )
            self._append_journal(revision)
            return revision

    def history(self) -> list[SkillRevision]:
        """Read the append-only activation journal in commit order."""
        if not self.journal_path.is_file():
            return []
        return [
            SkillRevision.from_dict(json.loads(line))
            for line in self.journal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _validate_candidate(
        self,
        proposal: SkillProposal,
        candidate: Path,
        initial: list[SkillValidationIssue],
    ) -> SkillValidationReport:
        issues = list(initial)
        if not proposal.changes:
            issues.append(
                SkillValidationIssue("skill.changes_required", "At least one change is required")
            )
        if not proposal.reason.strip():
            issues.append(SkillValidationIssue("skill.reason_required", "A reason is required"))
        if not 0 <= proposal.confidence <= 1:
            issues.append(
                SkillValidationIssue(
                    "skill.confidence_invalid", "Confidence must be between 0 and 1"
                )
            )
        if proposal.expires_at is not None and proposal.expires_at <= datetime.now(UTC):
            issues.append(SkillValidationIssue("skill.expired", "Proposal has expired"))
        for change in proposal.changes:
            if change.content is not None and any(
                pattern.search(change.content) for pattern in _SECRET_PATTERNS
            ):
                issues.append(
                    SkillValidationIssue(
                        "skill.possible_secret",
                        f"Change appears to contain a credential: {change.path}",
                    )
                )
        snapshot_report = self._validate_snapshot(candidate)
        issues.extend(snapshot_report.issues)
        executable = any(_is_executable_change(change.path) for change in proposal.changes)
        if executable:
            issues.append(
                SkillValidationIssue(
                    "skill.executable_review",
                    "Executable content changed and requires explicit review",
                    severity="warning",
                )
            )
        return SkillValidationReport(
            issues=tuple(issues),
            candidate_revision=snapshot_report.candidate_revision,
            requires_executable_review=executable,
        )

    def _validate_snapshot(self, candidate: Path) -> SkillValidationReport:
        issues: list[SkillValidationIssue] = []
        files: list[Path] = []
        total_bytes = 0
        if not candidate.is_dir():
            return SkillValidationReport(
                issues=(SkillValidationIssue("skill.missing", "Skill directory is missing"),)
            )
        for path in sorted(candidate.rglob("*")):
            if path.is_symlink():
                issues.append(
                    SkillValidationIssue(
                        "skill.symlink_forbidden",
                        f"Skill snapshots cannot contain symlinks: {path.relative_to(candidate)}",
                    )
                )
                continue
            if path.is_file():
                files.append(path)
                total_bytes += path.stat().st_size
        if len(files) > self.max_files:
            issues.append(
                SkillValidationIssue(
                    "skill.too_many_files",
                    f"Skill exceeds the {self.max_files}-file limit",
                )
            )
        if total_bytes > self.max_bytes:
            issues.append(
                SkillValidationIssue(
                    "skill.too_large",
                    f"Skill exceeds the {self.max_bytes}-byte limit",
                )
            )

        skill_md = candidate / "SKILL.md"
        if not skill_md.is_file():
            issues.append(SkillValidationIssue("skill.manifest_missing", "SKILL.md is required"))
        else:
            try:
                frontmatter = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
                if frontmatter.name != self._active_skill_name():
                    issues.append(
                        SkillValidationIssue(
                            "skill.identity_changed",
                            "A Skill proposal cannot change the Skill name",
                        )
                    )
            except (OSError, UnicodeError, ValueError) as error:
                issues.append(
                    SkillValidationIssue("skill.frontmatter_invalid", f"Invalid SKILL.md: {error}")
                )

        scripts = candidate / "scripts"
        if scripts.is_dir():
            for path in sorted(scripts.rglob("*.py")):
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    source = path.read_text(encoding="utf-8")
                    compile(source, str(path.relative_to(candidate)), "exec")
                except (OSError, UnicodeError, SyntaxError) as error:
                    issues.append(
                        SkillValidationIssue(
                            "skill.python_invalid",
                            f"Invalid Python script {path.relative_to(candidate)}: {error}",
                        )
                    )
        revision = None
        if not any(issue.severity == "error" for issue in issues):
            revision = _directory_revision(candidate)
        return SkillValidationReport(tuple(issues), revision)

    def _active_skill_name(self) -> str:
        skill_md = self.skill_path / "SKILL.md"
        if not skill_md.is_file():
            raise ValueError(f"Active Skill has no SKILL.md: {self.skill_path}")
        return _parse_frontmatter(skill_md.read_text(encoding="utf-8")).name

    def _persist_stage(
        self,
        proposal: SkillProposal,
        report: SkillValidationReport,
    ) -> StagedSkillProposal:
        staged = StagedSkillProposal(
            proposal=proposal,
            validation=report,
            status="validated" if report.valid else "rejected",
        )
        self._write_stage(staged)
        return staged

    def _write_stage(self, staged: StagedSkillProposal) -> None:
        _require_identifier(staged.proposal.id)
        _atomic_write(
            self.pending_root / staged.proposal.id / "proposal.json",
            json.dumps(staged.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )

    def _load_stage(self, proposal_id: str) -> StagedSkillProposal:
        _require_identifier(proposal_id)
        path = self.pending_root / proposal_id / "proposal.json"
        if not path.is_file():
            raise KeyError(f"Unknown Skill proposal: {proposal_id}")
        return StagedSkillProposal.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _store_snapshot(self, source: Path, revision: str) -> None:
        if not _REVISION.fullmatch(revision):
            raise ValueError("Invalid Skill revision identifier")
        destination = self.revisions_root / revision
        if destination.exists():
            if _directory_revision(destination) != revision:
                raise RuntimeError(f"Stored Skill revision is corrupt: {revision}")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{revision}.", dir=destination.parent))
        try:
            shutil.rmtree(temporary)
            shutil.copytree(source, temporary, symlinks=True)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def _activate_snapshot(self, snapshot: Path) -> None:
        parent = self.skill_path.parent
        incoming = Path(tempfile.mkdtemp(prefix=".skill-incoming.", dir=parent))
        outgoing = parent / f".skill-previous.{uuid4().hex}"
        try:
            shutil.rmtree(incoming)
            shutil.copytree(snapshot, incoming, symlinks=True)
            os.replace(self.skill_path, outgoing)
            try:
                os.replace(incoming, self.skill_path)
            except BaseException:
                os.replace(outgoing, self.skill_path)
                raise
            shutil.rmtree(outgoing)
        finally:
            if incoming.exists():
                shutil.rmtree(incoming)

    def _append_journal(self, revision: SkillRevision) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(revision.to_dict(), ensure_ascii=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        self.state_root.mkdir(parents=True, exist_ok=True)
        with _PROCESS_LOCK, self.lock_path.open("a+b") as lock_file:
            try:
                import fcntl
            except ImportError:  # pragma: no cover - non-Unix fallback
                yield
                return
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _safe_relative_path(raw: str) -> PurePosixPath | None:
    if not raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _is_executable_change(raw: str) -> bool:
    path = _safe_relative_path(raw)
    return path is not None and len(path.parts) > 1 and path.parts[0] == "scripts"


def _parse_frontmatter(content: str) -> SkillFrontmatter:
    if not content.startswith("---"):
        raise ValueError("YAML frontmatter is required")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("YAML frontmatter is not closed")
    payload = yaml.safe_load(parts[1])
    if not isinstance(payload, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return SkillFrontmatter(**payload)


def _directory_revision(root: Path) -> str:
    if not root.is_dir():
        raise ValueError(f"Skill directory does not exist: {root}")
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative_text = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"Skill packages cannot contain symlinks: {relative_text}")
        if path.is_file():
            files.append(path)
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        mode = stat.S_IMODE(path.stat().st_mode)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(mode.to_bytes(4, "big"))
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _require_identifier(value: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid Skill proposal identifier")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "SKILL_JOURNAL_SCHEMA_VERSION",
    "SkillEvolutionStore",
    "SkillFileChange",
    "SkillProposal",
    "SkillRevision",
    "SkillValidationIssue",
    "SkillValidationReport",
    "StagedSkillProposal",
]
