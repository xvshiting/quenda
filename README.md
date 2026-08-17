<p align="center">
  <img src="assets/branding/logo.png" alt="Quenda" width="420">
</p>

<h3 align="center">A lightweight, layered Agent framework for Python</h3>

<p align="center">
  <a href="https://www.python.org/downloads/"><img alt="Python" src="https://img.shields.io/badge/python-3.12+-blue.svg"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange.svg">
</p>

---

## What's New

### 2026-08 (v0.3.4)

- **Web UI** — A FastAPI gateway + React dashboard for agents, sessions, workspaces, and settings. `quenda web` for foreground use, `quenda gateway` for a background service.
- **Self-Evolution Platform** — Post-run memory evolution with `automatic`/`review`/`disabled` write modes, plus staged skill proposals with validation and rollback.
- **Config-Driven Providers** — Declare `builtin` overrides, `custom` OpenAI-compatible endpoints, and local `llama-server` presets directly in `config.yaml` ([ADR-035](docs/decisions/035-config-driven-provider-catalogs.md)).

### 2026-06 (v0.3.0)

- **Skills Framework** — Composable capability packages with instructions, resources, and tools. Discover, activate, and use skills on demand. [Learn more →](docs/skills.md)
- **Context Compression** — Automatic summarization when context grows large, with configurable policies and manual `/compress` command.
- **Interaction Requests** — LLM can ask users for choices, confirmations, and input via structured interaction protocol.
- **Custom Tool Extensions** — Agent-local tools via `extensions/tools/*.py` with `config.yaml` declaration.
- **Policy System** — Runtime policies for termination, tool selection, and result processing.
- **Multimodal Support** — Image input support with resource activation.
- **26 Model Providers** — OpenAI, Anthropic, DeepSeek, DashScope, Moonshot, Ollama, and 20 more.

---

## Quenda Code

**Quenda Code** is an AI coding agent that runs in your terminal. It reads your codebase, writes code, runs commands, and helps you ship.

> 📖 **[Quenda Code Documentation →](agents/quenda-code/README.md)**

```bash
# Install
pip install quenda quenda-code

# Start interactive session
quenda code

# One-shot task
quenda code "Add error handling to the API client"
```

## Personal Agents

Create a long-lived local agent with its own prompts, skills, memory, sessions,
and default workspace:

```bash
quenda agent create reviewer
quenda reviewer
```

Seed an independent agent from an installed package or source directory:

```bash
quenda agent create coder --from quenda-code
quenda agent create writer --from ./agents/writer
```

Agents live under `~/.quenda/agent-<name>/`. Without `--workspace`, they work
inside their own `workspace/`; the same agent can enter a project explicitly:

```bash
quenda reviewer --workspace ~/Workspace/my-project
```

### Features

- **Code-aware** — Reads and understands your codebase structure
- **Workspace-aware** — File tools resolve paths against the selected project; local execution follows explicit permissions and trust policy
- **Explicit execution trust** — Local shell/Python run as `local-trusted`; strong isolation must use a future isolated backend
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

[Reads src/quenda/cli.py]

The entry point is `cli.py:main()`. It defines two subcommands:
- `quenda run --agent <path>` — Run a custom agent from AGENT.md
- `quenda code` — Run Quenda Code Agent (built-in)

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

## Quenda SDK

Build agents in Python with a minimal API:

```python
from quenda import Agent, tool
from quenda.providers import get_provider_registry
from quenda.tools import get_core_tools
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
# Quenda Code — AI coding assistant (CLI)
pip install quenda quenda-code

# Quenda SDK — Build agents in Python
pip install quenda
```

**Requires Python 3.12+.** Zero required runtime dependencies.

---

## Web UI

A FastAPI gateway plus React dashboard to manage agents, sessions, workspaces,
and settings from the browser:

```bash
pip install "quenda[web]"   # optional dependencies

quenda web --port 8000      # foreground (dev)

quenda gateway start        # background service
quenda gateway status
quenda gateway logs
quenda gateway stop
```

Pages cover agents (create/edit/detail with model picker), sessions (chat with
streaming events), workspaces, and settings. Sessions run through the same
Host layer as the CLI.

---

## Features

- **Minimal API.** `Agent`, `Session`, `@tool`, and you're done.
- **27 model providers.** OpenAI, Anthropic, DeepSeek, DashScope, and more — one registry, one API.
- **Core tools.** Filesystem, local-trusted shell/Python, and user interaction.
- **Skills framework.** Composable capability packages with instructions and resources.
- **Explicit security contracts.** SSRF protection, command filtering, permissions, and fail-closed isolation requirements.
- **Observable by default.** Every run emits structured events for streaming and debugging.
- **Context compression.** Automatic summarization when context grows large.
- **Self-evolution.** Post-run memory writes and staged skill proposals, auditable and roll-back-able.
- **Config-driven providers.** Built-in overrides, custom OpenAI-compatible endpoints, and `llama-server` presets in `config.yaml`.
- **Web UI.** Optional FastAPI/React dashboard with `quenda web` and `quenda gateway`.

---

## Model Providers

Quenda ships with **27 built-in providers** covering 300+ models:

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
from quenda.providers import ProviderSpec, ModelSpec, get_provider_registry

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

Agents can also declare providers in `config.yaml` — a `builtin` override, a
`custom` OpenAI-compatible endpoint, or a `llama-server` preset — and select
roles with `models.default` / `models.vision` using `provider/model`
([ADR-035](docs/decisions/035-config-driven-provider-catalogs.md)):

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"

  local-llama:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    models:
      - id: "qwen3.5:9b"
        tool_calling: true

models:
  default: openai/gpt-4o
  vision: local-llama/qwen3.5:9b
```

---

## Built-in Tools

`get_core_tools(workspace)` returns **11 essential framework tools**:

| Tool | Capability |
|------|-----------|
| `list_files` | Browse directories (ls, find, tree) |
| `search_text` | Search file contents (grep, rg) |
| `read_file` | View files with line ranges |
| `write_file` | Create or overwrite files |
| `apply_patch` | Apply targeted text patches |
| `run_shell` | Execute shell commands (filtered) |
| `execute_python` | Run Python code in subprocess |
| `get_current_datetime` | Get exact current time or convert timezones |
| `request_interaction` | Ask the user for structured input |
| `request_skill_activation` | Ask Host to activate discovered skills |
| `activate_resource` | Attach a historical session resource |

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
| **[CLI Tutorials](docs/tutorials/code/01-quickstart.md)** | Step-by-step Quenda Code guide (5 chapters) |
| **[Architecture Decisions](docs/decisions/)** | ADR records |

---

## Contributing

Quenda is intentionally small. Before making a change, read [`CLAUDE.md`](CLAUDE.md) and the [ADR records](docs/decisions/).

1. Identify which architectural layer owns the change.
2. Prefer the smallest complete change; add tests with behavior changes.
3. Do not cross established layer boundaries.

```bash
pip install -e ".[dev]"   # editable install with dev tooling
pytest                    # run tests
ruff check src/quenda       # lint
```

---

## License

MIT
