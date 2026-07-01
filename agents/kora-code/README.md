# Kora Code Agent

The official coding agent for the [Kora](https://github.com/xvshiting/kora) framework.

## Installation

```bash
pip install kora-agent kora-code
```

Or with the `code` extra:

```bash
pip install kora-agent[code]
```

## Usage

```bash
# Interactive REPL mode
kora code

# One-shot task
kora code "refactor this module to use async"
```

## What it does

Kora Code is an engineering agent that:
- Reads and writes code
- Runs shell commands and Python in a sandbox
- Searches and patches files
- Reasons about systems and architecture

It is built on the same public `kora` APIs available to every developer.
