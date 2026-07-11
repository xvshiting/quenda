# ADR-029: Unify Code and Command Execution

## Status

Proposed (2026-07-11)

## Context

Quenda currently has three separate execution paths:

1. **`execute_python`** — In-process `exec()` with AST validation, import restrictions, and daemon-thread timeout
2. **`run_shell`** — `subprocess.run(shell=True)` with command string and dangerous-pattern filtering
3. **Skill script execution** — Separate subprocess path with its own logic

These paths have overlapping concerns and significant limitations:

### `execute_python` Problems

- **Fake timeout**: Daemon threads cannot be truly killed; timeout only prevents blocking program exit
- **Incomplete Python**: Blocks `sys`, `os`, `subprocess`, `threading` — making Playwright, requests, and many real libraries unusable
- **No Skill code reuse**: In-process execution has no Skill import namespace
- **Maintenance burden**: AST whitelist and `allowed_modules` require continuous updates
- **False security**: AST validation + module whitelist provide weaker isolation than process boundaries

### `run_shell` Problems

- Uses `shell=True` with string command (Shell-specific interface)
- Cannot accept structured `argv` list
- No stdin support
- Re-implements timeout, output capture, truncation separately

### Skill Script Problems

- `execute_skill_asset` is yet another execution path
- Skill Python code cannot be imported and composed
- No unified import namespace for active Skills

## Decision

### 1. Introduce `CommandRunner` as the sole local process primitive

```python
@dataclass(frozen=True)
class ExecutionLimits:
    default_timeout: int = 30
    max_timeout: int = 300
    max_output_chars: int = 100_000
    max_stdin_bytes: int = 1_000_000

@dataclass(frozen=True)
class CommandRequest:
    argv: list[str]
    cwd: Path
    stdin: str | None = None
    env: dict[str, str] | None = None
    timeout: int = 30

@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

class CommandRunner:
    """Unified command execution service for Tools and Host."""

    def run(self, request: CommandRequest) -> CommandResult: ...
```

`CommandRunner` is responsible only for:

- Starting subprocess with `shell=False`
- stdin/stdout/stderr handling
- Timeout with process-group termination
- Output truncation
- Exit code reporting

It is **NOT** responsible for:

- PermissionPolicy
- Workspace authorization
- Dangerous command filtering
- Skill discovery
- `PYTHONPATH` assembly
- User confirmation

These belong in Tool wrappers or Host policy layers.

### 2. `execute_python` becomes a thin wrapper

```python
class ExecutePythonTool(Tool):
    def execute(self, code: str, timeout: int = 30) -> ToolResult:
        return command_runner.run(
            CommandRequest(
                argv=[sys.executable, "-"],
                stdin=code,
                cwd=workspace,
                env=build_python_env(active_skills),
                timeout=timeout,
            )
        )
```

Delete:

- `SandboxConfig.allowed_modules`, `blocked_modules`, `allowed_builtins`
- `RestrictedImporter`
- `ASTValidator`
- In-process `exec()`
- Daemon-thread timeout

### 3. `run_command` becomes the general command tool

```json
{
  "argv": ["pytest", "-q"],
  "cwd": ".",
  "timeout": 60
}
```

For shell syntax, explicitly invoke shell:

```json
{
  "argv": ["bash", "-lc", "find . -name '*.py' | xargs grep -n TODO"]
}
```

### 4. `run_shell` becomes compatibility wrapper

```python
run_shell(command, cwd, timeout)
    ↓
run_command(
    argv=["bash", "-lc", command],
    cwd=cwd,
    timeout=timeout,
)
```

Mark as deprecated; do not expose to model in future versions.

### 5. Skill Python code reuse via `PYTHONPATH`

Active Skill `scripts/` directories are added to `PYTHONPATH`:

```python
def build_python_env(active_skills: Sequence[SkillDescriptor]) -> dict[str, str]:
    env = os.environ.copy()

    skill_script_paths = [
        str(skill.root / "scripts")
        for skill in active_skills
        if (skill.root / "scripts").is_dir()
    ]

    existing = env.get("PYTHONPATH")
    if existing:
        skill_script_paths.append(existing)

    if skill_script_paths:
        env["PYTHONPATH"] = os.pathsep.join(skill_script_paths)

    return env
```

Model can then write:

```python
from quenda_playwright.capture import capture_screenshot

capture_screenshot(url="https://example.com/", output="page.png")
```

No virtual `quenda_skills.*` namespace, no symlinks, no Skill name translation.

Skill authors should place reusable Python modules under `scripts/<unique-package-name>/`.

## Security Statement

**`CommandRunner` provides process isolation and lifecycle control, not filesystem or network sandboxing.**

