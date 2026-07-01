# ADR-008: Slash Commands as Registered Small Commands with Explicit State and Host Context Rebuild

## Status

Proposed

## Context

Quenda is being shaped as a Unix-style agent framework:

- small, composable units
- explicit state instead of hidden framework magic
- text-based interfaces where practical
- clear layer boundaries
- no special-case branches for individual features

Interactive agent sessions need a control surface. Users want to:

- inspect the current session
- change modes
- clear or reset state
- toggle behavior
- update per-session context

Today, such controls are often implemented as ad hoc command checks in a CLI or REPL loop. That approach works for a prototype, but it tends to grow into framework special casing:

- each command gets its own `if` branch
- command behavior leaks into the runtime loop
- state changes become implicit
- the next turn reuses stale context unless every caller remembers to rebuild it

Quenda should avoid that shape.

## Decision

Slash commands should be a registered command system with explicit state changes.

### 1. Slash commands are a Host-level control surface

Slash commands belong to the interactive control layer above Runtime and Kernel.

They are not:

- Kernel features
- model features
- tool features
- special CLI branches

They are a small command protocol for human-facing interfaces such as CLI, TUI, or web chat.

### 2. Commands must be registered, not hard-coded

Each command should be defined as a small unit with:

- a stable name
- a short description
- optional argument schema
- a handler that returns a state transition

The system should discover commands from a registry instead of encoding each one as framework special case logic.

Example command shape:

```text
/help
/clear
/mode review
/context show
/instructions reload
```

The exact command set is not fixed by this ADR. The important part is that commands are registered entries, not special branches in the core loop.

### 3. Commands return explicit state transitions

A command should not directly mutate hidden global state.

Instead, it should return a structured result describing:

- what state changed
- whether the command should be persisted
- whether the next turn requires context rebuild
- what short user-facing message to show

Recommended result shape:

```text
CommandResult
  - status: "ok" | "error"
  - state_patch: explicit state diff
  - rebuild_context: bool
  - message: short feedback text
```

This makes command behavior inspectable and testable.

### 4. Host rebuilds context on every turn

Host should treat the current prompt/context as a derived artifact, not a cached blob that gets patched in place.

On each turn, Host should rebuild the effective context from:

- framework contract
- agent base prompt
- agent instructions
- workspace instructions
- user and workspace state
- active command state
- any other approved overlays

That means a command changes state, and Host turns that state into the next turn's context.

The command itself does not own the prompt composition logic.

### 5. Runtime remains command-agnostic

Runtime should continue to manage:

- Session
- Run
- event emission
- model execution flow

It should not need to know whether a state change came from:

- a slash command
- a settings UI
- a server-side policy update

Runtime consumes the already-resolved state and context that Host provides.

### 6. Kernel remains completely unaware

Kernel must not know about slash commands.

It only sees:

- messages
- tools
- model responses

This keeps the model-tool loop pure and avoids framework-specific exceptions inside the core executor.

## Why This Fits Quenda

This pattern matches the framework boundary model already used in Quenda:

```text
Interface -> Host -> Runtime -> Kernel
```

Slash commands are a control-plane concern, so they naturally sit in Interface and Host.

The design also matches Unix philosophy:

- one command, one responsibility
- small text interfaces
- state is explicit
- composition beats special casing
- reusable primitives beat monolithic modes

## Command State Model

Command state should be serializable and versioned like other Host state.

Examples of explicit state:

- current interaction mode
- whether assistant output is compact or verbose
- current model override
- whether the next turn should rebuild instructions
- transient session flags such as "paused" or "review mode"

State should be stored where Host already stores session or workspace state, not in ad hoc process memory.

## Processing Flow

Recommended turn flow:

1. User enters input.
2. Interface checks whether the input is a registered slash command.
3. If yes, command handler returns a `CommandResult`.
4. Host applies the state patch.
5. Host rebuilds effective context for the next turn if needed.
6. If the input is not a command, it is forwarded as a normal user message to Runtime.
7. Runtime executes the run.
8. Host persists any resulting state changes.

This flow keeps the "parse command" step separate from the "run agent" step.

## Non-Goals

This ADR does not define:

- the exact command syntax grammar
- the exact set of built-in commands
- the UI presentation of command help
- a plugin marketplace for commands
- automatic command discovery from arbitrary files
- command execution inside Kernel or tools

It also does not require every Quenda deployment to expose slash commands.
Non-interactive SDK and batch use cases may ignore this system entirely.

## Consequences

### Positive

- command behavior becomes explicit and testable
- new commands can be added without editing core loops
- Host can rebuild context deterministically every turn
- session state stays durable and inspectable
- CLI, TUI, and future web interfaces can share one command protocol
- Kernel and Runtime remain cleanly separated from interactive control flow

### Negative

- Host needs a small command state model
- context rebuild becomes an intentional per-turn operation
- interactive surfaces need a shared command registry abstraction
- there is a little more upfront design work than hard-coded CLI branches

## Guidance for Implementation

When this ADR is implemented, prefer:

- a `Command` protocol or equivalent small interface
- a command registry with stable names
- structured command results with explicit state patches
- Host-owned context rebuild on each turn
- no command-specific branches in Kernel
- no special Runtime semantics for individual commands

## Recommendation

Quenda should adopt this principle.

It is not required for every consumer, but it is valuable for the framework because it keeps interactive control composable, inspectable, and aligned with Quenda's layer boundaries.
