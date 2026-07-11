"""
run_command tool - Execute commands with argv list.

This is the general-purpose command execution tool for Quenda.
It uses the unified CommandRunner internally.

ADR-029 Compliance:
- Uses CommandRunner for process execution
- Handles workspace validation and permission in Tool layer
- Does NOT expose env to model (first version)

For shell syntax, use explicit shell invocation:
    ["bash", "-lc", "find . -name '*.py' | xargs grep TODO"]
"""

from __future__ import annotations

import logging
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
    CommandResult,
    CommandRunner,
    ExecutionLimits,
)

logger = logging.getLogger(__name__)


class RunCommandTool(Tool):
    """
    Execute a command with argv list.

    This is the unified command execution tool. Unlike run_shell which
    takes a shell command string, this tool takes an explicit argv list.

    Examples:
        # Run pytest
        run_command(argv=["pytest", "-q"])

        # Run with stdin
        run_command(argv=["python", "-c", "print(input())"], stdin="hello")

        # Shell syntax (explicit)
        run_command(argv=["bash", "-lc", "find . -name '*.py'"])
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
        return "run_command"

    @property
    @override
    def description(self) -> str:
        return """Execute a command with explicit argv list.

Use for:
- Running tests: run_command(argv=["pytest", "-q"])
- Git operations: run_command(argv=["git", "status"])
- Package managers: run_command(argv=["npm", "install"])
- Build commands: run_command(argv=["python", "-m", "build"])
- Python scripts: run_command(argv=["python", "script.py"])

For shell syntax (pipes, redirects), use explicit shell:
- run_command(argv=["bash", "-lc", "find . -name '*.py' | xargs grep TODO"])
"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command and arguments as a list. First element is the executable.",
                },
                "stdin": {
                    "type": "string",
                    "description": "Optional input to pass to stdin.",
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
            "required": ["argv"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        argv = kwargs.get("argv", [])
        stdin = kwargs.get("stdin")
        cwd = kwargs.get("cwd", ".")
        timeout = kwargs.get("timeout", self.limits.default_timeout)

        # Validate argv
        if not isinstance(argv, list) or not argv:
            return ToolResult(
                "",
                self.name,
                "Error: argv must be a non-empty list of strings",
                is_error=True,
            )

        if not all(isinstance(arg, str) for arg in argv):
            return ToolResult(
                "",
                self.name,
                "Error: argv must contain only strings",
                is_error=True,
            )

        # Validate and resolve cwd
        if not isinstance(cwd, str):
            cwd = "."

        work_dir, cwd_error = self._validate_cwd(cwd)

        if cwd_error:
            # Request permission for workspace-external cwd
            decision = self._request_permission(
                kind=PermissionKind.SHELL_EXECUTE,
                resource=str(work_dir),
                reason=f"Executing command outside workspace: {cwd}",
                tool_args={"argv": argv, "cwd": cwd, "timeout": timeout},
            )
            if not decision.allowed:
                return ToolResult(
                    "",
                    self.name,
                    f"Error: {decision.reason or cwd_error}",
                    is_error=True,
                )

        # Build and execute request
        request = CommandRequest(
            argv=argv,
            cwd=work_dir,
            stdin=stdin if isinstance(stdin, str) else None,
            timeout=int(timeout) if isinstance(timeout, (int, float)) else self.limits.default_timeout,
        )

        result = self._runner.run(request)

        return self._result_to_tool_result(result, argv)

    def _validate_cwd(self, cwd: str) -> tuple[Path, str | None]:
        """
        Validate cwd is within workspace.

        Returns:
            Tuple of (resolved_path, error_message).
            error_message is None if valid or needs permission.
        """
        try:
            resolved = (self.workspace / cwd).resolve()
            if not str(resolved).startswith(str(self.workspace)):
                return resolved, "Working directory is outside workspace"
            return resolved, None
        except Exception as e:
            return Path(cwd), f"Invalid path: {e}"

    def _request_permission(
        self,
        kind: PermissionKind,
        resource: str,
        reason: str,
        tool_args: dict,
    ) -> "PermissionRequest":
        """Request permission for an operation."""
        request = PermissionRequest(
            kind=kind,
            resource=resource,
            scope=PermissionScope.PATH,
            reason=reason,
            lifetime=PermissionLifetime.SESSION,
            tool_name=self.name,
            tool_args=tool_args,
        )
        policy = self.permission_policy or DenyPermissionPolicy()
        return policy.decide(request)

    def _result_to_tool_result(
        self,
        result: CommandResult,
        argv: list[str],
    ) -> ToolResult:
        """Convert CommandResult to ToolResult."""
        # Build output
        output_parts = []

        if result.stdout:
            output_parts.append(result.stdout)

        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        if not output_parts:
            output_parts.append("(no output)")

        output = "\n".join(output_parts)

        # Add exit code info
        if result.exit_code != 0:
            output += f"\n\n[exit code: {result.exit_code}]"

        if result.timed_out:
            output += "\n\n[process timed out]"

        # Build display hint (shortened command)
        cmd_str = " ".join(argv)
        display_hint = cmd_str if len(cmd_str) <= 40 else cmd_str[:37] + "..."

        # Build result summary
        if result.timed_out:
            result_summary = "timeout"
        elif result.exit_code != 0:
            result_summary = f"exit {result.exit_code}"
        else:
            result_summary = "success"

        return ToolResult(
            "",
            self.name,
            output,
            is_error=result.exit_code != 0 or result.timed_out,
            display_hint=display_hint,
            result_summary=result_summary,
        )


def get_run_command_tool(
    workspace_root: Path | str,
    limits: ExecutionLimits | None = None,
    permission_policy: PermissionPolicy | None = None,
) -> Tool:
    """
    Get the run_command tool.

    Args:
        workspace_root: Workspace directory for path validation.
        limits: Execution limits.
        permission_policy: Permission policy for operations.

    Returns:
        RunCommandTool instance.
    """
    return RunCommandTool(workspace_root, limits, permission_policy)


__all__ = [
    "RunCommandTool",
    "get_run_command_tool",
]
