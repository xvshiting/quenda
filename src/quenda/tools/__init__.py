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
│   ├── fetching.py  → web_fetch
│   └── searching.py → web_search
├── task/           # Task management (coding)
│   └── __init__.py  → task_create, task_get, task_list, task_update
├── lsp/            # LSP code intelligence (coding)
│   └── __init__.py  → lsp
├── plan_mode/      # Plan mode (coding)
│   └── __init__.py  → enter_plan_mode, exit_plan_mode
├── scheduling/     # Scheduled tasks
│   └── __init__.py  → schedule_wakeup, cron_create, cron_delete, cron_list
└── security/       # Security patterns
```

## Tool Bundles

### Core Tools (10)
Basic file, execution, and interaction tools:
- list_files, search_text, read_file, write_file, apply_patch
- execute_python, run_shell
- request_interaction, request_skill_activation, activate_resource

Use `get_core_tools()` for the minimal essential toolset.

### Coding Tools (7)
Tools specifically for software development:
- Task management: task_create, task_get, task_list, task_update
- Code intelligence: lsp
- Planning: enter_plan_mode, exit_plan_mode

Use `get_coding_tools()` for programming-focused workflows.

### Extended Tools (29)
All available tools combined:
- Core (10) + Coding (7) + Agent (4) + Skill (4) + Scheduling (4)

Use `get_extended_tools()` for full-featured agents.

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
    WebSearchTool,
    get_network_tools,
)

# Task management tools
from quenda.tools.task import (
    Task,
    TaskStatus,
    TaskManager,
    get_task_manager,
    set_task_manager,
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskUpdateTool,
    get_task_tools,
)

# LSP code intelligence tools
from quenda.tools.lsp import (
    LSPOperation,
    LSPResult,
    LSPTool,
    LSPConfig,
    get_lsp_tools,
)

# Plan mode tools
from quenda.tools.plan_mode import (
    PlanModeState,
    Plan,
    EnterPlanModeTool,
    ExitPlanModeTool,
    PlanStorage,
    get_plan_tools,
)

# Scheduling tools
from quenda.tools.scheduling import (
    TaskType,
    ScheduledTask,
    ScheduleWakeupTool,
    CronCreateTool,
    CronDeleteTool,
    CronListTool,
    ScheduledTaskStorage,
    get_cron_tools,
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
    "WebSearchTool",
    "get_network_tools",
    # Task management tools
    "Task",
    "TaskStatus",
    "TaskManager",
    "get_task_manager",
    "set_task_manager",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskListTool",
    "TaskUpdateTool",
    "get_task_tools",
    # LSP code intelligence tools
    "LSPOperation",
    "LSPResult",
    "LSPTool",
    "LSPConfig",
    "get_lsp_tools",
    # Plan mode tools
    "PlanModeState",
    "Plan",
    "EnterPlanModeTool",
    "ExitPlanModeTool",
    "PlanStorage",
    "get_plan_tools",
    # Scheduling tools
    "TaskType",
    "ScheduledTask",
    "ScheduleWakeupTool",
    "CronCreateTool",
    "CronDeleteTool",
    "CronListTool",
    "ScheduledTaskStorage",
    "get_cron_tools",
    # Interaction tool
    "RequestInteractionTool",
    "RequestSkillActivationTool",
    "ActivateResourceTool",
    # Tool aggregation
    "get_core_tools",
    "get_coding_tools",
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


def get_coding_tools(
    workspace_root: str,
    session_dir: str | None = None,
) -> list:
    """
    Get coding-related tools for software development.

    Includes tools specifically useful for programming tasks:
    - Task management tools (4): task_create, task_get, task_list, task_update
    - LSP code intelligence (1): lsp
    - Plan mode tools (2): enter_plan_mode, exit_plan_mode

    Total: 7 coding tools

    These tools help with:
    - Tracking progress on complex coding tasks
    - Code navigation and understanding
    - Planning implementation approaches

    Args:
        workspace_root: The workspace directory for file operations.
        session_dir: Optional directory for session-level storage.

    Returns:
        List of 7 coding Tool instances.
    """
    from pathlib import Path

    # Initialize task manager with session directory if provided
    if session_dir:
        from quenda.tools.task import set_task_manager, TaskManager
        task_manager = TaskManager(Path(session_dir))
        set_task_manager(task_manager)

    tools = []
    tools.extend(get_task_tools())
    tools.extend(get_lsp_tools())
    tools.extend(get_plan_tools())

    return tools


def get_extended_tools(
    workspace_root: str,
    session_dir: str | None = None,
    permission_policy: PermissionPolicy | None = None,
) -> list:
    """
    Get all available tools for full-featured Quenda agent.

    Tool categories:
    - Core tools (10): Basic file, execution, and interaction
    - Coding tools (7): Task management, LSP, plan mode
    - Agent tools (4): Sub-agent spawning and team coordination
    - Skill tools (4): Skill invocation and management
    - Scheduling tools (4): Cron and wake-up scheduling

    Total: 29 tools

    Args:
        workspace_root: The workspace directory for file operations.
        session_dir: Optional directory for session-level storage.
        permission_policy: Optional permission policy.

    Returns:
        List of all 29 Tool instances.
    """
    from pathlib import Path

    tools = get_core_tools(workspace_root, permission_policy)
    tools.extend(get_coding_tools(workspace_root, session_dir))
    tools.extend(get_cron_tools())

    return tools
