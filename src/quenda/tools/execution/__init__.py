"""
Execution tools for Quenda.

- CommandRunner: Unified local process execution primitive (internal)
- run_command: Execute commands with argv list (model-visible)
- run_shell: Execute shell commands (compatibility wrapper)
- execute_python: Execute Python code in subprocess
"""

from quenda.tools.execution.command import (
    CommandRequest,
    CommandResult,
    CommandRunner,
    ExecutionLimits,
)
from quenda.tools.execution.command_tool import (
    RunCommandTool,
    get_run_command_tool,
)
from quenda.tools.execution.shell import (
    RunShellTool,
    ShellConfig,
)
from quenda.tools.execution.code import (
    PythonExecutionTool,
    SandboxConfig,
    build_python_env,
    get_python_execution_tool,
)

__all__ = [
    # CommandRunner (internal primitive)
    "CommandRunner",
    "CommandRequest",
    "CommandResult",
    "ExecutionLimits",
    # Tools (model-visible)
    "RunCommandTool",
    "get_run_command_tool",
    "RunShellTool",
    "ShellConfig",
    "PythonExecutionTool",
    "SandboxConfig",
    "get_python_execution_tool",
    # Helper functions
    "build_python_env",
]


def get_execution_tools(
    workspace_root: str,
) -> list:
    """Get execution tools."""
    from pathlib import Path

    workspace = Path(workspace_root)
    return [
        RunCommandTool(workspace),
        RunShellTool(workspace),
        PythonExecutionTool(workspace),
    ]
