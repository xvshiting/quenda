# API Reference

Core API for the Quenda framework.

## Public API

```python
from quenda import Agent, Session, build_framework_capability_manifest, tool
```

Provider exports:

```python
from quenda.providers import (
    Model,
    ModelSpec,
    Provider,
    ProviderSpec,
    get_provider_registry,
)
```

---

## Framework capability manifest

Quenda exposes one versioned, credential-free source of truth for framework
authoring tools, documentation, and Agents:

```python
manifest = build_framework_capability_manifest()
```

The same manifest is available from Unix-friendly and Web interfaces:

```sh
quenda capabilities --json
quenda capabilities --json --section configuration
```

```text
GET /api/system/capabilities
```

The manifest reports supported configuration shapes, Skill discovery behavior,
registered provider protocols/catalogs, and public extension contracts. It
never includes API keys, resolved credentials, request headers, or environment
values.

The lifecycle catalog is generated from the same code-owned registry:

```sh
quenda capabilities --json --section lifecycle
```

Each descriptor identifies its ordered stage, contract, registration surface,
owner, failure mode, permitted mutation, transition authority, cache impact,
and whether the seam is active or reserved.

Prompt assembly exposes content-free cache telemetry through
`PromptAssembly.observe(previous)`. `HostService` emits the same information as
`prompt_cache_observed`, including stable/reused prefix digests, segment counts,
and estimated tokens. These estimates are diagnostic; provider-reported cached
input remains authoritative for billing. Provider usage is normalized to one
framework invariant: `input_tokens` is the total logical input for the request,
`cached_input_tokens` is the subset served from an existing cache, and
`cache_creation_input_tokens` records newly written cache input when the provider
reports it. This keeps session totals comparable even when provider wire formats
use overlapping versus disjoint counters.

All prompt-building callers collect sources through `resolve_prompt_sources()`
and render them through `PromptAssembler`. Context providers contribute typed
`InstructionSource` values at that seam; scope ordering and path de-duplication
remain Host policy rather than extension responsibilities.

### Revisioned memory evolution

`quenda.evolution` provides a policy-controlled local store for `MEMORY.md`,
`USER.md`, `IDENTITY.md`, and `SOUL.md`:

```python
from quenda.evolution import (
    MemoryEvolutionPolicy,
    MemoryEvolutionStore,
    MemoryProposal,
    MemoryTarget,
    MemoryWriteMode,
)

store = MemoryEvolutionStore(
    agent_home,
    policy=MemoryEvolutionPolicy(write_mode=MemoryWriteMode.AUTOMATIC),
)
proposal = MemoryProposal(
    target=MemoryTarget.CORE_MEMORY,
    proposed_content=updated_markdown,
    reason="The user explicitly corrected this preference",
    expected_revision=store.current_revision(MemoryTarget.CORE_MEMORY),
    source_run_id=run_id,
)
report = store.validate(proposal)
if report.valid:
    revision = store.apply(proposal, actor="default-evolution-policy")
```

The write uses optimistic concurrency and an atomic file replacement. Immutable,
content-addressed Markdown revisions and an append-only JSONL journal live under
`<agent-home>/.quenda/evolution/memory/`. Rollback restores an existing snapshot
as a new journal entry, so history is never rewritten. Possible credentials are
rejected by the default validator. `MemoryEvolutionPolicy` selects `automatic`,
`review`, or `disabled`; the official default is `automatic`. A proposal still
has no mutation authority by itself—the configured policy grants that authority
when `apply()` is invoked and the journal records whether the commit was automatic
or explicitly approved.

`IDENTITY.md` and `SOUL.md` are independent and both are loaded. Identity defines
role, responsibilities, and operating scope; Soul defines personality, values,
and temperament.

Agent packages enable the official after-Run implementation declaratively:

```yaml
evolution:
  enabled: true
  write_mode: automatic       # automatic | review | disabled
  every_n_user_turns: 5
  on_explicit_signal: true
  min_confidence: 0.8
  max_proposals: 2
```

