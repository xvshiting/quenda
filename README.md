<p align="center">
  <img src="assets/branding/logo.png" alt="Kora" width="420">
</p>

<h3 align="center">A lightweight, layered Agent framework for Python</h3>

<p align="center">
  <a href="https://www.python.org/downloads/"><img alt="Python" src="https://img.shields.io/badge/python-3.12+-blue.svg"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange.svg">
</p>

---

## What's New

### 2026-06

- **Skills Framework** — Composable capability packages with instructions, resources, and tools. Discover, activate, and use skills on demand. [Learn more →](docs/skills.md)
- **Context Compression** — Automatic summarization when context grows large, with configurable policies and manual `/compress` command.
- **Interaction Requests** — LLM can ask users for choices, confirmations, and input via structured interaction protocol.
- **Agent Commands Extension** — Define custom slash commands in `extensions/commands/*.py`.
- **Custom Tool Extensions** — Agent-local tools via `extensions/tools/*.py` with `config.yaml` declaration.
- **26 Model Providers** — OpenAI, Anthropic, DeepSeek, DashScope, Moonshot, Ollama, and 20 more.

---

## Kora Code

**Kora Code** is an AI coding agent that runs in your terminal. It reads your codebase, writes code, runs commands, and helps you ship.

> 📖 **[Kora Code Documentation →](agents/kora-code/README.md)**

```bash
# Install
pip install kora-agent kora-code

# Start interactive session
kora code

# One-shot task
kora code "Add error handling to the API client"
```

### Features

- **Code-aware** — Reads and understands your codebase structure
- **Workspace-scoped** — All file operations stay within your project directory
- **Safe execution** — Shell commands filtered, Python code sandboxed
- **Session persistence** — Conversations saved and resumable
- **Interactive mode switching** — Switch between `code`, `architect`, and `chat` modes
- **Skills on demand** — Activate capability packages as needed

### REPL Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/mode [code\|architect\|chat]` | Switch interaction mode |
| `/model <provider>/<model>` | Switch model mid-session |
| `/skill list` | List available skills |
| `/skill activate <name>` | Activate a skill |
| `/compress` | Manually compress context |
| `/status` | Show session and token info |
| `/reset` | Clear conversation history |

### Example Session

```
> read the main entry point and explain how it works

I'll read the main entry point...

[Reads src/kora/cli.py]

The entry point is `cli.py:main()`. It defines two subcommands:
- `kora run --agent <path>` — Run a custom agent from AGENT.md
- `kora code` — Run Kora Code Agent (built-in)

Each command supports one-shot mode (with a message) or REPL mode (without).

> add a --version flag to the CLI

I'll add a `--version` flag to the argument parser...

[Applies patch to cli.py]

Done. Added `--version` flag that prints the version and exits.

> run the tests

[Runs pytest]

All 42 tests passed.
```

---

## Kora SDK

Build agents in Python with a minimal API:

```python
from kora import Agent, tool
from kora.providers import get_provider_registry
from kora.tools import get_core_tools
import asyncio

@tool
def calculate(expression: str) -> float:
    """Safely evaluate a math expression."""
    import ast
    node = ast.parse(expression, mode='eval')
    return eval(compile(node, '<string>', 'eval'), {"__builtins__": {}}, {})

model = get_provider_registry().get_model("deepseek", "deepseek-v4-flash")

agent = Agent(
    name="assistant",
    system_prompt="You are a helpful assistant.",
    tools=[calculate, *get_core_tools(".")],
    model=model,
)

async def main():
    session = agent.open_session()
    result = await session.send("What is 15% of 847?")
    print(result)

asyncio.run(main())
```

> 📖 **[SDK Tutorials](docs/tutorials/agent/01-quickstart.md)** — 8 chapters covering agents, tools, providers, sessions, and events.

---

## Installation

```bash
# Kora Code — AI coding assistant (CLI)
pip install kora-agent kora-code

# Kora SDK — Build agents in Python
pip install kora-agent
```

**Requires Python 3.12+.** Zero required runtime dependencies.

---

## Features

