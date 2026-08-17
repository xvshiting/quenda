"""Guarded, revisioned mutation of one Agent Home configuration."""

from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]

from quenda.host.validation import ValidationReport, validate_agent_configuration
from quenda.runtime.permission import (
    DenyPermissionPolicy,
    PermissionKind,
    PermissionLifetime,
    PermissionPolicy,
    PermissionRequest,
    PermissionScope,
)

MutationStatus = Literal[
    "preview",
    "committed",
    "unchanged",
    "invalid",
    "conflict",
    "denied",
]

_SECRET_MARKERS = ("api_key", "key", "token", "password", "secret", "authorization", "cookie")


@dataclass(frozen=True)
class AgentConfigMutationResult:
    """Observable result of previewing or committing one config patch."""

    status: MutationStatus
    valid: bool
    committed: bool
    base_revision: str
    revision: str
    changed_keys: tuple[str, ...]
    diff: str
    validation: ValidationReport
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "valid": self.valid,
            "committed": self.committed,
            "base_revision": self.base_revision,
            "revision": self.revision,
            "changed_keys": list(self.changed_keys),
            "diff": self.diff,
            "validation": self.validation.to_dict(),
            "message": self.message,
        }


class AgentConfigEditor:
    """Apply validated JSON Merge Patches to one Agent Home config."""

    def __init__(
        self,
        agent_path: Path | str,
        *,
        workspace_path: Path | str | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        path = Path(agent_path).expanduser().resolve()
        self.agent_path = path.parent if path.is_file() else path
        self.workspace_path = (
            Path(workspace_path).expanduser().resolve()
            if workspace_path is not None
            else self.agent_path
        )
        self.config_path = self.agent_path / "config.yaml"
        self.permission_policy = permission_policy or DenyPermissionPolicy()

    def current_revision(self) -> str:
        """Return the content revision of the currently active config."""
        return _revision(self._read_raw())

    def apply(
        self,
        patch: dict[str, Any],
        *,
        commit: bool = False,
        expected_revision: str | None = None,
    ) -> AgentConfigMutationResult:
        """Preview or commit a JSON Merge Patch after full package validation."""
        current_raw = self._read_raw()
        base_revision = _revision(current_raw)
        current_data = self._read_mapping(current_raw)
        candidate_data = _merge_patch(current_data, patch)
        candidate_raw = yaml.safe_dump(
            candidate_data,
            allow_unicode=True,
            sort_keys=False,
        )
        revision = _revision(candidate_raw)
        changed_keys = tuple(sorted(str(key) for key in patch))
        report = validate_agent_configuration(
            self.agent_path,
            candidate_data,
            workspace_path=self.workspace_path,
        )
        diff = _redacted_diff(current_data, candidate_data)

        def result(
            status: MutationStatus,
            *,
            valid: bool = report.valid,
            committed: bool = False,
            message: str = "",
        ) -> AgentConfigMutationResult:
            return AgentConfigMutationResult(
                status=status,
                valid=valid,
                committed=committed,
                base_revision=base_revision,
                revision=revision,
                changed_keys=changed_keys,
                diff=diff,
                validation=report,
                message=message,
            )

        if expected_revision is not None and expected_revision != base_revision:
            return result(
                "conflict",
                valid=False,
                message="Agent config changed since the requested base revision",
            )
        if not report.valid:
            return result("invalid", valid=False, message="Candidate config is invalid")
        if candidate_data == current_data:
            return result("unchanged", message="Patch does not change config.yaml")
        if not commit:
            return result("preview")

        decision = self.permission_policy.decide(
            PermissionRequest(
                kind=PermissionKind.AGENT_CONFIG_WRITE,
                resource=str(self.config_path),
                scope=PermissionScope.PATH,
                reason=(
                    "Commit validated Agent configuration changes to: "
                    + ", ".join(changed_keys)
                ),
                lifetime=PermissionLifetime.RUN,
                tool_name="apply_agent_config_patch",
                tool_args={
                    "base_revision": base_revision,
                    "revision": revision,
                    "changed_keys": list(changed_keys),
                },
                cacheable=False,
            )
        )
        if not decision.allowed:
            return result("denied", message=decision.reason or "Change denied")

        # Recheck immediately before the write so a stale proposal cannot win.
        if self.current_revision() != base_revision:
            return result(
                "conflict",
                valid=False,
                message="Agent config changed while approval was pending",
            )

        self._commit(current_raw, candidate_raw, base_revision, revision, changed_keys)
        return result("committed", committed=True)

    def _read_raw(self) -> str:
        if not self.config_path.is_file():
            return ""
        return self.config_path.read_text(encoding="utf-8")

    @staticmethod
    def _read_mapping(raw: str) -> dict[str, Any]:
        parsed = yaml.safe_load(raw) if raw else {}
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("config.yaml must contain a top-level mapping")
        return parsed

    def _commit(
        self,
        current_raw: str,
        candidate_raw: str,
        base_revision: str,
        revision: str,
        changed_keys: tuple[str, ...],
    ) -> None:
        state_dir = self.agent_path / ".quenda"
        revisions_dir = state_dir / "config-revisions"
        revisions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        revisions_dir.chmod(0o700)
        backup = revisions_dir / f"{base_revision}.yaml"
        if not backup.exists():
            backup.write_text(current_raw, encoding="utf-8")
            backup.chmod(0o600)

        descriptor, temp_name = tempfile.mkstemp(
            prefix=".config-",
            suffix=".yaml.tmp",
            dir=self.agent_path,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(candidate_raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.config_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

        journal = state_dir / "config-journal.jsonl"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "base_revision": base_revision,
            "revision": revision,
            "changed_keys": list(changed_keys),
        }
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        journal.chmod(0o600)


def _merge_patch(current: Any, patch: Any) -> Any:
    """Apply RFC 7396 JSON Merge Patch semantics."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    target = copy.deepcopy(current) if isinstance(current, dict) else {}
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        else:
            target[key] = _merge_patch(target.get(key), value)
    return target


def _revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


_MISSING = object()


def _redact(
    value: Any,
    *,
    parent_key: str = "",
    counterpart: Any = _MISSING,
    changed_label: str = "changed",
) -> Any:
    if parent_key and any(marker in parent_key.lower() for marker in _SECRET_MARKERS):
        return (
            "<redacted>"
            if counterpart is not _MISSING and value == counterpart
            else f"<redacted> ({changed_label})"
        )
    if isinstance(value, dict):
        other = counterpart if isinstance(counterpart, dict) else {}
        return {
            key: _redact(
                item,
                parent_key=str(key),
                counterpart=other.get(key, _MISSING),
                changed_label=changed_label,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, changed_label=changed_label) for item in value]
    return value


def _redacted_diff(current: dict[str, Any], candidate: dict[str, Any]) -> str:
    before = yaml.safe_dump(
        _redact(current, counterpart=candidate, changed_label="current"),
        allow_unicode=True,
        sort_keys=False,
    ).splitlines()
    after = yaml.safe_dump(
        _redact(candidate, counterpart=current, changed_label="changed"),
        allow_unicode=True,
        sort_keys=False,
    ).splitlines()
    return "\n".join(
        difflib.unified_diff(
            before,
            after,
            fromfile="config.yaml@current",
            tofile="config.yaml@candidate",
            lineterm="",
        )
    )


__all__ = ["AgentConfigEditor", "AgentConfigMutationResult", "MutationStatus"]
