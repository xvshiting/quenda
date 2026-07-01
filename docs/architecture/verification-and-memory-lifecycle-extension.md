# Verification and Memory Lifecycle Extension

## Status

Draft (2026-06-29)

## Purpose

This document defines the next lifecycle expansion after the current
linear `Run -> Model -> Tool -> LoopDecision` runtime.

Based on the current research-support analysis, the two highest-value
extensions are:

- `Verification / Reflection` phases
- `Memory Read / Write / Compaction` phases

The goal of this document is to show how these phases fit into Quenda's
existing runtime state machine without collapsing the current layering.

This document answers:

- what new lifecycle states should be added first
- where those states should sit in the current execution graph
- which transitions should become legal
- which future hooks and policies naturally attach to those boundaries

## Why These Two First

These two phase families are the best next step because they are both:

- highly relevant to current agent research
- conceptually compatible with Quenda's existing runtime design

They also improve support for a broad range of methods without forcing
Quenda to adopt search or branching immediately.

### Verification / Reflection

This phase family improves support for:

- external verification
- self-critique with structured boundaries
- tool-interactive critique
- repair loops

Representative work:

- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)

### Memory Read / Write / Compaction

This phase family improves support for:

- long-running memory-managed agents
- episodic and semantic retrieval
- selective writeback
- memory trust and filtering
- compaction and retention strategies

Representative work:

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- recent memory management and memory poisoning studies

## Current Baseline

The current lifecycle from
[ADR-021](/Users/xushiting/Workspace/quenda/docs/decisions/021-runtime-lifecycle-and-state-machine.md)
can be simplified as:

```text
Pending
  -> Started
  -> CompressionCheck
  -> ContextPrepared
  -> ModelInvoking
  -> ModelResponded
  -> ToolPhaseRunning
  -> ToolBatchCompleted
  -> LoopDecision
  -> Completed / Terminated / Interrupted / Failed
```

This baseline already supports:

- ReAct-style linear loops
- budget-aware stopping
- trace export
- compression

But it does not yet give verification or memory a first-class phase
boundary.

## Proposed New State Families

The next extension should introduce five new runtime states:

- `MemoryReadRunning`
- `MemoryWriteRunning`
- `MemoryCompactionRunning`
- `VerificationRunning`
- `ReflectionRunning`

Not all five need immediate implementation. The important decision is to
reserve them explicitly in the lifecycle model.

## State Definitions

### 1. `MemoryReadRunning`

Runtime is actively retrieving or selecting memory candidates before the
next effective model context is assembled.

This phase is the natural home for:

- memory retrieval policies
- retrieval ranking
- trust-aware filtering
- memory truncation before prompt assembly

### 2. `MemoryWriteRunning`

Runtime is deciding what information from the just-completed run phase
should be persisted into long-term memory or memory-like stores.

This phase is the natural home for:

- write policies
- memory deduplication
- selective persistence
- retention metadata assignment

### 3. `MemoryCompactionRunning`

Runtime is compacting existing memory structures.

This phase is similar in spirit to the existing compression seam, but
should remain distinct:

- message compression is conversation-history management
- memory compaction is memory-store management

They may share some implementation patterns, but should not be treated
as identical concepts.

### 4. `VerificationRunning`

Runtime is evaluating a candidate result or state transition before
deciding the next loop action.

This phase is the natural home for:

- external verifier checks
- rule-based validation
- post-tool validation
- post-model validation

### 5. `ReflectionRunning`

Runtime is generating or applying reflective feedback about previous
execution.

This phase is related to verification but distinct:

- verification asks "is this acceptable / correct enough?"
- reflection asks "what should change next?"

In some agents, these may be merged. In others, they should remain
separate.

## Recommended Transition Additions

The following transitions should be added conceptually.

## Memory transitions

### Before context assembly

Recommended path:

```text
Started
  -> CompressionCheck
  -> MemoryReadRunning
  -> ContextPrepared
```

Meaning:

- compression and memory retrieval happen before final context assembly
- Runtime should be able to retrieve memory after deciding the current
  message/context budget shape

### After tool or model progress

Recommended path:

```text
ToolBatchCompleted
  -> MemoryWriteRunning
  -> LoopDecision
```

and optionally:

```text
Completed
  -> MemoryWriteRunning
```

Meaning:

- some agents will want to write memory after each meaningful tool/model
  phase
- others may only want to write memory once the run completes

The lifecycle should support both.

### Periodic memory maintenance

Recommended path:

```text
CompressionCheck
  -> MemoryCompactionRunning
```

or, in future, a separate maintenance-trigger path outside a user run.

## Verification / reflection transitions

### After model response

Recommended path:

```text
ModelResponded
  -> VerificationRunning
  -> LoopDecision
```

Use case:

