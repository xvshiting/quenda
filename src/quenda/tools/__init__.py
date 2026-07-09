"""
Built-in tools for Quenda.

## Organization

Tools are organized by capability domain:

```
tools/
├── filesystem/     # File operations
│   ├── listing.py   → list_files
│   ├── searching.py → search_text
│   ├── reading.py   → read_file
│   └── editing.py   → write_file, apply_patch
├── execution/      # Command execution
│   └── shell.py     → run_shell
├── network/        # Network operations
│   ├── http.py      → http_request
│   └── fetching.py  → web_fetch
└── security/       # Security patterns
```

## Tool Bundles

### Core Tools (10)
Basic file, execution, and interaction tools:
- list_files, search_text, read_file, write_file, apply_patch
- execute_python, run_shell
- request_interaction, request_skill_activation, activate_resource

Use `get_core_tools()` for the minimal essential toolset.

### Extended Tools (12)
Framework-level tools combined:
- Core (10) + Network (2)

Use `get_extended_tools()` when an agent explicitly needs both local
execution and network access.

## Architecture

    Agent Layer (semantic tool interfaces)
         ↓
    Tool Abstraction Layer (limits, pagination, error handling)
         ↓
    Backend Layer (ripgrep, elasticsearch, database, MCP)
"""

# Core tools (minimal set for Coding Agents)
from quenda.tools.filesystem import (
    ApplyPatchTool,
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
    WriteFileTool,
    get_filesystem_tools,
)

from quenda.tools.execution import (
    PythonExecutionTool,
    RunShellTool,
    SandboxConfig,
    ShellConfig,
    get_execution_tools,
)

from quenda.tools.network import (
    HTTPRequestTool,
    WebFetchTool,
    get_network_tools,
)

# Decorator
from quenda.tools.decorator import FunctionTool, tool

# Interaction tool (framework-reserved)
from quenda.tools.interaction import RequestInteractionTool
from quenda.tools.resource_activation import ActivateResourceTool
from quenda.tools.skill_activation import RequestSkillActivationTool
from quenda.runtime.permission import PermissionPolicy

__all__ = [
    # Decorator
    "tool",
    "FunctionTool",
    # Core filesystem tools
    "ListFilesTool",
    "SearchTextTool",
    "ReadFileTool",
    "WriteFileTool",
    "ApplyPatchTool",
    "get_filesystem_tools",
    # Execution tools
    "RunShellTool",
    "ShellConfig",
    "PythonExecutionTool",
    "SandboxConfig",
    "get_execution_tools",
    # Network tools
    "HTTPRequestTool",
    "WebFetchTool",
    "get_network_tools",
    # Interaction tool
    "RequestInteractionTool",
    "RequestSkillActivationTool",
    "ActivateResourceTool",
    # Tool aggregation
    "get_core_tools",
    "get_extended_tools",
]


def get_core_tools(
    workspace_root: str,
    permission_policy: PermissionPolicy | None = None,
) -> list:
    """
    Get the 10 core tools for Quenda Coding Agent.

    The minimal tool set following capability semantics:
    - list_files: See what exists
    - search_text: Find where things are
    - read_file: See specific content
    - write_file: Create new files
    - apply_patch: Modify existing files
    - execute_python: Run Python code safely
    - run_shell: Execute shell commands
    - request_interaction: Ask human for a decision
    - request_skill_activation: Ask Host to activate a discovered skill
    - activate_resource: Ask Runtime to attach a historical session resource

    Args:
        workspace_root: The workspace directory for file operations.

    Returns:
        List of 10 core Tool instances.
    """
    from pathlib import Path

    workspace = Path(workspace_root)
    return [
        ListFilesTool(workspace),
        SearchTextTool(workspace),
        ReadFileTool(workspace, permission_policy=permission_policy),
        WriteFileTool(workspace),
        ApplyPatchTool(workspace),
        PythonExecutionTool(workspace),
        RunShellTool(workspace),
        RequestInteractionTool(),
        RequestSkillActivationTool(),
        ActivateResourceTool(),
    ]


def get_extended_tools(
    workspace_root: str,
    permission_policy: PermissionPolicy | None = None,
) -> list:
    """
    Get framework-level tools for an agent that needs network access.

    Tool categories:
    - Core tools (10): Basic file, execution, and interaction
    - Network tools (2): HTTP request and web fetch

    Total: 12 tools

    Args:
        workspace_root: The workspace directory for file operations.
        permission_policy: Optional permission policy.

    Returns:
        List of core tools plus network tools.
    """
    tools = get_core_tools(workspace_root, permission_policy)
    tools.extend([HTTPRequestTool(), WebFetchTool()])

    return tools
