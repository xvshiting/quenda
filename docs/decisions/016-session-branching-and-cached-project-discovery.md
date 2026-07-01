# ADR-016: Session Branching for Cached Project Discovery

## Status

Proposed

## Context

Quenda sessions are increasingly used for coding-agent workflows where the
first expensive step is not code generation, but project discovery:

- listing directories
- reading README and configuration files
- locating entry points
- inspecting tests
- building an understanding of project structure

For large repositories, this can consume a meaningful number of input
tokens before the user asks the first concrete implementation task.

This cost becomes more important when the agent repeatedly starts from a
cold session and re-reads the same project context. It becomes less
painful when the model provider supports prompt caching, because early
context can be reused more cheaply across related follow-up work.

The project therefore needs a workflow that supports:

- doing project discovery early
- retaining that high-value context as a reusable baseline
- branching task-specific work from that baseline
- returning to the baseline after a task completes
- keeping this behavior separate from ordinary source-control branches

## Decision

Quenda should support **session branching** as a Host-level control-plane
feature.

The intended workflow is:

1. Start a session and let the agent learn the project.
2. Mark that state as a reusable base branch.
3. Fork task branches from the base branch for specific work.
4. Return to the base branch when starting the next task.

This gives Quenda a reusable context baseline that works well with prompt
cache friendly providers and avoids repeated project re-discovery.

## What a Session Branch Is

A session branch is:

- a branch of conversation state
- derived from an existing session checkpoint
- intended to preserve or reuse context

A session branch is **not**:

- a Git branch
- a brand-new unrelated session
- a Kernel feature
- a replacement for compression

The branch model is about reusing a high-value conversational baseline.

## Why This Exists

This design is particularly useful for coding agents because project
discovery is often:

- expensive
- repetitive
- mostly stable across related tasks

If Quenda can preserve that baseline and let later tasks fork from it, the
system can:

- reduce repeated file-reading cost
- reuse prompt cache more effectively
- keep task-specific sessions cleaner
- separate "project understanding" from "task execution"

## Layer Ownership

Session branching follows the normal Quenda architecture:

```text
Interface -> Host -> Runtime -> Kernel
```

| Layer | Owns | Does not own |
|---|---|---|
| `Host` | `/branch` commands, branch metadata, lineage, persistence, branch switching, branch naming, base branch designation | Model execution semantics |
| `Runtime` | Loading the active branch view into session execution, continuing from the selected branch state | Branch policy, UI commands, storage layout |
| `Kernel` | Nothing branch-specific | Session identity, lineage, persistence |

Recommended rule:

- **Host manages branches**
- **Runtime executes the selected branch**
- **Kernel stays unaware**

## Relationship to Compression

Branching and compression solve different problems.

Branching solves:

- reusable project-discovery context
- task isolation
- returning to a known baseline

Compression solves:

- overlong history inside one branch
- prompt budget control
- long-session maintainability

These features should complement each other, not replace each other.

## Base Branch and Task Branches

Quenda should recognize two practical branch roles:

- **base branch**: the stable project-discovery branch
- **task branch**: a branch forked from a base or another branch for one
  concrete unit of work

The base branch should remain relatively clean and stable. It should be
used to retain high-value repository knowledge, not as a dumping ground
for many unrelated tasks.

Task branches can be shorter-lived and more disposable.

## Command Surface

The first version should expose branching as a Host-level command set.

Example command surface:

```text
/branch list
/branch create <name>
/branch switch <name-or-id>
/branch back
/branch fork <name>
/branch base
```

Suggested semantics:

- `/branch create <name>`: create a branch from the current session
  checkpoint
- `/branch fork <name>`: explicit task-branch action from the current
  branch
- `/branch switch <name-or-id>`: switch active execution to another
  branch
- `/branch list`: show available branches and lineage
- `/branch back`: return to the parent or base branch
- `/branch base`: mark the current branch as the reusable project base

The exact syntax can evolve, but the command family belongs in Host, not
in Runtime or Kernel.

## Persistence Model

Session branches should be stored in Quenda's own Host persistence model.

They should **not** be implemented by directly editing session files
through Git operations.

Why not use Git as the underlying implementation:

- session branches and Git branches are different concepts
- session data includes conversation state, summaries, usage counters,
  and lineage metadata that are not source-control primitives
- coupling branch switching to Git checkout or commit behavior creates
  unnecessary operational risk
- the user may already be using Git independently for code work

Git is excellent for source code history. It is not the right primary
storage engine for conversation lineage.

## Git Relationship

Session branching may optionally record Git-related metadata, such as:

- current Git branch name
- current commit SHA
- dirty working tree state

This metadata can help the UI explain context, but Quenda session
branching must remain correct even if:

- the workspace is not a Git repository
- the user changes Git branches manually
- the working tree is dirty

Recommended rule:

- session branches are **Git-aware**
- session branches are **not Git-backed**

## Data Model

The first version should keep the model explicit and minimal.

Suggested fields:

```text
SessionBranch
  - branch_id: str
  - session_id: str
  - parent_branch_id: str | None
  - base_branch_id: str | None
  - title: str
  - kind: "base" | "task"
  - checkpoint_ref: str
  - archived: bool
  - created_at: datetime
  - git_branch: str | None
  - git_commit: str | None
  - git_dirty: bool | None
```

Important ideas:

- `session_id` keeps the overall conversation family identity
- `branch_id` identifies one branch within that family
- `checkpoint_ref` points to the snapshot or message boundary from which
  the branch continues

This keeps branch lineage inspectable and avoids magical hidden copying.

## Execution Model

Recommended flow:

1. The user performs project discovery in a session.
2. Host marks the branch as a base branch.
3. The user runs `/branch fork task-xyz`.
4. Host creates a new branch record derived from the current checkpoint.
5. Runtime loads the new branch's visible session state.
6. The agent performs task-specific work inside that branch.
7. The user switches back to the base branch after the task is complete.
8. A later task forks again from the base branch.

This keeps high-value discovery context reusable while isolating
task-specific conversations.

## Non-Goals

This ADR does not define:

- exact snapshot storage format
- automatic Git branch creation
- multi-user collaborative branching
- merge semantics between session branches
- visual branch-tree UI
- prompt-cache provider internals

Those can be added later if the workflow proves valuable.

## Consequences

### Positive

- avoids repeated project re-discovery
- makes prompt-cache-friendly providers more valuable
- keeps project understanding separate from task chatter
- gives users a clean mental model for reusable context
- avoids conflating conversation structure with source-control history

### Negative

- adds persistence and lineage complexity
- introduces new control-surface concepts for users to learn
- needs careful UX to avoid branch confusion

## Recommendation

Quenda should adopt Host-level session branching as a reusable project
context feature.

The first version should be implemented in Quenda's own persistence model,
with optional Git metadata, but not Git as the underlying branch
mechanism.