The normal Run completes first. The trigger then uses a separate model request,
containing only current evolution documents and the recent conversation tail.
This keeps the main Agent prompt prefix unchanged. Explicit preference,
remember/forget, and correction signals can trigger evaluation before the
periodic interval. `review` stores validated JSON proposals under
`.quenda/evolution/memory/pending/`; `automatic` commits them; `disabled` avoids
the evaluation call entirely. Failures emit `evolution_failed` but cannot turn a
successful Run into a failed Run.

---

## Agent package validation

Validate an Agent package without starting a Session, importing extensions,
resolving credentials, or contacting a model provider:

```python
from quenda.host import validate_agent_package

report = validate_agent_package("path/to/agent", workspace_path="path/to/project")
if not report.valid:
    for diagnostic in report.diagnostics:
        print(diagnostic.code, diagnostic.message)
```

The CLI exposes the same interface with meaningful exit status and pipeable
JSON:

```sh
quenda agent validate path/to/agent --json
```

Inside a running Agent, the always-bound read-only
`validate_agent_package` framework Tool validates the current Agent when `path`
is omitted. Explicit targets are restricted to the current workspace or Agent
package.

Validation checks declarative providers and model roles, configured
instructions and Skills, tool bundles, and Python extension syntax. References
implemented by Agent-local extensions are reported as deferred warnings because
static validation deliberately does not execute extension code.

The always-bound `apply_agent_config_patch` framework Tool is the guarded
mutation counterpart. It accepts an RFC 7396 JSON Merge Patch and defaults to a
side-effect-free preview. Commit requires the preview's `base_revision` and a
separate `agent_config.write` approval. The implementation redacts secrets from
diffs, validates the complete candidate package, writes atomically, and stores
the prior content under `.quenda/config-revisions/` with an audit entry in
`.quenda/config-journal.jsonl`.

Before proposing a patch, `explain_agent_config` returns a credential-free,
normalized view of the current effective configuration. Callers can select
`summary`, `models`, `providers`, `tools`, `skills`, `execution`, `evolution`,
or `all`. Its `quenda.agent-config-inspection/v1` result includes the current
revision, validation report, and the matching live capability-registry facts;
provider credentials, header values, URL userinfo, and URL queries are omitted.

Skill changes use two separate always-bound framework Tools.
`inspect_skill_evolution` lists active revision, proposal metadata, validation
findings, and history without returning candidate file contents.
`apply_skill_evolution` stages package-relative replacements in quarantine;
commit and rollback require a non-cacheable `skill_evolution.write` approval
and an expected active revision. Candidate Python is compiled but never
imported or executed. A successful commit changes the installed package while
existing Host bindings retain their content-addressed Skill snapshot until an
explicit `advance_skill_activation_epoch()` call, Skill activation request, or
new capability binding.

---

## Agent

The main entry point for creating an AI agent.

### Constructor

```python
Agent(
    name: str,
    *,
    system_prompt: str | None = None,
    tools: list[Tool] | None = None,
    model: Model | None = None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Agent name for identification |
| `system_prompt` | `str \| None` | `None` | System prompt for the model |
| `tools` | `list[Tool] \| None` | `None` | Tools available to the agent |
| `model` | `Model \| None` | `None` | Model provider; may be set later via `set_model()` or per-call |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | The agent name |
| `config` | `AgentConfig` | The underlying immutable agent configuration |
| `model` | `Model \| None` | The default model provider |

### Methods

#### `open_session(*, session_id: str | None = None) -> Session`

Open a persistent session for multi-turn conversation.

```python
session = agent.open_session()
session = agent.open_session(session_id="my-session")
```

#### `async run(message, *, model=None, on_event=None) -> str`

One-shot execution. Creates a temporary session, sends the message, and
returns the agent's response text.

```python
result = await agent.run("Hello!")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `message` | `str` | User message |
| `model` | `Model \| None` | Optional model override |
| `on_event` | `Callable[[AnyEvent], None] \| None` | Optional event handler |

#### `run_sync(message, *, model=None, on_event=None) -> str`

Synchronous wrapper around `run()` using `asyncio.run`.

