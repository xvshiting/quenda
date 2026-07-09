# Tools Guide

Quenda provides a focused set of built-in tools organized around
**capabilities**, not individual Unix commands. Each tool covers a
family of operations (e.g. `read_file` covers `cat`, `head`, `tail`,
`sed -n`).

## Tool Definition

### Using the @tool Decorator

The simplest way to create a tool:

```python
from quenda import tool

@tool
def my_tool(param: str, optional: int = 10) -> str:
    """Tool description shown to the model."""
    return f"Result: {param}"
```

The decorator automatically:
- Uses the function name as the tool name
- Extracts the description from the first line of the docstring
- Generates JSON Schema from type hints
- Wraps the function in a `FunctionTool` implementing the `Tool` protocol
- Catches exceptions and returns an error `ToolResult`

A custom name can be supplied with `@tool(name="custom_name")`.

### Implementing the Tool Protocol

For stateful tools:

```python
from pathlib import Path
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult

class MyComplexTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "my_complex_tool"

    @property
    def description(self) -> str:
        return "A complex tool with custom logic"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input value"},
            },
            "required": ["input"],
        }

    def execute(self, **kwargs) -> ToolResult:
        try:
            result = self._process(kwargs["input"])
            return ToolResult(call_id="", name=self.name, content=result)
        except Exception as e:
            return ToolResult(
                call_id="", name=self.name,
                content=f"Error: {e}", is_error=True,
            )
```

---

## Core Tools Bundle

The 10 essential framework tools, available via
`get_core_tools(workspace)`:

| Tool | Capability | Covers |
|------|-----------|--------|
| `list_files` | See what exists | `ls`, `find`, `tree` |
| `search_text` | Find where things are | `grep`, `rg` |
| `read_file` | See specific content | `cat`, `head`, `tail`, `sed -n` |
| `write_file` | Create new files | `>` |
| `apply_patch` | Modify existing files | `sed`, `patch` |
| `run_shell` | Execute and verify | `pytest`, `git`, `npm`, … |
| `execute_python` | Run sandboxed Python | quick scripts, data transforms |
| `request_interaction` | Ask a human for a decision | choices, confirmations, input |
| `request_skill_activation` | Ask Host to activate skills | skill package activation |
| `activate_resource` | Attach session resources | historical multimodal resources |

```python
from quenda.tools import get_core_tools
from pathlib import Path

tools = get_core_tools(Path("."))
```

---

## File System Tools

All filesystem tools are workspace-scoped: paths are validated and
rejected if they escape the workspace root.

```python
from pathlib import Path
from quenda.tools import (
    ListFilesTool,
    SearchTextTool,
    ReadFileTool,
    WriteFileTool,
    ApplyPatchTool,
    get_filesystem_tools,
)

workspace = Path(".")

# Individual tools
list_tool = ListFilesTool(workspace)
search_tool = SearchTextTool(workspace)
read_tool = ReadFileTool(workspace)
write_tool = WriteFileTool(workspace)
patch_tool = ApplyPatchTool(workspace)

# Or get all 5 at once
tools = get_filesystem_tools(workspace)
```

### ListFilesTool

List files and directories. Covers `ls`, `find`, `tree`.