- **Minimal API.** `Agent`, `Session`, `@tool`, and you're done.
- **26 model providers.** OpenAI, Anthropic, DeepSeek, DashScope, and more — one registry, one API.
- **9 core tools.** Filesystem, shell, Python sandbox, and user interaction — all workspace-scoped.
- **Skills framework.** Composable capability packages with instructions and resources.
- **Security by code.** SSRF protection, command filtering, import restrictions, workspace isolation.
- **Observable by default.** Every run emits structured events for streaming and debugging.
- **Context compression.** Automatic summarization when context grows large.

---

## Model Providers

Kora ships with **26 built-in providers** covering 300+ models:

| Provider | Example Models | API Key Env |
|----------|---------------|-------------|
| `openai` | `gpt-4o`, `gpt-4-turbo` | `OPENAI_API_KEY` |
| `anthropic` | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| `agnes` | `agnes-2.0-flash` | `AGNES_API_KEY` |
| `deepseek` | `deepseek-chat`, `deepseek-v4-flash` | `DEEPSEEK_API_KEY` |
| `deepseek-anthropic` | `deepseek-v4-flash` (Anthropic API) | `DEEPSEEK_API_KEY` |
| `dashscope` | `qwen-max`, `qwen-plus` | `DASHSCOPE_API_KEY` |
| `moonshot` | `moonshot-v1-8k`, `moonshot-v1-128k` | `MOONSHOT_API_KEY` |
| `openrouter` | `anthropic/claude-3.5-sonnet` | `OPENROUTER_API_KEY` |
| `ollama` | `llama3`, `mistral`, `qwen2` | local (no key) |

[Full provider list →](docs/tutorials/agent/04-providers.md)

Add a custom provider in 5 lines:

```python
from kora.providers import ProviderSpec, ModelSpec, get_provider_registry

registry = get_provider_registry()
registry.register(ProviderSpec(
    id="my-provider",
    name="My Provider",
    base_url="https://api.example.com/v1",
    api="openai-completions",
    api_key="${MY_API_KEY}",
    models=(ModelSpec(id="my-model", name="My Model", tool_calling=True),),
))
```

---

## Built-in Tools

`get_core_tools(workspace)` returns **9 essential tools**:

| Tool | Capability |
|------|-----------|
| `list_files` | Browse directories (ls, find, tree) |
| `search_text` | Search file contents (grep, rg) |
| `read_file` | View files with line ranges |
| `write_file` | Create or overwrite files |
| `apply_patch` | Apply targeted text patches |
| `run_shell` | Execute shell commands (filtered) |
| `execute_python` | Run Python in a sandbox |
| `request_interaction` | Ask the user for input |
| `request_skill_activation` | Request skill activation |

[Full tool reference →](docs/tools.md)

---

## Architecture

```
Interface → Host → Runtime → Kernel
```

| Layer | Responsibility |
|-------|---------------|
| **Kernel** | Synchronous model-tool loop. No knowledge of agents, sessions, or users. |
| **Runtime** | Async Agent/Session/Run lifecycle. Event emission, context management. |
| **Host** | Persistence, identity, permissions, instruction composition, skills. |
| **Interface** | Event rendering, user interaction, REPL. |

Each layer depends only on the layer inside it. The Kernel is fully testable with fake models — no network required.

---

## Documentation

| Resource | Description |
|----------|-------------|
| **[Getting Started](docs/getting-started.md)** | Setup and your first agent |
| **[Tools Guide](docs/tools.md)** | All built-in tools with parameters |
| **[Skills Guide](docs/skills.md)** | Capability packages system |
| **[API Reference](docs/api.md)** | Complete API reference |
| **[SDK Tutorials](docs/tutorials/agent/01-quickstart.md)** | Step-by-step Python SDK guide (8 chapters) |
| **[CLI Tutorials](docs/tutorials/code/01-quickstart.md)** | Step-by-step Kora Code guide (5 chapters) |
| **[Architecture Decisions](docs/decisions/)** | ADR records |

---

## Contributing

Kora is intentionally small. Before making a change, read [`CLAUDE.md`](CLAUDE.md) and the [ADR records](docs/decisions/).

1. Identify which architectural layer owns the change.
2. Prefer the smallest complete change; add tests with behavior changes.
3. Do not cross established layer boundaries.

```bash
pip install -e ".[dev]"   # editable install with dev tooling
pytest                    # run tests
ruff check src/kora       # lint
```

---

## License

MIT
