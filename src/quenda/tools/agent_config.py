"""Framework tool for guarded Agent configuration changes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import override

from quenda.host.config_inspection import INSPECTION_SECTIONS, AgentConfigInspector
from quenda.host.config_mutation import AgentConfigEditor
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.runtime.permission import PermissionPolicy


class ApplyAgentConfigPatchTool(Tool):
    """Preview or commit one validated JSON Merge Patch."""

    def __init__(
        self,
        *,
        workspace: Path,
        agent_package_path: Path,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self._workspace = workspace.expanduser().resolve()
        self._agent_package_path = agent_package_path.expanduser().resolve()
        self.permission_policy = permission_policy

    @property
    @override
    def name(self) -> str:
        return "apply_agent_config_patch"

    @property
    @override
    def description(self) -> str:
        return (
            "Preview or commit a validated JSON Merge Patch to the current Agent "
            "Home config.yaml. Preserves unrelated keys, redacts secrets in diffs, "
            "checks revisions, records rollback history, and requests user approval "
            "before commit. Preview first, then commit with expected_revision."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "object",
                    "description": (
                        "RFC 7396 JSON Merge Patch. Objects merge recursively, "
                        "arrays replace, and null removes a key."
                    ),
                },
                "commit": {
                    "type": "boolean",
                    "default": False,
                    "description": "False previews; true requests approval and commits.",
                },
                "expected_revision": {
                    "type": "string",
                    "description": "Base revision returned by preview.",
                },
            },
            "required": ["patch"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        patch = kwargs.get("patch")
        commit = kwargs.get("commit", False)
        expected_revision = kwargs.get("expected_revision")
        if not isinstance(patch, dict):
            return self._error("patch must be an object")
        if not isinstance(commit, bool):
            return self._error("commit must be a boolean")
        if expected_revision is not None and not isinstance(expected_revision, str):
            return self._error("expected_revision must be a string")

        try:
            result = AgentConfigEditor(
                self._agent_package_path,
                workspace_path=self._workspace,
                permission_policy=self.permission_policy,
            ).apply(
                patch,
                commit=commit,
                expected_revision=expected_revision,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            return self._error(f"Unable to prepare Agent config change: {exc}")

        payload = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)
        is_error = result.status in {"invalid", "conflict", "denied"}
        return ToolResult(
            call_id="",
            name=self.name,
            content=payload,
            is_error=is_error,
            display_hint=str(self._agent_package_path / "config.yaml"),
            result_summary=result.status,
            change_preview=result.diff,
        )

    def _error(self, message: str) -> ToolResult:
        return ToolResult(call_id="", name=self.name, content=message, is_error=True)


class ExplainAgentConfigTool(Tool):
    """Explain normalized Agent configuration without exposing credentials."""

    def __init__(self, *, workspace: Path, agent_package_path: Path) -> None:
        self._workspace = workspace.expanduser().resolve()
        self._agent_package_path = agent_package_path.expanduser().resolve()

    @property
    @override
    def name(self) -> str:
        return "explain_agent_config"

    @property
    @override
    def description(self) -> str:
        return (
            "Explain the current Agent's normalized effective configuration and "
            "the matching live framework capabilities without exposing credential "
            "values. Use before proposing a configuration change."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": sorted(INSPECTION_SECTIONS),
                    "default": "summary",
                }
            },
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        section = kwargs.get("section", "summary")
        if not isinstance(section, str) or section not in INSPECTION_SECTIONS:
            return ToolResult(
                call_id="",
                name=self.name,
                content=(
                    f"section must be one of: {', '.join(sorted(INSPECTION_SECTIONS))}"
                ),
                is_error=True,
            )
        try:
            result = AgentConfigInspector(
                self._agent_package_path,
                workspace_path=self._workspace,
            ).inspect(section)  # type: ignore[arg-type]
        except (OSError, UnicodeError, ValueError) as exc:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Unable to inspect Agent config: {exc}",
                is_error=True,
            )
        return ToolResult(
            call_id="",
            name=self.name,
            content=json.dumps(result, ensure_ascii=False, sort_keys=True),
            is_error=not bool(result["valid"]),
            display_hint=str(self._agent_package_path / "config.yaml"),
            result_summary=("valid" if result["valid"] else "invalid"),
        )


__all__ = ["ApplyAgentConfigPatchTool", "ExplainAgentConfigTool"]