#### `set_model(model: Model) -> None`

Set the default model for this agent.

---

## AgentConfig / AgentDefinition

`AgentConfig` is the default immutable implementation of the
`AgentDefinition` protocol.

```python
from quenda.runtime import AgentConfig, AgentDefinition

config = AgentConfig(
    name="assistant",
    system_prompt="You are helpful.",
    tools=[...],
)
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Agent name |
| `system_prompt` | `str \| None` | System prompt |
| `tools` | `list[Tool]` | Tools (defaults to empty) |

---

## Session

Manages conversation history and execution. Created via
`Agent.open_session()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique session identifier |
| `state` | `SessionState` | The underlying persistable state |
| `messages` | `list[Message]` | Conversation history |

### Methods

#### `async send(message, *, model=None, on_event=None) -> str`

Send a message and get a response. Streams events via `on_event` and
returns the agent's final response text.

```python
result = await session.send("Hello!", on_event=handler)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `message` | `str` | User message |
| `model` | `Model \| None` | Optional model override |
| `on_event` | `Callable[[AnyEvent], None] \| None` | Optional event handler |

**Raises:** `ValueError` if no model is configured.

#### `send_sync(message, *, model=None, on_event=None) -> str`

Synchronous wrapper around `send()` using `asyncio.run`.

#### `set_model(model: Model) -> None`

Set the model for this session.

#### `clear() -> None`

Clear conversation history.

#### `__len__() -> int`

Number of messages in history.

---

## SessionState

The pure-data, persistable representation of a session.

```python
from quenda.runtime import SessionState

state = SessionState.create("assistant", session_id="optional-id")
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Session ID (auto-generated UUID if omitted) |
| `agent_name` | `str` | Name of the owning agent |
| `messages` | `list[Message]` | Conversation history |
| `metadata` | `dict[str, Any]` | Free-form metadata |
| `created_at` | `datetime` | Creation timestamp |

---

## Run / RunStatus

A `Run` represents a single execution of an agent within a session. It
bridges the async Runtime with the sync Kernel and emits events.

```python
from quenda.runtime import Run, RunStatus
```

`RunStatus` is an enum with values: `PENDING`, `RUNNING`, `COMPLETED`,
`FAILED`.

Runs are normally created internally by `Session.send()`. For
low-level control see `quenda.runtime.run.Run`.

---

## @tool Decorator

Create a tool from a function.

```python
from quenda import tool

@tool
def my_function(param: str, optional: int = 10) -> str:
    """Tool description."""
    return "result"

@tool(name="custom_name")
def another(x: int, y: int = 10) -> str:
    """Add two numbers."""
    return str(x + y)
```

The decorator:
- Uses the function name as the tool name (or a custom `name`)
- Extracts the description from the first line of the docstring
- Generates JSON Schema from type hints
- Wraps the function in a `FunctionTool` implementing the `Tool` protocol
- Catches exceptions and returns an error `ToolResult`

### Supported Types

| Python Type | JSON Schema Type |
|-------------|------------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |
| `T \| None` | the type of `T` (optional) |

---

## Tool Protocol

For implementing custom tools with state.

```python
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult

class CustomTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "custom_tool"

    @property
    def description(self) -> str:
        return "Tool description shown to the model"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"},
            },
            "required": ["param"],
        }

    def execute(self, **kwargs) -> ToolResult:
        try:
            result = self._process(kwargs["param"])
            return ToolResult(call_id="", name=self.name, content=result)
        except Exception as e:
            return ToolResult(
                call_id="", name=self.name,
                content=f"Error: {e}", is_error=True,
            )
```

### Required Members

| Member | Type | Description |
|--------|------|-------------|
| `name` | `str` (property) | Unique tool name |
| `description` | `str` (property) | Description shown to the model |
| `parameters` | `dict[str, object]` (property) | JSON Schema for parameters |
| `execute(**kwargs)` | `ToolResult` (method) | Execute the tool |

---

## Model Protocol

Interface for model providers.

