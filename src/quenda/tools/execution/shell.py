"""
run_shell tool - Execute shell commands (compatibility wrapper).

DEPRECATED: Use run_command with explicit shell invocation instead:
    run_command(argv=["bash", "-lc", "find . -name '*.py'"])

This tool is kept for backward compatibility. It internally uses CommandRunner.

The controlled escape hatch for operations not covered by specialized tools.

Use it for:
- Running tests: run_shell("pytest tests/ -q")
- Git operations: run_shell("git status")
- Package management: run_shell("npm install")
- Build commands: run_shell("python -m build")

Security: Dangerous commands are blocked (rm -rf /, mkfs, etc.)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.runtime.permission import (
    DenyPermissionPolicy,
    PermissionKind,
    PermissionLifetime,
    PermissionPolicy,
    PermissionRequest,
    PermissionScope,
)
from quenda.tools.execution.command import (
    CommandRequest,
    CommandRunner,
    ExecutionLimits,
)

logger = logging.getLogger(__name__)


# Security: Blocked command patterns
BLOCKED_PATTERNS: list[str] = [
    # Filesystem destruction
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\*",
    r"rm\s+-fr\s+/",
    r"rm\s+-fr\s+~",
    # Disk operations
    r"mkfs",
    r"dd\s+if=.*of=/dev/",
    r">\s*/dev/sd",
    r">\s*/dev/hd",
    # Fork bomb
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
    r":\(\)\{\s*:\|:&\s*\}\s*;:",
    # Dangerous chmod
    r"chmod\s+(-R\s+)?777\s+/",
    r"chmod\s+(-R\s+)?777\s+~",
    # Shutdown/reboot
    r"shutdown",
    r"reboot",
    r"init\s+[06]",
    # User management
    r"userdel",
    r"passwd\s+--",
    # Network dangerous
    r"iptables\s+-F",
    r"iptables\s+-P\s+INPUT\s+DROP",
]


def _is_command_blocked(command: str) -> str | None:
    """Check if command matches any blocked pattern."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "Command blocked by security policy"
    return None


class RunShellTool(Tool):
    """
    Execute shell commands.

    DEPRECATED: Use run_command with explicit shell invocation instead.

    Covers: pytest, git, npm, python, docker, and all other CLI tools.

    This is the escape hatch for operations not covered by specialized tools.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        limits: ExecutionLimits | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.limits = limits or ExecutionLimits()
        self.permission_policy = permission_policy
        self._runner = CommandRunner(self.limits)

    @property
    @override
    def name(self) -> str:
        return "run_shell"

    @property
    @override
    def description(self) -> str:
        return "Execute a shell command. Use for tests, git, package managers, and other CLI operations. Prefer run_command for non-shell commands."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (relative to workspace). Default: workspace root.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (max {self.limits.max_timeout}).",
                    "default": self.limits.default_timeout,
                },
            },
            "required": ["command"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd", ".")
        timeout = kwargs.get("timeout", self.limits.default_timeout)

        if not isinstance(command, str):
            return ToolResult("", self.name, "Error: command must be a string", is_error=True)

        # Security check
        blocked_error = _is_command_blocked(command)
        if blocked_error:
            return ToolResult("", self.name, f"Error: {blocked_error}", is_error=True)

        # Validate working directory
        if not isinstance(cwd, str):
            cwd = "."

        work_dir, error = self._validate_path(self.workspace, cwd)
        if error:
            request = PermissionRequest(
                kind=PermissionKind.SHELL_EXECUTE,
                resource=str(work_dir),
                scope=PermissionScope.PATH,
                reason=f"Running shell command outside workspace: {cwd}",
                lifetime=PermissionLifetime.SESSION,
                tool_name=self.name,
                tool_args={"command": command, "cwd": cwd, "timeout": timeout},
            )
            policy = self.permission_policy or DenyPermissionPolicy()
            decision = policy.decide(request)
            if not decision.allowed:
                return ToolResult("", self.name, f"Error: {decision.reason or error}", is_error=True)

        if not work_dir.exists():
            return ToolResult("", self.name, f"Error: Directory not found: {cwd}", is_error=True)

        # Use CommandRunner with explicit shell invocation
        request = CommandRequest(
            argv=["bash", "-lc", command],
            cwd=work_dir,
            timeout=int(timeout) if isinstance(timeout, (int, float)) else self.limits.default_timeout,
        )

        result = self._runner.run(request)

        # Build display_hint and result_summary
        display_hint = command if len(command) <= 40 else command[:37] + "..."
        result_summary = "timeout" if result.timed_out else (
            f"exit {result.exit_code}" if result.exit_code != 0 else "success"
        )

        # Build output
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")
        if not output_parts:
            output_parts.append("(no output)")

        output = "\n".join(output_parts)

        if result.exit_code != 0:
            output += f"\n\n[exit code: {result.exit_code}]"

        if result.timed_out:
            output += "\n\n[process timed out]"

        return ToolResult(
            "",
            self.name,
            output,
            is_error=result.exit_code != 0 or result.timed_out,
            display_hint=display_hint,
            result_summary=result_summary,
        )

    def _validate_path(self, workspace: Path, path: str) -> tuple[Path, str | None]:
        """Validate path is within workspace. Returns (resolved_path, error_message)."""
        try:
            resolved = (workspace / path).resolve()
            if not str(resolved).startswith(str(workspace.resolve())):
                return resolved, "Access denied - path outside workspace"
            return resolved, None
        except Exception as e:
            return Path(path), f"Invalid path: {e}"


class ShellConfig:
    """
    Configuration for run_shell tool.

    DEPRECATED: Use ExecutionLimits instead.
    """

    def __init__(
        self,
        default_timeout: int = 30,
        max_timeout: int = 300,
        max_output_chars: int = 100000,
    ) -> None:
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.max_output_chars = max_output_chars

    def to_limits(self) -> ExecutionLimits:
        """Convert to ExecutionLimits."""
        return ExecutionLimits(
            default_timeout=self.default_timeout,
            max_timeout=self.max_timeout,
            max_output_chars=self.max_output_chars,
        )
