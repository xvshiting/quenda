# Getting Started

This guide will help you create your first Quenda agent.

## Installation

### Requirements

- Python 3.12 or higher
- pip or uv package manager

### Basic Installation

```bash
pip install quenda
```

### Optional Dependencies

```bash
# Network tools (HTTP requests, web search)
pip install quenda[network]

# Anthropic Claude support
pip install quenda[anthropic]

# All dependencies
pip install quenda[all]
```

## Set Up Environment

Before running examples, you need to configure your API keys:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
# For example:
# DASHSCOPE_API_KEY=your-dashscope-api-key

# Or export directly in your shell
export DASHSCOPE_API_KEY='your-api-key'
```

## Your First Agent

### Step 1: Define Simple Tools

The easiest way to create a tool is using the `@tool` decorator:

```python
from quenda import tool

@tool
def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}!"

@tool
def add(a: int, b: int) -> str:
    """Add two numbers together."""
    return str(a + b)

@tool
def calculate(expression: str) -> str:
    """
    Evaluate a math expression.

    Supports: +, -, *, /, **, ()
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"
```

The decorator automatically:
- Extracts the tool name from the function name
- Extracts the description from the docstring
- Generates JSON Schema from type hints

### Step 2: Set Up a Model Provider

Quenda ships built-in provider specs under `quenda.providers` for common
backends. The easiest path is to resolve a model from the global provider
registry:

```python
from quenda.providers import get_provider_registry

registry = get_provider_registry()
model = registry.get_model("dashscope", "qwen-max")
```

| Provider ID | Example models | Env var |
|-------------|----------------|---------|
| `openai` | `gpt-4o`, `gpt-4-turbo` | `OPENAI_API_KEY` |
| `anthropic` | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| `dashscope` | `qwen-max`, `qwen-plus` | `DASHSCOPE_API_KEY` |
| `jdcloud` | `glm-5`, `glm-4` | `JDCLOUD_API_KEY` |
| `deepseek` | `deepseek-chat`, `deepseek-reasoner` | `DEEPSEEK_API_KEY` |
| `deepseek-anthropic` | `deepseek-v4-flash`, `deepseek-v4-pro` | `DEEPSEEK_API_KEY` |
| `moonshot` | `moonshot-v1-8k`, `moonshot-v1-32k` | `MOONSHOT_API_KEY` |
| `openrouter` | `anthropic/claude-3.5-sonnet`, `openai/gpt-4o` | `OPENROUTER_API_KEY` |
| `ollama` | `llama3`, `mistral`, `qwen2` | local |

For a custom provider that uses an OpenAI-compatible or Anthropic-compatible
API, the simplest path is to register a `ProviderSpec`:

```python
from quenda.providers import ProviderSpec, ModelSpec, get_provider_registry

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

If you need full control over the HTTP protocol, implement the kernel
`Model` protocol directly. Here's a sketch using an OpenAI-compatible
client:

```python
from openai import OpenAI
from quenda.kernel import Model, ModelResponse, Tool, ToolCall, Message

class SimpleModel:
    """A custom model provider implementing the Model protocol."""

    def __init__(self, base_url: str, api_key: str, model: str = "gpt-4"):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                openai_messages.append({"role": msg.role, "content": msg.content})
            # Handle tool calls and results...

        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            tools=[{"type": "function", "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }} for t in tools] if tools else None,
            tool_choice="auto" if tools else None,
        )

        # Convert response
        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return ModelResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )
```

### Step 3: Create an Agent

```python
from quenda import Agent
from pathlib import Path

# Define workspace for file operations
workspace = Path(".")

# Create the agent
agent = Agent(
    name="my-assistant",
    system_prompt="You are a helpful assistant. Use tools when appropriate.",
    tools=[
        greet,
        add,
        calculate,
        # Add file system tools (workspace-scoped):
        # ListFilesTool(workspace),
        # ReadFileTool(workspace),
    ],
    model=model,
)
```

### Step 4: Run a Session

```python
import asyncio
from quenda.runtime import RunStarted, RunCompleted, ToolExecuted

async def main():
    # Open a session (persists conversation history)
    session = agent.open_session()

    # Define an event handler for observability
    def on_event(event):
        if isinstance(event, RunStarted):
            print("🚀 Run started")
        elif isinstance(event, ToolExecuted):
            status = "✅" if not event.is_error else "❌"
            print(f"🔧 Tool [{event.tool_name}] {status}")

    # Send a message
    result = await session.send(
        "What is 123 + 456?",
        on_event=on_event,
    )
    print(f"Result: {result}")

    # Continue the conversation
    result = await session.send("Now multiply that by 2")
    print(f"Result: {result}")

asyncio.run(main())
```

## Using File System Tools

File system tools require a workspace path for security (paths are
validated and rejected if they escape the workspace):

```python
from quenda.tools import get_filesystem_tools

workspace = Path("/path/to/workspace")

agent = Agent(
    name="file-assistant",
    tools=[
        # 5 tools: list_files, search_text, read_file, write_file, apply_patch
        *get_filesystem_tools(workspace),
    ],
    model=your_model,
)
```

Individual tools are also available: `ListFilesTool`, `SearchTextTool`,
`ReadFileTool`, `WriteFileTool`, `ApplyPatchTool`. See the
[Tools Guide](tools.md) for per-tool parameters.

## Using the Core Tools Bundle

`get_core_tools(workspace)` returns the 10 essential framework tools:
filesystem, execution, interaction, skill activation, and resource activation.

```python
from quenda.tools import get_core_tools

agent = Agent(
    name="coder",
    tools=get_core_tools(Path(".")),
    model=your_model,
)
```

## Using Network Tools

Network tools require the `httpx` package:

```bash
pip install quenda[network]
```

```python
from quenda.tools import get_network_tools

agent = Agent(
    name="web-assistant",
    tools=[
        # HTTP request, web fetch, web search
        *get_network_tools(),
    ],
    model=your_model,
)
```

## Using Python Execution Tool

```python
from quenda.tools import PythonExecutionTool

agent = Agent(
    name="code-assistant",
    tools=[
        PythonExecutionTool(),  # workspace is optional; sandboxed execution
    ],
    model=your_model,
)
```

## Using Shell Execution Tool

```python
from quenda.tools import RunShellTool

agent = Agent(
    name="shell-assistant",
    tools=[
        RunShellTool(workspace),  # execute shell commands (dangerous commands blocked)
    ],
    model=your_model,
)
```

## Next Steps

- [Tools Guide](tools.md) - Learn about all available tools
- [API Reference](api.md) - Explore the full API
- [Examples](../examples/) - See complete working examples
