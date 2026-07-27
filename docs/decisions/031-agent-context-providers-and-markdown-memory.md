# ADR-031: Agent Context Providers and Markdown Memory

## Status

Accepted

## Context

Quenda already composes framework, agent, user, workspace, and skill
instructions before each Run. Agent packages can extend commands, tools,
interactions, providers, and policies, but they cannot add their own textual
context sources through the same package-local extension model.

Quenda Code needs three always-on sources:

- package-owned `SOUL.md`
- private user-owned `USER.md`
- private user-owned `MEMORY.md`

It also needs an expandable detailed memory library under `memory/**/*.md`.
Those detailed files must not all remain in the prompt. They should be searched
and read explicitly without requiring a persistent index.

These filenames are Quenda Code policy, not framework concepts.

## Decision

### Generic context provider seam

Core defines an ordered `ContextProviderRegistry`. Agent-local providers live
under:

```text
<agent-package>/extensions/context/*.py
```

Each module exports either a `providers` list or `register(registry)`.
Providers receive a per-Run `ContextProviderRequest` and return
`list[InstructionSource]`. The Host invokes them during text refresh before
`InstructionComposer` builds the final prompt.

Core does not recognize `SOUL.md`, `USER.md`, or `MEMORY.md`.

### Stable extension context

Agent-local extensions may receive an `AgentExtensionContext` containing
Host-resolved paths and identities:

- agent name and package path
- current user
- private user-agent path
- workspace path and logical workspace id

Tool modules may keep the existing `register(builder)` form or opt into
`register(builder, context)`. This preserves compatibility while avoiding
extension code that reconstructs Host identity or storage paths itself.

Agent packages may also register idempotent initializers under:

```text
<agent-package>/extensions/setup/*.py
```

Initializers run after Host resolves `AgentExtensionContext` and before context
providers or tools are loaded. They may create missing Agent-owned state but
must not overwrite existing user data. Context providers remain read-only.

### Quenda Code adapter

Quenda Code provides an Agent-local context adapter:

```text
SOUL.md                         package-owned, always on
<user-agent>/USER.md            private, optional, always on
<user-agent>/MEMORY.md          private, optional, always on
<user-agent>/memory/**/*.md     private, detailed, not automatically injected
```

`USER.md` is user-authored and authoritative. `MEMORY.md` is curated context
and is explicitly framed as memory rather than a command.

On first setup, Quenda Code creates template `USER.md` and `MEMORY.md` files
plus the `memory/` directory through its Agent-local initializer. Repeated
setup is idempotent and preserves edited files.

### Index-free detailed memory

Quenda Code registers two read-only Agent-local tools:

- `memory_search`: scans Markdown files and returns ranked excerpts
- `memory_get`: reads a bounded line range from one returned path

The implementation has no SQLite or vector index. It rejects path traversal,
limits result counts and output size, and keeps all detailed memory outside the
prompt until requested.

Persistent indexing, embeddings, automatic writes, forgetting, and memory
promotion are deferred. They can be added later as alternative adapters behind
the same extension seams.

### Dynamic module identity

Agent-local Python modules are identified by extension kind, filename, and a
stable hash of their resolved path. Two agents may therefore use the same
extension filename without sharing the wrong loaded module.

## Consequences

### Positive

- Context assembly becomes a real Agent extension seam.
- Quenda Code demonstrates the seam without imposing its file conventions.
- Extensions receive Host-resolved private paths instead of recreating them.
- Detailed memory stays inspectable and requires no index maintenance.
- Existing one-argument custom tool registration remains compatible.

### Negative

- Context provider code is trusted Agent-package code.
- Index-free search is intentionally simple and will not scale to very large
  memory libraries.
- Automatic memory writes and lifecycle policies remain future work.