- verify whether a model-only answer is acceptable
- verify whether returned tool calls are safe or coherent

### After tool batch completion

Recommended path:

```text
ToolBatchCompleted
  -> VerificationRunning
  -> LoopDecision
```

Use case:

- evaluate whether current tool evidence is enough
- decide whether to continue, re-prompt, or stop

### Reflection path

Recommended path:

```text
VerificationRunning
  -> ReflectionRunning
  -> LoopDecision
```

Meaning:

- verification may succeed without reflection
- reflection may be triggered only when the verifier or policy decides
  it is useful

## Expanded State Graph

The expanded lifecycle can be summarized as:

```text
Pending
  -> Started
  -> CompressionCheck
     -> CompressionRunning
     -> MemoryCompactionRunning
     -> MemoryReadRunning
  -> ContextPrepared
  -> ModelInvoking
  -> ModelResponded
     -> VerificationRunning
     -> Completed
     -> ToolPhaseRunning
  -> ToolBatchCompleted
     -> MemoryWriteRunning
     -> VerificationRunning
  -> ReflectionRunning
  -> LoopDecision
     -> ModelInvoking
     -> Completed
     -> Terminated
     -> Interrupted
     -> Failed
```

This should still be understood as a runtime state machine, not a
promise that every state will occur on every run.

## State Roles and Hook Placement

The benefit of these new states is that they give future hooks precise
phase boundaries.

### `MemoryReadRunning`

Natural hooks:

- `MemoryRetrievalPolicy`
- memory ranking policy
- trust filter policy

### `MemoryWriteRunning`

Natural hooks:

- `MemoryWritePolicy`
- deduplication policy
- selective persistence policy

### `MemoryCompactionRunning`

Natural hooks:

- `MemoryCompactionPolicy`

### `VerificationRunning`

Natural hooks:

- `VerificationPolicy`
- external verifier integration
- structured correctness checks

### `ReflectionRunning`

Natural hooks:

- `ReflectionPolicy`
- critique generation
- repair guidance generation

## Layer Ownership

These new phases should remain Runtime-owned.

### Runtime

Runtime should own:

- entering and exiting these states
- invoking policies attached to them
- deciding which next transition is legal

### Host

Host may own:

- memory storage adapters
- verifier package loading
- configuration and persistence wiring

### Kernel

Kernel should not directly own:

- verification logic
- reflection logic
- memory policy logic

Kernel remains the engine for:

- model invocation
- tool execution
- hard execution guards

This preserves the same architectural split already established in
earlier ADRs.

## Why Verification and Reflection Should Be Separate

It may be tempting to collapse `VerificationRunning` and
`ReflectionRunning` into one state, but they serve different purposes.

### Verification

Verification answers:

- is this output acceptable
- is this evidence sufficient
- is this state transition allowed

### Reflection

Reflection answers:

- what should be changed next
- what pattern of failure just happened
- what corrective strategy should be attempted

Some agents may implement both phases with one component. But the
lifecycle should not force them to be identical.

## Why Memory Read and Write Should Be Explicit

If memory stays implicit inside context assembly or persistence, several
important research questions become harder to study:

- comparing retrieval strategies
- comparing writeback strategies
- studying trust or poisoning defenses
- separating context compression from memory maintenance

By naming `MemoryReadRunning` and `MemoryWriteRunning` explicitly, Quenda
creates a clean place for experimentation without overloading unrelated
phases.

## What This Enables

These additions would allow Quenda to support the following more cleanly:

- verifier-guided stopping
- post-tool evidence evaluation
- reflection-triggered retry
- selective memory writeback
- long-running memory-managed agent experiments
- comparison between verification-aware and verification-free loops

This is a meaningful step toward better support for current research
without requiring immediate branching or search semantics.

## What This Still Does Not Solve

Even with these phase additions, Quenda would still not fully support:

- branch-native search execution
- candidate tree evaluation
- rollback and branch pruning
- native multi-agent orchestration

Those still require future lifecycle expansion.

## Recommended Implementation Order

Suggested order:

1. reserve these states in architecture and terminology
2. implement `VerificationRunning` first
3. implement `MemoryReadRunning` and `MemoryWriteRunning`
4. separate message compression from broader memory compaction semantics
5. add `ReflectionRunning` after verification semantics stabilize

This keeps the expansion incremental and reduces the risk of premature
overgeneralization.

## Final Recommendation

The next lifecycle expansion should focus first on:

- `VerificationRunning`
- `MemoryReadRunning`
- `MemoryWriteRunning`

and should keep `MemoryCompactionRunning` and `ReflectionRunning` as
explicit follow-on targets.

This is the highest-leverage extension for improving Quenda's support of
current agent research while preserving the current Runtime-centered
state-machine architecture.
