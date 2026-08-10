# ADR-034: Local Agent Homes and Named Launchers

## Status

Accepted

## Context

Quenda could load an Agent package by path or Python entry point, but users had
no uniform way to create, discover, customize, and launch several long-lived
agents. The official `quenda code` command was also a privileged CLI branch
instead of the same experience being available to every agent.

Quenda needs one definition format that supports three Host contexts:

- personal use with durable prompts, memory, sessions, and a default workspace
- project use with the same identity operating in an explicitly selected folder
- server use where Host adapters provide user, tenant, workspace, and storage
  isolation around the same Agent definition

## Decision

The local Host adopts **Agent Home** as its user-facing unit. A named agent
`<name>` lives at:

```text
~/.quenda/agent-<name>/
```

The directory contains the agent definition and its local state:

```text
AGENT.md
SOUL.md
USER.md
MEMORY.md
config.yaml
agent.yaml
instructions/
skills/
memory/
sessions/
artifacts/
workspace/
```

`quenda agent create <name>` creates a minimal runnable home. Supplying
`--from <source>` copies an installed Agent package, a source directory, or the
parent directory of an `AGENT.md` into a new independent home. The source is an
initialization origin, not a live dependency.

The filesystem is the discovery source of truth. The local Host scans
`agent-*` directories containing `AGENT.md`; no central registry is required.
`agent.yaml` stores provenance and creation metadata.

Every Agent Home supports both launch forms:

```text
quenda <name>
quenda agent run <name>
```

Without `--workspace`, execution uses the home-local `workspace/`. With an
explicit workspace, identity and capabilities still come from the Agent Home
while tools operate in the selected project.

`QUENDA_HOME` may replace `~/.quenda` for tests and alternate Host setups.
Server Hosts may map the same logical Agent Home interface to another store;
they must not depend on the local directory naming convention.

## Layer Ownership

- Host owns Agent Home creation, discovery, source resolution, and context.
- CLI maps commands to the Host interface and does not implement discovery.
- Runtime and Kernel remain unaware of Agent Homes.
- Team orchestration remains a separate upper-layer concern.

## Consequences

### Positive

- Creating a personal agent no longer requires packaging knowledge.
- All agents receive the same named-launch experience as Quenda Code.
- Prompt and memory files remain ordinary, inspectable, editable files.
- One definition works in personal, project, and future server contexts.
- Copy-on-create lets initialized agents evolve independently.

### Negative

- Copying an Agent package means later package upgrades do not automatically
  update existing homes.
- Agent names can conflict with built-in CLI commands; the explicit
  `quenda agent run <name>` form remains unambiguous.
- Team directory semantics still require a separate orchestration decision.
