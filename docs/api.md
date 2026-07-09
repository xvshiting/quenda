# API Reference

Core API for the Quenda framework.

## Public API

```python
from quenda import Agent, Session, tool
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

# The 10 essential framework tools:
# filesystem, execution, interaction, skill activation, and resource activation
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
