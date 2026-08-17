"""Read-only framework tool for validating Quenda Agent packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import override

from quenda.host.validation import validate_agent_package
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class ValidateAgentPackageTool(Tool):
    """Expose static Agent validation without granting arbitrary filesystem reads."""

    def __init__(self, *, workspace: Path, agent_package_path: Path) -> None:
        self._workspace = workspace.expanduser().resolve()
        self._agent_package_path = agent_package_path.expanduser().resolve()

    @property
    @override
    def name(self) -> str:
        return "validate_agent_package"

    @property
    @override
    def description(self) -> str:
        return (
            "Validate the current Quenda Agent package, or another package inside "
            "the current workspace. Parses config and references and compiles "
            "extensions without executing extensions, contacting providers, or "
            "resolving credentials."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Optional Agent directory or AGENT.md path. Omit to validate "
                        "the current Agent package; relative paths resolve inside "
                        "the current workspace."
                    ),
                }
            },
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        raw_path = kwargs.get("path")
        try:
            target = self._resolve_target(raw_path)
        except ValueError as exc:
            return ToolResult(
                call_id="",
                name=self.name,
                content=str(exc),
                is_error=True,
            )

        report = validate_agent_package(target, workspace_path=self._workspace)
        return ToolResult(
            call_id="",
            name=self.name,
            content=json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True),
            is_error=not report.valid,
            display_hint=str(target),
            result_summary=(
                f"{report.error_count} error(s), {report.warning_count} warning(s)"
            ),
        )

    def _resolve_target(self, raw_path: object) -> Path:
        if raw_path is None or raw_path == "":
            return self._agent_package_path
        if not isinstance(raw_path, str):
            raise ValueError("path must be a string")

        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = self._workspace / candidate
        resolved = candidate.resolve()
        allowed = any(
            resolved == root or resolved.is_relative_to(root)
            for root in (self._workspace, self._agent_package_path)
        )
        if not allowed:
            raise ValueError(
                "Validation target must be inside the current workspace or Agent package"
            )
        return resolved


__all__ = ["ValidateAgentPackageTool"]