- `cwd` controls where the process starts, not what it can access
- A Python subprocess can still read `~/.ssh`, access network, or spawn child processes
- Strong isolation belongs to a future `SandboxBackend` (Docker, macOS Sandbox, remote execution)
- PermissionPolicy governs what commands require user approval

This is an honest admission: local process execution is **not** a strong sandbox.

## Architecture

### File Structure

```text
src/quenda/tools/execution/
├── command.py       # CommandRunner (internal primitive)
├── command_tool.py  # run_command (model-visible Tool)
├── code.py          # execute_python (thin wrapper)
└── shell.py         # run_shell (compatibility wrapper)
```

### Dependency Graph

```text
RunCommandTool ───────┐
                      │
ExecutePythonTool ────┼──> CommandRunner ──> subprocess
                      │
RunShellTool ─────────┘
```

### Layer Responsibilities

| Component | Owns | Does NOT Own |
|-----------|------|--------------|
| `CommandRunner` | Process start, stdin/stdout, timeout, kill process group | Workspace, permissions, Skill discovery |
| `RunCommandTool` | argv validation, workspace-relative cwd, permission request | Process execution |
| `ExecutePythonTool` | Python env setup, Skill PYTHONPATH, code size limit | Process execution |
| `RunShellTool` | Shell compatibility, dangerous pattern check | Process execution |

### Tool Interfaces

#### `run_command` (Phase 2)

```python
run_command(
    argv: list[str],
    stdin: str | None = None,
    cwd: str = ".",
    timeout: int = 30,
)
```

First version does **NOT** expose `env` to model.

#### `execute_python` (Phase 3)

```python
execute_python(
    code: str,
    timeout: int = 30,
)
```

Active Skills' `scripts/` are automatically added to `PYTHONPATH`.

## Implementation Phases

### Phase 1: CommandRunner (Internal Primitive)

- Create `tools/execution/command.py`
- `ExecutionLimits`, `CommandRequest`, `CommandResult`, `CommandRunner`
- Process-group termination (POSIX + Windows)
- Timeout handling
- Output truncation
- Unit tests

**No model-visible behavior change in this phase.**

### Phase 2: run_command Tool + run_shell Migration

- Create `tools/execution/command_tool.py` with `RunCommandTool`
- Migrate `run_shell` to use `CommandRunner`
- Mark `run_shell` as deprecated
- Integration tests

### Phase 3: execute_python Refactor + Skill Import

- Delete AST/import sandbox code from `code.py`
- Implement `build_python_env()` for Skill PYTHONPATH
- Update `ExecutePythonTool` to use `CommandRunner`
- Update documentation

### Phase 4: Cleanup

- Remove or deprecate `execute_skill_asset`
- Update README to remove "sandboxed" claims
- Add migration guide for users who relied on import restrictions

## Consequences

### Positive

- **Real Python behavior**: `sys`, `os`, Playwright, requests work normally
- **Killable processes**: Timeout truly terminates process tree
- **Skill code reuse**: Can import and compose Skill Python modules
- **Single execution path**: No duplicate timeout, output capture logic
- **Honest security**: No false sense of sandbox protection
- **Unix philosophy**: Do one thing well (process execution)

### Negative

- **Broader process capabilities**: Python code can access filesystem and network
- **Permission needed**: Sensitive operations require explicit permission policy
- **Migration effort**: Users who relied on import whitelist may need updates
- **Documentation update**: README and guides need correction

### Risks

- Users may assume local execution is secure sandbox
- Skill `scripts/` package naming collisions if not unique
- Windows process-group termination complexity

## Alternatives Considered

### A. Keep AST/import sandbox and add subprocess option

Pros: Backward compatible

Cons: Two execution modes, confusing for users, sandbox still incomplete

Conclusion: Rejected — one clear execution model is better

### B. Use virtual `quenda_skills.*` namespace with symlinks

Pros: Explicit Skill import paths

Cons: Windows symlink issues, name translation complexity, module cache problems

Conclusion: Rejected — standard `PYTHONPATH` is simpler and more portable

### C. Add `lib/` as Skill special directory

Pros: Clear separation of importable code

Cons: Not in Agent Skills standard, language-specific, framework must understand it

Conclusion: Rejected — `scripts/` with unique package names is sufficient

## Decision Summary

Quenda should unify all local process execution through a single `CommandRunner` primitive:

- `CommandRunner` owns process lifecycle, not security policy
- `execute_python` becomes real subprocess, not restricted interpreter
- `run_command` replaces `run_shell` as the general tool
- Skill Python reuse via standard `PYTHONPATH`
- Security is honest: process isolation, not sandbox

The most important principle:

> `CommandRunner` provides process isolation and lifecycle control, not filesystem or network sandboxing.
