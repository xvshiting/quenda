# Quenda Code Agent

The official coding agent for the [Quenda](https://github.com/xvshiting/quenda) framework.

## Installation

```bash
pip install quenda quenda-code
```

Or with the `code` extra:

```bash
pip install quenda[code]
```

## Usage

```bash
# Interactive REPL mode
quenda code

# One-shot task
quenda code "refactor this module to use async"
```

## What it does

Quenda Code is an engineering agent that:
- Reads and writes code
- Runs shell commands and Python in a sandbox
- Searches and patches files
- Reasons about systems and architecture

It is built on the same public `quenda` APIs available to every developer.

## Capability config

The agent package declares its capabilities in `src/quenda_code/agent/config.yaml`.

For network tools, `quenda code` just declares the bundle:

```yaml
tools:
  bundles:
    - core
    - network
```

That means `http_request` and `web_fetch` are available from config.
Runtime permission prompts are reserved for reading directories outside the workspace in REPL.