```python
from quenda.kernel import Model, ModelResponse, Message, Tool

class MyModel(Model):
    def invoke(
        self,
        messages: list[Message],
        *,
        tools: list[Tool],
    ) -> ModelResponse:
        # Call the LLM API and convert to/from Quenda types
        ...
```

### Method

#### `invoke(messages, *, tools) -> ModelResponse`

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `list[Message]` | Conversation history |
| `tools` | `list[Tool]` | Available tools |

**Returns:** `ModelResponse`

The built-in provider path is registry-based:

```python
from quenda.providers import get_provider_registry

registry = get_provider_registry()
model = registry.get_model("dashscope", "qwen-max")
```

Built-in provider IDs include `openai`, `anthropic`, `dashscope`,
`jdcloud`, `deepseek`, `deepseek-anthropic`, `moonshot`, `openrouter`,
and `ollama`.

The `Model` returned by the registry also supports streaming:

```python
for chunk in model.invoke_stream(messages, tools=tools):
    # chunk.content: str | None
    # chunk.tool_calls: list[ToolCall] | None
    # chunk.is_final: bool
    ...
```

For custom providers, register a `ProviderSpec` with one or more
`ModelSpec` entries:

Agent packages can declare the same catalog without executable Python by using
the `providers:` mapping in `config.yaml`. Supported entry types are `builtin`,
`custom`, and `llama-server`; role selection remains under `models.default` and
`models.vision`. See the [Provider tutorial](tutorials/agent/04-providers.md).

```python
from quenda.providers import ModelSpec, ProviderSpec, get_provider_registry

registry = get_provider_registry()
registry.register(ProviderSpec(
    id="my-provider",
    name="My Provider",
    base_url="https://api.example.com/v1",
    api="openai-completions",       # or "anthropic-messages"
    api_key="${MY_API_KEY}",
    models=(
        ModelSpec(id="my-model", name="My Model", tool_calling=True),
    ),
))
model = registry.get_model("my-provider", "my-model")
```

`ModelSpec` fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | — | Model identifier |
| `name` | `str` | — | Human-readable name |
| `tool_calling` | `bool` | `True` | Supports tool calling |
| `streaming` | `bool` | `True` | Supports streaming |
| `vision` | `bool` | `False` | Supports image input |
| `reasoning` | `bool` | `False` | Reasoning model (e.g. R1) |
| `context_window` | `int \| None` | `None` | Context window size |
| `max_output_tokens` | `int \| None` | `None` | Max output tokens |
| `cost` | `ModelCost \| None` | `None` | Pricing per million tokens |
| `api` | `str \| None` | `None` | Override provider API protocol |
| `base_url` | `str \| None` | `None` | Override provider base URL |

---

## Core Types

### Message

```python
@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant", "system"]
    content: str | Sequence[ToolCall | ToolResult]
```

### ToolCall

```python
@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]
```

### ToolResult

```python
@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False
```

### ModelResponse

```python
@dataclass(frozen=True)
class ModelResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"] = "end_turn"
```

### StreamChunk

```python
@dataclass(frozen=True)
class StreamChunk:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    is_final: bool = False
```

Yielded by `Model.invoke_stream()`. Import from `quenda.kernel.types`.

---

## Kernel

The synchronous model-tool loop executor.

```python
from quenda.kernel import Kernel, KernelStep
```

```python
kernel = Kernel(model=model, tools=[...], max_iterations=100)
for step in kernel.run(messages):
    # step.type is "model" or "tool"
    # step.content is ModelResponse or ToolResult
    ...
```

| Method | Returns | Description |
|--------|---------|-------------|
| `run(messages)` | `Iterator[KernelStep]` | Generator yielding steps |
| `run_to_completion(messages)` | `list[KernelStep]` | Collects all steps |

---

## Events

All events inherit from a base `Event` with `id`, `timestamp`, and
`run_id` fields, and are emitted during `Run` execution.

```python
from quenda.runtime import (
    AnyEvent,
    ErrorOccurred,
    Event,
    ModelCalled,
    ModelResponded,
    RunCompleted,
    RunStarted,
    ToolExecuted,
)
```

### RunStarted

