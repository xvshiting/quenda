"""
CommandRunner - Unified local process execution primitive.

This module provides a single execution primitive for all local command
execution in Quenda. It handles:

- Process spawning with argv list (shell=False)
- stdin/stdout/stderr handling
- Timeout with process-group termination
- Output truncation
- Exit code reporting

ADR-029 Compliance:
- CommandRunner provides process isolation and lifecycle control
- It does NOT provide filesystem or network sandboxing
- Security policy (permissions, workspace validation) belongs in Tool wrappers

Security Statement:
- cwd controls where the process starts, not what it can access
- A subprocess can still read ~/.ssh, access network, or spawn children
- Strong isolation belongs to a future SandboxBackend
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionLimits:
    """
    Configurable limits for command execution.

    These are hard limits that can be enforced:
    - Input/output size
    - Execution time
    - Process lifecycle

    Unlike the old SandboxConfig, these do not include:
    - Module whitelists
    - AST validation
    - Import restrictions
    """

    default_timeout: int = 30
    max_timeout: int = 300
    max_output_chars: int = 100_000  # 100KB
    max_stdin_bytes: int = 1_000_000  # 1MB


@dataclass(frozen=True)
class CommandRequest:
    """
    Request to execute a command.

    Attributes:
        argv: Command and arguments as a list (e.g., ["python", "-c", "print(1)"])
        cwd: Working directory for the command
        stdin: Optional input to pass to stdin
        env: Optional environment variables (merged with os.environ)
        timeout: Timeout in seconds

    Note:
        - argv is a list, not a string; use ["bash", "-lc", command] for shell
        - env is merged, not replaced; None means use current environment
        - cwd should be validated by the caller (workspace boundary check)
    """

    argv: list[str]
    cwd: Path
    stdin: str | None = None
    env: dict[str, str] | None = None
    timeout: int = 30


@dataclass(frozen=True)
class CommandResult:
    """
    Result of command execution.

    Attributes:
        exit_code: Process exit code (0 for success)
        stdout: Captured standard output
        stderr: Captured standard error
        timed_out: Whether the process was killed due to timeout
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CommandRunner:
    """
    Unified command execution service.

    This is the sole local process primitive in Quenda. All tools that need
    to execute commands (run_command, execute_python, run_shell) should use
    this class.

    Responsibilities:
    - Start subprocess with shell=False
    - Handle stdin/stdout/stderr
    - Enforce timeout with process-group termination
    - Truncate output
    - Report exit code

    NOT responsible for:
    - PermissionPolicy
    - Workspace authorization
    - Dangerous command filtering
    - Skill discovery
    - PYTHONPATH assembly

    Example:
        runner = CommandRunner()
        result = runner.run(CommandRequest(
            argv=[sys.executable, "-c", "print('hello')"],
            cwd=Path("."),
            timeout=10,
        ))
        print(result.stdout)  # "hello\\n"
    """

    def __init__(self, limits: ExecutionLimits | None = None) -> None:
        self.limits = limits or ExecutionLimits()

    def run(self, request: CommandRequest) -> CommandResult:
        """
        Execute a command.

        Args:
            request: The command request containing argv, cwd, stdin, env, timeout

        Returns:
            CommandResult with exit_code, stdout, stderr, timed_out
        """
        # Validate stdin size
        if request.stdin and len(request.stdin.encode("utf-8")) > self.limits.max_stdin_bytes:
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr=f"stdin exceeds {self.limits.max_stdin_bytes} bytes limit",
            )

        # Clamp timeout
        timeout = min(request.timeout, self.limits.max_timeout)

        # Build environment
        env = self._build_env(request.env)

        # Validate executable exists
        if not request.argv:
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr="argv is empty",
            )

        executable = request.argv[0]
        if not self._executable_exists(executable, env):
            return CommandResult(
                exit_code=127,  # Standard "command not found" exit code
                stdout="",
                stderr=f"executable not found: {executable}",
            )

        # Ensure cwd exists
        if not request.cwd.exists():
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr=f"working directory does not exist: {request.cwd}",
            )

        try:
            return self._execute(request, env, timeout)
        except Exception as e:
            logger.exception("Command execution failed")
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr=f"execution error: {e}",
            )

    def _execute(
        self,
        request: CommandRequest,
        env: dict[str, str],
        timeout: int,
    ) -> CommandResult:
        """Execute the command with process-group management."""
        is_windows = sys.platform == "win32"

        # On Windows, we don't use start_new_session; on Unix we do for process group
        start_new_session = not is_windows

        process = subprocess.Popen(
            request.argv,
            cwd=request.cwd,
            env=env,
            stdin=subprocess.PIPE if request.stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            start_new_session=start_new_session,
        )

        try:
            stdout, stderr = process.communicate(
                input=request.stdin,
                timeout=timeout,
            )
            timed_out = False
        except subprocess.TimeoutExpired:
            # Kill the process group
            self._kill_process_tree(process)
            # Collect any output that was buffered
            stdout, stderr = process.communicate()
            timed_out = True
            logger.warning(
                f"Command timed out after {timeout}s: {' '.join(request.argv[:3])}..."
            )

        # Truncate output
        stdout = self._truncate(stdout)
        stderr = self._truncate(stderr)

        return CommandResult(
            exit_code=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
        )

    def _kill_process_tree(self, process: subprocess.Popen[str]) -> None:
        """
        Kill a process and all its children.

        On Unix, kills the process group.
        On Windows, uses taskkill to kill the process tree.
        """
        if sys.platform == "win32":
            # On Windows, use taskkill to kill the process tree
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                # Fallback: just kill the main process
                process.kill()
        else:
            # On Unix, kill the process group
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                # Process already dead
                pass
            except Exception:
                # Fallback: kill the process directly
                process.kill()

    def _build_env(self, overrides: dict[str, str] | None) -> dict[str, str]:
        """Build environment with optional overrides."""
        env = os.environ.copy()
        if overrides:
            env.update(overrides)
        return env

    def _truncate(self, text: str) -> str:
        """Truncate text to max output size."""
        if len(text) > self.limits.max_output_chars:
            return text[: self.limits.max_output_chars] + "\n... [output truncated]"
        return text

    def _executable_exists(self, executable: str, env: dict[str, str]) -> bool:
        """Check if executable exists in PATH or is an absolute path."""
        # Absolute path
        if os.path.isabs(executable):
            return os.path.isfile(executable)

        # Check PATH
        path_dirs = env.get("PATH", os.environ.get("PATH", "")).split(os.pathsep)

        # On Windows, try with extensions
        if sys.platform == "win32":
            extensions = env.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")
            for directory in path_dirs:
                for ext in extensions:
                    full_path = os.path.join(directory, executable + ext)
                    if os.path.isfile(full_path):
                        return True
        else:
            for directory in path_dirs:
                full_path = os.path.join(directory, executable)
                if os.path.isfile(full_path):
                    return True

        return False


__all__ = [
    "ExecutionLimits",
    "CommandRequest",
    "CommandResult",
    "CommandRunner",
]
