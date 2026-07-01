# ADR-013: Agent Package Distribution via PyPI

**Status:** Accepted  
**Date:** 2025-07-18  
**Deciders:** @xvshiting  

## Context

The Kora framework provides a mechanism to load agents from packages
(AGENT.md + config.yaml + instructions + extensions). The official Kora
Code Agent (`kora-code`) was initially bundled inside the monorepo at
`agents/kora-code/` and discovered via a hardcoded relative path.

As the project grows, we need a clean distribution model where:

- The framework (`kora`) provides the loading mechanism.
- Agent definitions are distributed as independent packages.
- Users install only the agents they need.
- The framework can discover installed agents without hardcoded paths.

## Decision

We adopt a **two-package distribution model**:

| Package | PyPI name | Responsibility |
|---------|-----------|---------------|
| `kora-agent` | `kora-agent` | Framework: kernel, runtime, host, built-in tools |
| `kora-code` | `kora-code` | Agent definition: AGENT.md, instructions, extensions |

### Discovery mechanism

Agent packages register a **`kora.agents` entry point** in their
`pyproject.toml`:

```toml
[project.entry-points."kora.agents"]
kora-code = "kora_code"
```

The module pointed to must expose an `AGENT_DIR` attribute — a
`pathlib.Path` pointing to the directory containing `AGENT.md`.

The framework's `find_builtin_agent(name)` function:

1. First scans `importlib.metadata.entry_points(group="kora.agents")`
   for a matching entry point.
2. Falls back to a development-mode relative path lookup.

### User installation

```bash
# Explicit two-package install
pip install kora-agent kora-code

# Convenience extra
pip install kora-agent[code]    # pulls in kora-code
```

### Package structure for kora-code

```
kora-code/
├── pyproject.toml          # entry-points.kora.agents = "kora_code"
├── README.md
└── src/
    └── kora_code/
        ├── __init__.py     # exposes AGENT_DIR
        ├── __about__.py    # version
        └── agent/          # package data
            ├── AGENT.md
            ├── config.yaml
            ├── instructions/
            └── extensions/
```

## Consequences

### Positive

- Clean separation of concerns: framework vs. agent definitions.
- No hardcoded paths in the framework.
- Third-party developers can publish their own agent packages.
- Versioning is independent for framework and each agent.
- `pip install kora` stays minimal (no unnecessary deps).

### Negative

- Users must install two packages (mitigated by `kora[code]` extra).
- Slightly more complex development setup (editable install for both).

### Neutral

- `kora-code` becomes a thin data+Python shim around AGENT.md.
- Future agents (e.g., `kora-architect`, `kora-writer`) follow the
  same pattern.