```python
@dataclass(frozen=True)
class RunStarted(Event):
    type: Literal["run_started"] = "run_started"
    agent_name: str = ""
    session_id: str = ""
    user_message: str = ""
```

### ModelCalled

```python
@dataclass(frozen=True)
class ModelCalled(Event):
    type: Literal["model_called"] = "model_called"
    message_count: int = 0
```

### ModelResponded

```python
@dataclass(frozen=True)
class ModelResponded(Event):
    type: Literal["model_responded"] = "model_responded"
    content: str | None = None
    tool_calls: list[str] = []  # field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    reasoning_tokens: int | None = None
```

### ToolExecuted

```python
@dataclass(frozen=True)
class ToolExecuted(Event):
    type: Literal["tool_executed"] = "tool_executed"
    tool_name: str = ""
    arguments: dict[str, Any] = {}  # field(default_factory=dict)
    result: str = ""
    is_error: bool = False
```

### RunCompleted

```python
@dataclass(frozen=True)
class RunCompleted(Event):
    type: Literal["run_completed"] = "run_completed"
    agent_name: str = ""
    session_id: str = ""
    total_steps: int = 0
    final_content: str | None = None
```

### ErrorOccurred

```python
@dataclass(frozen=True)
class ErrorOccurred(Event):
    type: Literal["error_occurred"] = "error_occurred"
    error_message: str = ""
    error_type: str = ""
```

`AnyEvent` is the union of all the above.

---

## Built-in Tools

### File System (`quenda.tools.filesystem`)

```python
from quenda.tools import (
    ListFilesTool,
    SearchTextTool,
    ReadFileTool,
    WriteFileTool,
    ApplyPatchTool,
    get_filesystem_tools,
)
```

### Execution (`quenda.tools.execution`)

```python
from quenda.tools import (
    RunShellTool,
    ShellConfig,
    PythonExecutionTool,
    SandboxConfig,
    get_execution_tools,
)
```

### Network (`quenda.tools.network`)

```python
from quenda.tools import (
    HTTPRequestTool,
    HTTPConfig,
    WebFetchTool,
    WebFetchConfig,
    get_network_tools,
)
```

### Core tools bundle

```python
from quenda.tools import get_core_tools

# The 11 essential framework tools:
# filesystem, execution, current time, interaction, skill activation, and resource activation
tools = get_core_tools(".")
```

See [Tools Guide](tools.md) for per-tool parameters and usage.

---

## Provider Errors

All provider-related exceptions inherit from `QuendaError` and are
exported from `quenda.providers`:

```python
from quenda.providers import (
    QuendaError,
    ProviderError,
    AuthenticationError,
    APIError,
    RateLimitError,
    NetworkError,
    ModelNotFoundError,
    UnsupportedFeatureError,
)
```

| Exception | Description |
|-----------|-------------|
| `QuendaError` | Base exception for all Quenda errors |
| `ProviderError` | Base exception for provider-related errors |
| `AuthenticationError` | API key invalid, missing, or denied |
| `APIError` | Base exception for API communication errors |
| `RateLimitError` | HTTP 429; has `retry_after` attribute (seconds) |
| `NetworkError` | Connection failure, timeout, DNS error |
| `ModelNotFoundError` | Model ID not found in provider catalog |
| `UnsupportedFeatureError` | Feature (e.g. vision) not supported by model |

---

## Skills API

The Skills framework provides composable capability packages.

```python
from quenda.host.skill import (
    SkillDiscovery,
    SkillActivator,
    ResourceResolver,
    SkillPackage,
    SkillFrontmatter,
)
```

### SkillDiscovery

Discover available skills from multiple sources.

```python
discovery = SkillDiscovery(
    user_workspace_skills_path=Path("~/.quenda/users/<user>/workspaces/<ws_id>/skills"),
    agent_package_path=Path("/path/to/agent"),
    workspace_path=Path("/path/to/workspace"),
)
skills = discovery.discover_skills()  # Returns list[SkillPackage]
```

### SkillActivator

Activate and deactivate skills.