```python
list_tool.execute()                              # List workspace root (flat)
list_tool.execute(path="src/quenda")               # List specific directory
list_tool.execute(path=".", depth=3)             # Tree view with depth limit
list_tool.execute(pattern="*.py")                # Filter by glob pattern
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `"."` | Directory to list |
| `depth` | `int` | `1` | Max depth. `1` = flat list, `2+` = tree view |
| `pattern` | `str` | — | Glob filter (e.g. `*.py`, `**/*.md`) |

### SearchTextTool

Search for text patterns in files. Covers `grep`, `rg`. Uses ripgrep
when available, falling back to a native Python implementation.

```python
search_tool.execute(pattern="AgentConfig")
search_tool.execute(pattern="def run", path="src")
search_tool.execute(pattern="TODO", include="*.py")
search_tool.execute(pattern="error", ignore_case=True)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | `str` | — | Search pattern (regex) |
| `path` | `str` | `"."` | File or directory to search |
| `include` | `str` | — | Glob filter (e.g. `*.py`) |
| `ignore_case` | `bool` | `False` | Case-insensitive search |
| `context_lines` | `int` | `2` | Lines of context around each match |

### ReadFileTool

Read file content with range selection. Covers `cat`, `head`, `tail`,
`sed -n`. Output is formatted with line numbers.

```python
read_tool.execute(path="app.py")                       # Read entire file
read_tool.execute(path="app.py", start=1, end=100)     # Read lines 1-100
read_tool.execute(path="app.log", start=-50)           # Read last 50 lines
read_tool.execute(path="config.json", end=30)          # Read first 30 lines
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | File path to read |
| `start` | `int` | `1` | Start line (1-indexed). Negative = last N lines |
| `end` | `int` | — | End line (inclusive). Omit to read to EOF |

### WriteFileTool

Create a new file or completely overwrite an existing one. Creates
parent directories automatically.

```python
write_tool.execute(path="output.txt", content="Hello, World!")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | File path to write |
| `content` | `str` | — | Content to write |

### ApplyPatchTool

Apply a targeted text patch to an existing file. Safer than
`write_file` for partial changes: it verifies the `old_text` matches
exactly and uniquely before replacing it.

```python
patch_tool.execute(
    path="app.py",
    old_text="def old():",
    new_text="def new():",
)

# Preview without writing
patch_tool.execute(
    path="app.py",
    old_text="x = 1",
    new_text="x = 2",
    dry_run=True,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | File path to modify |
| `old_text` | `str` | — | Text to find (must match exactly and uniquely) |
| `new_text` | `str` | — | Replacement text |
| `dry_run` | `bool` | `False` | Preview changes without writing |

Errors are returned if `old_text` is not found or appears more than
once.

---

## Execution Tools

### RunShellTool

Execute shell commands. This is the controlled escape hatch for
operations not covered by specialized tools (tests, git, package
managers, build commands). Dangerous commands are blocked.

```python
from quenda.tools import RunShellTool, ShellConfig
from pathlib import Path

shell_tool = RunShellTool(Path("."))

# With custom config
config = ShellConfig(
    default_timeout=30,
    max_timeout=300,
    max_output_chars=100_000,
)
shell_tool = RunShellTool(Path("."), config)
```

```python
shell_tool.execute(command="pytest tests/ -q")
shell_tool.execute(command="git status")
shell_tool.execute(command="python script.py", cwd="scripts")
shell_tool.execute(command="long_running.sh", timeout=60)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | — | Shell command to execute |
| `cwd` | `str` | `"."` | Working directory (relative to workspace) |
| `timeout` | `int` | `config.default_timeout` | Timeout in seconds |

**Blocked command patterns** include: `rm -rf /`, `mkfs`,
`dd if=... of=/dev/`, fork bombs, `shutdown`, `reboot`,
`iptables -F`, and `chmod 777 /`.

### PythonExecutionTool

Execute Python code in a sandboxed environment with AST validation,
import restrictions, and restricted builtins.

```python
from quenda.tools import PythonExecutionTool, SandboxConfig

python_tool = PythonExecutionTool()  # workspace optional

config = SandboxConfig(
    default_timeout=30,
    max_timeout=60,
    max_ast_nodes=5000,
)
python_tool = PythonExecutionTool(config=config)
```

```python
python_tool.execute(code='print("Hello, World!")')

python_tool.execute(code='''
import math
print(f"Square root of 16 is {math.sqrt(16)}")
''')

python_tool.execute(code='import time; time.sleep(5)', timeout=3)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `code` | `str` | — | Python code to execute |
| `timeout` | `int` | `config.default_timeout` | Timeout in seconds |

**Allowed modules:** `math`, `random`, `statistics`, `datetime`,
`time`, `json`, `csv`, `re`, `collections`, `itertools`, `functools`,
`typing`, `dataclasses`, `enum`, `hashlib`, `base64`, `hmac`, …

**Blocked modules:** `os`, `sys`, `subprocess`, `socket`,
`threading`, `multiprocessing`, `asyncio`, `importlib`, `ctypes`,
`pickle`, `shelve`, …

**Restricted builtins:** `open`, `exec`, `eval`, and `__import__`
(replaced with a restricted importer) are blocked.

---

## Network Tools

Requires: `pip install quenda[network]` (installs `httpx`).

```python
from quenda.tools import (
    HTTPRequestTool,
    HTTPConfig,
    WebFetchTool,
    WebFetchConfig,
    get_network_tools,
)

# Individual tools
http_tool = HTTPRequestTool()
fetch_tool = WebFetchTool()

# Or get both at once
tools = get_network_tools()

# With custom config
http_tool = HTTPRequestTool(HTTPConfig(user_agent="MyAgent/1.0"))
```

### HTTPRequestTool

Make HTTP requests with SSRF protection. Supports GET, POST, PUT,
DELETE, PATCH.

```python
http_tool.execute(url="https://api.example.com/data")

http_tool.execute(
    url="https://api.example.com/create",
    method="POST",
    body='{"name": "test"}',
    headers={"Content-Type": "application/json"},
)

http_tool.execute(url="https://slow.example.com", timeout=60)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | URL (must be `http`/`https`) |
| `method` | `str` | `"GET"` | One of GET, POST, PUT, DELETE, PATCH |
| `headers` | `dict[str, str]` | — | Request headers |
| `body` | `str` | — | Request body (POST/PUT/PATCH) |
| `timeout` | `int` | `config.default_timeout` | Timeout in seconds |

### WebFetchTool

Fetch and extract readable text from a web page.

```python
fetch_tool.execute(url="https://example.com/article")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | URL to fetch |
| `timeout` | `int` | `config.default_timeout` | Timeout in seconds |

### SSRF Protection

`HTTPRequestTool` and `WebFetchTool` validate URLs before requesting:

- Schemes restricted to `http`/`https`
- Blocked domains: `localhost`, `*.local`, `*.internal`,
  `metadata.google.internal`, `kubernetes`, …
- Blocked IP ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`,
  `127.0.0.0/8`, `169.254.0.0/16` (AWS metadata), `0.0.0.0/8`, IPv6
  private/link-local
- Redirects are re-validated
- Sensitive headers (`Authorization`, `Cookie`, `Set-Cookie`) are
  blocked from outgoing requests

---

## Combining Tools

```python
from pathlib import Path
from quenda.tools import (
    get_core_tools,
    get_network_tools,
)

workspace = Path(".")

all_tools = []
all_tools.extend(get_core_tools(workspace))   # 10 framework tools
all_tools.extend(get_network_tools())         # 2 network tools

from quenda import Agent
agent = Agent(
    name="full-assistant",
    tools=all_tools,
    model=your_model,
)
```

Individual bundles: `get_filesystem_tools(workspace)` (5 tools),
`get_execution_tools(workspace)` (2 tools), `get_network_tools()`
(2 tools), `get_core_tools(workspace)` (10 tools).
