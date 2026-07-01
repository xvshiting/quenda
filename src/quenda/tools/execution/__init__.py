"""
Execution tools for Kora.

- run_shell: Execute shell commands (escape hatch for tests, git, npm, etc.)
- execute_python: Execute Python code in a sandboxed environment
"""

from quenda.tools.execution.shell import (
    RunShellTool,
    ShellConfig,
)
from quenda.tools.execution.code import (
    PythonExecutionTool,
    SandboxConfig,
)

__all__ = [
    "RunShellTool",
    "ShellConfig",
    "PythonExecutionTool",
    "SandboxConfig",
]


def get_execution_tools(workspace_root: str) -> list:
    """Get execution tools."""
    from pathlib import Path

    workspace = Path(workspace_root)
    return [
        RunShellTool(workspace),
        PythonExecutionTool(workspace),
    ]