```python
activator = SkillActivator(discovery)
activator.activate_skill("code-review")
activator.deactivate_skill("code-review")

# Get active skills for instruction composition
active_skills = activator.active_skills  # list[SkyllPackage]
```

### ResourceResolver

Load resources from active skills.

```python
resolver = ResourceResolver(active_skills)
guide = resolver.load_resource("code-review", "references/style-guide.md")
# Returns skill:// URI or file content
```

### SkillPackage

Data class representing a discovered skill.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Skill directory path |
| `frontmatter` | `SkillFrontmatter` | Metadata (name, description, version) |
| `source` | `str` | Source type (user_workspace, workspace, agent_package, user) |

### SkillFrontmatter

Metadata extracted from SKILL.md frontmatter.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier |
| `description` | `str` | Yes | Human-readable description |
| `version` | `str` | No | Semantic version (default: "0.1.0") |

---

## Policies API

Runtime policies control agent behavior at decision points.

```python
from quenda.runtime import (
    TerminationPolicy,
    ToolSelectionPolicy,
    ToolResultProcessingPolicy,
    TraceSink,
)
```

### TerminationPolicy

Control when to stop execution.

```python
from quenda.runtime.termination import (
    MaxStepsPolicy,
    TimeBudgetPolicy,
    TokenBudgetPolicy,
    ConsecutiveErrorsPolicy,
)

# Built-in policies
policy = MaxStepsPolicy(max_steps=30)
policy = TimeBudgetPolicy(max_time_ms=60000)
policy = TokenBudgetPolicy(max_total_tokens=100000)
policy = ConsecutiveErrorsPolicy(max_consecutive_errors=3)
```

### ToolSelectionPolicy

Control which tools are allowed to execute.

```python
from quenda.runtime.tool_policy import (
    AllowlistToolSelectionPolicy,
    DenylistToolSelectionPolicy,
)

# Allow only specific tools
policy = AllowlistToolSelectionPolicy({"read_file", "write_file"})

# Block specific tools
policy = DenylistToolSelectionPolicy({"run_shell"})
```

### ToolResultProcessingPolicy

Control how tool results enter the context.

```python
from quenda.runtime.tool_policy import (
    TruncatingToolResultProcessingPolicy,
    LineLimitToolResultProcessingPolicy,
)

# Truncate by characters
policy = TruncatingToolResultProcessingPolicy(max_chars=6000)

# Limit by lines
policy = LineLimitToolResultProcessingPolicy(max_lines=120)
```

### TraceSink

Observe runtime events for logging and debugging.

```python
from quenda.runtime import JsonlTraceSink

# Write events to JSONL file
sink = JsonlTraceSink("traces/run.jsonl")

agent = Agent(
    name="traced-agent",
    tools=tools,
    model=model,
    trace_sink=sink,
)
```

Custom trace sink:

```python
class CustomTraceSink(TraceSink):
    def record(self, event: AnyEvent) -> None:
        # Process event (should not raise exceptions)
        print(f"[{event.type}] {event}")
```

---

## Host Layer API

For agent package loading and workspace management.

```python
from quenda.host import (
    load_agent_package,
    AgentPackage,
    AgentConfigYaml,
    WorkspaceResolver,
    FileStorage,
    InstructionComposer,
    InstructionSource,
)
```

### load_agent_package

Load an agent package from a directory.

```python
pkg = load_agent_package("/path/to/agent")
pkg.name         # Agent name
pkg.version      # Version
pkg.description  # Description
pkg.agent_md     # AGENT.md content
pkg.config       # AgentConfigYaml or None
pkg.instructions # List of instruction files
```

### WorkspaceResolver

Resolve workspace binding and paths.

```python
resolver = WorkspaceResolver(workspace_path=Path("."))
ws_id = resolver.workspace_id
ws_binding_path = resolver.binding_path
```

### FileStorage

Session persistence.

```python
storage = FileStorage(base_path=Path("~/.quenda/users/<user>/agents/<agent>/workspaces/<ws_id>"))
storage.save_session(session.state)
state = storage.load_session(session_id)
```
