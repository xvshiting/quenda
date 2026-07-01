"""
run_shell tool - Execute and verify.

The controlled escape hatch for operations not covered by specialized tools.

Use it for:
- Running tests: run_shell("pytest tests/ -q")
- Git operations: run_shell("git status")
- Package management: run_shell("npm install")
- Build commands: run_shell("python -m build")

Security: Dangerous commands are blocked (rm -rf /, mkfs, etc.)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


@dataclass
class ShellConfig:
    """Configuration for run_shell tool."""

    default_timeout: int = 30
    max_timeout: int = 300
    max_output_chars: int = 100000  # 100KB max output


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


def _validate_path(workspace: Path, path: str) -> tuple[Path, str | None]:
    """Validate path is within workspace. Returns (resolved_path, error_message)."""
    try:
        resolved = (workspace / path).resolve()
        if not str(resolved).startswith(str(workspace.resolve())):
            return resolved, "Access denied - path outside workspace"
        return resolved, None
    except Exception as e:
        return Path(path), f"Invalid path: {e}"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text if needed. Returns (text, was_truncated)."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]", True
    return text, False


def _is_command_blocked(command: str) -> str | None:
    """Check if command matches any blocked pattern."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "Command blocked by security policy"
    return None


class RunShellTool(Tool):
    """
    Execute shell commands.

    Covers: pytest, git, npm, python, docker, and all other CLI tools.

    This is the escape hatch for operations not covered by specialized tools.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: ShellConfig | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or ShellConfig()

    @property
    @override
    def name(self) -> str:
        return "run_shell"

    @property
    @override
    def description(self) -> str:
        return "Execute a shell command. Use for tests, git, package managers, and other CLI operations."

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
                    "description": f"Timeout in seconds (max {self.config.max_timeout}).",
                    "default": self.config.default_timeout,
                },
            },
            "required": ["command"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd", ".")
        timeout = kwargs.get("timeout", self.config.default_timeout)

        if not isinstance(command, str):
            return ToolResult("", self.name, "Error: command must be a string", is_error=True)

        # Security check
        blocked_error = _is_command_blocked(command)
        if blocked_error:
            return ToolResult("", self.name, f"Error: {blocked_error}", is_error=True)

        # Validate working directory
        work_dir, error = _validate_path(self.workspace, cwd if isinstance(cwd, str) else ".")
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        if not work_dir.exists():
            return ToolResult("", self.name, f"Error: Directory not found: {cwd}", is_error=True)

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
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
            output, truncated = _truncate(output, self.config.max_output_chars)

            if result.returncode != 0:
                output += f"\n\n[exit code: {result.returncode}]"

            if truncated:
                output += "\n[output truncated]"

            # Build display_hint (shortened command) and result_summary
            display_hint = command if len(command) <= 40 else command[:37] + "..."
            result_summary = f"exit {result.returncode}" if result.returncode != 0 else "success"

            return ToolResult(
                "",
                self.name,
                output,
                is_error=result.returncode != 0,
                display_hint=display_hint,
                result_summary=result_summary,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                "",
                self.name,
                f"Error: Command timed out after {timeout_seconds} seconds",
                is_error=True,
            )
        except FileNotFoundError:
            return ToolResult("", self.name, "Error: Command not found", is_error=True)
        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)