"""Revisioned, policy-controlled evolution for Agent-owned Markdown memory."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import uuid4

MEMORY_JOURNAL_SCHEMA_VERSION = "quenda.memory-journal/v1"
_PROCESS_LOCK = threading.RLock()
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*[^\s]{12,}"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class MemoryTarget(StrEnum):
    """Agent-owned documents eligible for revisioned evolution."""

    CORE_MEMORY = "core_memory"
    USER_PROFILE = "user_profile"
    IDENTITY = "identity"
    SOUL = "soul"

    @property
    def filename(self) -> str:
        return {
            MemoryTarget.CORE_MEMORY: "MEMORY.md",
            MemoryTarget.USER_PROFILE: "USER.md",
            MemoryTarget.IDENTITY: "IDENTITY.md",
            MemoryTarget.SOUL: "SOUL.md",
        }[self]


class MemoryWriteMode(StrEnum):
    """Who may turn a validated proposal into a committed revision."""

    DISABLED = "disabled"
    REVIEW = "review"
    AUTOMATIC = "automatic"


@dataclass(frozen=True)
class MemoryEvolutionPolicy:
    """Write authority policy; validation and journaling remain mandatory."""

    write_mode: MemoryWriteMode = MemoryWriteMode.AUTOMATIC


@dataclass(frozen=True)
class EvolutionObservation:
    """Evidence that may justify a future proposal but cannot mutate state."""

    content: str
    kind: Literal["preference", "fact", "correction", "pattern", "forget"]
    source_run_id: str = ""
    confidence: float = 1.0
    id: str = field(default_factory=lambda: uuid4().hex)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class MemoryProposal:
    """A complete-document candidate awaiting validation and approval."""

    target: MemoryTarget
    proposed_content: str
    reason: str
    expected_revision: str | None = None
    source_run_id: str = ""
    confidence: float = 1.0
    observation_ids: tuple[str, ...] = ()
    id: str = field(default_factory=lambda: uuid4().hex)
    proposed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["target"] = self.target.value
        payload["proposed_at"] = self.proposed_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> MemoryProposal:
        raw_observations = payload.get("observation_ids", ())
        observations = (
            tuple(str(item) for item in raw_observations)
            if isinstance(raw_observations, list | tuple)
            else ()
        )
        return cls(
            target=MemoryTarget(str(payload["target"])),
            proposed_content=str(payload["proposed_content"]),
            reason=str(payload["reason"]),
            expected_revision=(
                str(payload["expected_revision"])
                if payload.get("expected_revision") is not None
                else None
            ),
            source_run_id=str(payload.get("source_run_id", "")),
            confidence=float(payload.get("confidence", 1.0)),
            observation_ids=observations,
            id=str(payload.get("id") or uuid4().hex),
            proposed_at=(
                datetime.fromisoformat(str(payload["proposed_at"]))
                if payload.get("proposed_at")
                else datetime.now(UTC)
            ),
        )


@dataclass(frozen=True)
class MemoryValidationIssue:
    """One machine-readable proposal validation finding."""

    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class MemoryValidationReport:
    """Validation result that callers can review before requesting approval."""

    issues: tuple[MemoryValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class MemoryValidator:
    """Conservative, deterministic checks for proposed Markdown state."""

    def __init__(self, *, max_bytes: int = 65_536) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.max_bytes = max_bytes

    def validate(self, proposal: MemoryProposal) -> MemoryValidationReport:
        issues: list[MemoryValidationIssue] = []
        content = proposal.proposed_content
        if not content.strip():
            issues.append(MemoryValidationIssue("memory.empty", "Memory cannot be empty"))
        if "\x00" in content:
            issues.append(MemoryValidationIssue("memory.nul", "Memory cannot contain NUL bytes"))
        if len(content.encode("utf-8")) > self.max_bytes:
            issues.append(
                MemoryValidationIssue(
                    "memory.too_large",
                    f"Memory exceeds the {self.max_bytes}-byte limit",
                )
            )
        if not proposal.reason.strip():
            issues.append(
                MemoryValidationIssue(
                    "memory.reason_required",
                    "A human-readable reason is required",
                )
            )
        if not 0 <= proposal.confidence <= 1:
            issues.append(
                MemoryValidationIssue(
                    "memory.invalid_confidence",
                    "Proposal confidence must be between 0 and 1",
                )
            )
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
            issues.append(
                MemoryValidationIssue(
                    "memory.possible_secret",
                    "Proposed memory appears to contain a credential or private key",
                )
            )
        return MemoryValidationReport(tuple(issues))


@dataclass(frozen=True)
class MemoryRevision:
    """One committed, append-only journal record."""

    id: str
    target: MemoryTarget
    content_revision: str
    previous_revision: str | None
    proposal_id: str
    reason: str
    committed_by: str
    approved_by: str | None
    automatic: bool
    committed_at: datetime
    source_run_id: str = ""
    rollback_of: str | None = None
    schema_version: str = MEMORY_JOURNAL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["target"] = self.target.value
        payload["committed_at"] = self.committed_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> MemoryRevision:
        return cls(
            id=str(payload["id"]),
            target=MemoryTarget(str(payload["target"])),
            content_revision=str(payload["content_revision"]),
            previous_revision=(
                str(payload["previous_revision"])
                if payload.get("previous_revision") is not None
                else None
            ),
            proposal_id=str(payload["proposal_id"]),
            reason=str(payload["reason"]),
            committed_by=str(
                payload.get("committed_by") or payload.get("approved_by") or "unknown"
            ),
            approved_by=(
                str(payload["approved_by"])
                if payload.get("approved_by") is not None
                else None
            ),
            automatic=bool(payload.get("automatic", False)),
            committed_at=datetime.fromisoformat(str(payload["committed_at"])),
            source_run_id=str(payload.get("source_run_id", "")),
            rollback_of=(
                str(payload["rollback_of"])
                if payload.get("rollback_of") is not None
                else None
            ),
            schema_version=str(
                payload.get("schema_version", MEMORY_JOURNAL_SCHEMA_VERSION)
            ),
        )


class MemoryEvolutionStore:
    """Commit approved proposals and preserve reversible local history."""

    def __init__(
        self,
        agent_home: Path | str,
        *,
        validator: MemoryValidator | None = None,
        policy: MemoryEvolutionPolicy | None = None,
    ) -> None:
        self.agent_home = Path(agent_home).expanduser().resolve()
        self.state_root = self.agent_home / ".quenda" / "evolution" / "memory"
        self.revisions_root = self.state_root / "revisions"
        self.journal_path = self.state_root / "journal.jsonl"
        self.lock_path = self.state_root / "write.lock"
        self.validator = validator or MemoryValidator()
        self.policy = policy or MemoryEvolutionPolicy()

    def current_revision(self, target: MemoryTarget) -> str | None:
        path = self.agent_home / target.filename
        if not path.is_file():
            return None
        return _content_revision(path.read_text(encoding="utf-8"))

    def validate(self, proposal: MemoryProposal) -> MemoryValidationReport:
        return self.validator.validate(proposal)

    def stage(self, proposal: MemoryProposal) -> Path:
        """Persist a validated proposal for later review without mutating memory."""
        report = self.validate(proposal)
        if not report.valid:
            codes = ", ".join(issue.code for issue in report.issues)
            raise ValueError(f"Invalid memory proposal: {codes}")
        path = self.state_root / "pending" / f"{proposal.id}.json"
        _atomic_write(
            path,
            json.dumps(proposal.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
        return path

    def pending(self) -> list[MemoryProposal]:
        """Return staged proposals in stable creation order."""
        pending_root = self.state_root / "pending"
        if not pending_root.is_dir():
            return []
        proposals = [
            MemoryProposal.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(pending_root.glob("*.json"))
        ]
        return sorted(proposals, key=lambda item: (item.proposed_at, item.id))

    def apply(
        self,
        proposal: MemoryProposal,
        *,
        actor: str = "evolution-policy",
        approved_by: str | None = None,
    ) -> MemoryRevision:
        """Commit a proposal when the configured write policy grants authority."""
        return self._apply(
            proposal,
            actor=actor,
            approved_by=approved_by,
            rollback_of=None,
        )

    def _apply(
        self,
        proposal: MemoryProposal,
        *,
        actor: str,
        approved_by: str | None,
        rollback_of: str | None,
    ) -> MemoryRevision:
        actor = actor.strip()
        approver = (approved_by.strip() or None) if approved_by is not None else None
        if not actor:
            raise ValueError("Memory evolution actor is required")
        if self.policy.write_mode is MemoryWriteMode.DISABLED:
            raise PermissionError("Memory evolution writes are disabled")
        if self.policy.write_mode is MemoryWriteMode.REVIEW and not approver:
            raise PermissionError("Memory evolution requires explicit review")
        report = self.validate(proposal)
        if not report.valid:
            codes = ", ".join(issue.code for issue in report.issues)
            raise ValueError(f"Invalid memory proposal: {codes}")

        with self._write_lock():
            previous = self.current_revision(proposal.target)
            if (
                proposal.expected_revision is not None
                and proposal.expected_revision != previous
            ):
                raise RuntimeError(
                    "Memory changed after this proposal was created; review it again"
                )
            content_revision = _content_revision(proposal.proposed_content)
            if content_revision == previous:
                raise ValueError("Memory proposal does not change the target")

            target_path = self.agent_home / proposal.target.filename
            if previous is not None:
                self._store_revision_blob(
                    proposal.target,
                    previous,
                    target_path.read_text(encoding="utf-8"),
                )
            self._store_revision_blob(
                proposal.target,
                content_revision,
                proposal.proposed_content,
            )
            _atomic_write(
                target_path,
                proposal.proposed_content,
            )
            revision = MemoryRevision(
                id=uuid4().hex,
                target=proposal.target,
                content_revision=content_revision,
                previous_revision=previous,
                proposal_id=proposal.id,
                reason=proposal.reason.strip(),
                committed_by=actor,
                approved_by=approver,
                automatic=approver is None,
                committed_at=datetime.now(UTC),
                source_run_id=proposal.source_run_id,
                rollback_of=rollback_of,
            )
            self._append_journal(revision)
            return revision

    def rollback(
        self,
        target: MemoryTarget,
        content_revision: str,
        *,
        actor: str = "evolution-policy",
        approved_by: str | None = None,
        reason: str,
    ) -> MemoryRevision:
        """Restore a known immutable revision as a new audited commit."""
        snapshot = self._revision_path(target, content_revision)
        if not snapshot.is_file():
            raise KeyError(f"Unknown {target.value} revision: {content_revision}")
        proposal = MemoryProposal(
            target=target,
            proposed_content=snapshot.read_text(encoding="utf-8"),
            reason=reason,
            expected_revision=self.current_revision(target),
        )
        return self._apply(
            proposal,
            actor=actor,
            approved_by=approved_by,
            rollback_of=content_revision,
        )

    def history(self, target: MemoryTarget | None = None) -> list[MemoryRevision]:
        if not self.journal_path.is_file():
            return []
        revisions: list[MemoryRevision] = []
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            revision = MemoryRevision.from_dict(json.loads(line))
            if target is None or revision.target is target:
                revisions.append(revision)
        return revisions

    def _store_revision_blob(
        self,
        target: MemoryTarget,
        revision: str,
        content: str,
    ) -> None:
        path = self._revision_path(target, revision)
        if not path.exists():
            _atomic_write(path, content)

    def _revision_path(self, target: MemoryTarget, revision: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", revision) is None:
            raise ValueError("Invalid memory revision identifier")
        return self.revisions_root / target.value / f"{revision}.md"

    def _append_journal(self, revision: MemoryRevision) -> None:
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


def _content_revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
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
    "EvolutionObservation",
    "MEMORY_JOURNAL_SCHEMA_VERSION",
    "MemoryEvolutionStore",
    "MemoryEvolutionPolicy",
    "MemoryProposal",
    "MemoryRevision",
    "MemoryTarget",
    "MemoryWriteMode",
    "MemoryValidationIssue",
    "MemoryValidationReport",
    "MemoryValidator",
]
