"""
execute_python tool - Execute Python code in a subprocess.

This tool provides a convenient way to execute Python code. It uses
the unified CommandRunner internally.

ADR-029 Compliance:
- Uses subprocess execution (not in-process exec)
- Real Python behavior (sys, os, requests, etc. work normally)
- Skill Python path via PYTHONPATH
- Killable processes with real timeout

Security Statement:
- cwd controls where the process starts, not what it can access
- Python code can still read files, access network, spawn children
- Strong isolation belongs to a future SandboxBackend
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.tools.execution.command import (
    CommandRequest,
    CommandRunner,
    ExecutionLimits,
)

if TYPE_CHECKING:
    from quenda.host.skill.package import SkillPackage

logger = logging.getLogger(__name__)


# =============================================================================
# Legacy types for backward compatibility
# =============================================================================


class SandboxConfig:
    """
    Configuration for Python execution.

    DEPRECATED: Use ExecutionLimits instead.

    This class is kept for backward compatibility but the module whitelist
    and AST validation features have been removed. All fields except timeout
    and output limits are now ignored.
    """

    def __init__(
        self,
        allowed_modules: list[str] | None = None,
        blocked_modules: list[str] | None = None,
        allowed_builtins: list[str] | None = None,
        default_timeout: int = 30,
        max_timeout: int = 60,
        max_output_bytes: int = 1_000_000,
        max_ast_nodes: int = 5000,
    ) -> None:
        # These are ignored (legacy compatibility)
        self.allowed_modules = allowed_modules or []
        self.blocked_modules = blocked_modules or []
        self.allowed_builtins = allowed_builtins or []
        self.max_ast_nodes = max_ast_nodes

        # These are still used
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.max_output_bytes = max_output_bytes

    def to_limits(self) -> ExecutionLimits:
        """Convert to ExecutionLimits."""
        return ExecutionLimits(
            default_timeout=self.default_timeout,
            max_timeout=self.max_timeout,
            max_output_chars=self.max_output_bytes,
        )


# =============================================================================
# Helper functions
# =============================================================================


def build_python_env(
    active_skills: list[SkillPackage] | None = None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Build environment for Python execution with Skill import paths.

    Adds active Skill `scripts/` directories to PYTHONPATH, allowing
    model to import and reuse Skill Python code.

    Args:
        active_skills: List of active SkillPackage objects
        base_env: Base environment (defaults to os.environ)

    Returns:
        Environment dict with PYTHONPATH set for Skill imports

    Example:
        Skill playwright has scripts/quenda_playwright/capture.py
        Model can write:
            from quenda_playwright.capture import capture_screenshot
    """
    env = dict(base_env or os.environ)

    if not active_skills:
        return env

    # Collect skill script paths
    skill_script_paths: list[str] = []
    for skill in active_skills:
        scripts_dir = skill.path / "scripts"
        if scripts_dir.is_dir():
            skill_script_paths.append(str(scripts_dir))
            logger.debug(f"Added Skill scripts to PYTHONPATH: {scripts_dir}")

    # Merge with existing PYTHONPATH
    if skill_script_paths:
        existing = env.get("PYTHONPATH")
        if existing:
            skill_script_paths.append(existing)

        env["PYTHONPATH"] = os.pathsep.join(skill_script_paths)

    return env


# =============================================================================
# Tool implementation
# =============================================================================


class PythonExecutionTool(Tool):
    """
    Tool to execute Python code.

    This tool executes Python code in a subprocess (not in-process),
    providing real Python behavior with sys, os, and other modules
    working normally.

    Active Skills' `scripts/` directories are automatically added
    to PYTHONPATH for code reuse.
    """

    def __init__(
        self,
        workspace: Path | str | None = None,
        config: SandboxConfig | None = None,
        active_skills: list[SkillPackage] | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()
        self.config = config or SandboxConfig()
        self.active_skills = active_skills
        self._runner = CommandRunner(self.config.to_limits())

    @property
    @override
    def name(self) -> str:
        return "execute_python"

    @property
    @override
    def description(self) -> str:
        return """Execute Python code in a subprocess.

All standard Python modules work normally (sys, os, subprocess, etc.).
Use for data processing, file manipulation, or any task where Python is convenient.

If Skills are active, their `scripts/` directories are available for import:
    from quenda_playwright.capture import capture_screenshot
"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (max {self.config.max_timeout}).",
                    "default": self.config.default_timeout,
                },
            },
            "required": ["code"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        code = kwargs.get("code", "")
        timeout = kwargs.get("timeout", self.config.default_timeout)

        if not isinstance(code, str):
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: code must be a string",
                is_error=True,
            )

        if not code.strip():
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: code cannot be empty",
                is_error=True,
            )

        # Build Python environment with Skill paths
        python_env = build_python_env(self.active_skills)

        # Execute via CommandRunner
        request = CommandRequest(
            argv=[sys.executable, "-"],
            cwd=self.workspace,
            stdin=code,
            env=python_env,
            timeout=int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
        )

        result = self._runner.run(request)

        return self._result_to_tool_result(result)

    def _result_to_tool_result(self, result: Any) -> ToolResult:
        """Convert CommandResult to ToolResult."""
        # Build output
        parts = []

        if result.stdout:
            parts.append(f"[stdout]\n{result.stdout}")

        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr}")

        if not parts:
            parts.append("Execution completed (no output)")

        content = "\n\n".join(parts)

        if result.timed_out:
            content += f"\n\n[process timed out after {self.config.default_timeout}s]"

        return ToolResult(
            call_id="",
            name=self.name,
            content=content,
            is_error=result.exit_code != 0 or result.timed_out,
        )


def get_python_execution_tool(
    workspace: Path | str | None = None,
    config: SandboxConfig | None = None,
) -> Tool:
    """
    Get the Python execution tool.

    Args:
        workspace: Optional workspace directory.
        config: Execution configuration.

    Returns:
        PythonExecutionTool instance.
    """
    return PythonExecutionTool(workspace, config)


__all__ = [
    "PythonExecutionTool",
    "SandboxConfig",
    "build_python_env",
    "get_python_execution_tool",
]
