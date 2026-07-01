# ADR-023: Runtime Owns Tool Phase and Policy Control

## Status

Proposed (2026-06-29)

## Context

Kora has already established the following architectural direction:

- `ADR-019` prioritizes strategy hooks over rich UI
- `ADR-020` defines runtime terminology, including tool call, tool
  batch, and tool phase
- `ADR-021` defines a runtime lifecycle centered on `Run`, with
  `ToolPhaseRunning -> ToolBatchCompleted -> LoopDecision`
- `ADR-022` keeps core minimal while pushing strategy into policies and
  extensions

Kora also already defines the target policy contracts for:

- `ToolSelectionPolicy`
- `ToolResultProcessingPolicy`

However, the current execution shape does not yet make those seams real.

Today, the effective flow is:

```text
Runtime
  -> builds messages
  -> starts Kernel.run(messages)

Kernel
  -> invokes model
  -> yields ModelResponse
  -> executes returned tool calls itself
  -> appends assistant tool-call message
  -> appends raw tool-result message
  -> continues next iteration
```

This means Runtime can observe tool steps, but does not fully own:

- tool-call approval before execution
- raw vs processed tool-result handling
- message writeback timing for tool results
- tool-phase completion semantics

As a result:

- `ToolSelectionPolicy` is only a target contract
- `ToolResultProcessingPolicy` is only a target contract
- tool denial, partial execution, and phase-level stopping semantics
  remain underspecified

Kora needs a clear ownership rule before these seams can become real.

## Decision

Kora should make **Runtime the owner of the tool phase**.

This means Runtime, not Kernel, should own:

- entry into `ToolPhaseRunning`
- tool-batch acceptance
- invocation of `ToolSelectionPolicy`
- sequencing of approved tool calls
- handling of rejected tool calls
- invocation of `ToolResultProcessingPolicy`
- tool-result writeback into loop messages
- transition to `ToolBatchCompleted`
- next `LoopDecision`

Kernel should remain the execution engine for:

- model invocation mechanics
- tool registry lookup
- individual tool execution mechanics
- hard guards and execution invariants

In short:

- **Runtime owns control flow**
- **Kernel owns execution primitives**

## Why This Boundary

### 1. It makes tool policies real

`ToolSelectionPolicy` and `ToolResultProcessingPolicy` only become true
framework seams if Runtime owns the decision points where they act.

### 2. It aligns with the lifecycle model

`ADR-021` already treats the tool phase as a Runtime lifecycle boundary.
This ADR makes that ownership operational rather than conceptual.

### 3. It preserves a small Kernel

Kernel should remain a reusable execution engine, not absorb strategy
semantics such as:

- which calls are approved
- how denials are represented
- which result form goes back into the loop

### 4. It enables later phases cleanly

Future verification, reflection, memory write, and richer termination
behavior all benefit from a clean post-tool Runtime boundary.

## Tool-Phase Semantics

The Runtime-owned tool phase should follow this model:

1. Runtime receives a `ModelResponse` with a requested tool batch
2. Runtime decides to enter `ToolPhaseRunning`
3. Runtime constructs `ToolSelectionRequest`
4. Runtime invokes `ToolSelectionPolicy`
5. Runtime executes approved calls in order
6. Runtime preserves explicit rejection information for rejected calls
7. Runtime processes raw tool results through
   `ToolResultProcessingPolicy`
8. Runtime writes back assistant tool-call and loop-facing tool-result
   messages
9. Runtime transitions to `ToolBatchCompleted`
10. Runtime makes the next `LoopDecision`

## Required Phase-1 Rules

The first implementation should follow these rules.

### 1. Preserve requested tool-call writeback

The assistant-side writeback should reflect the original requested tool
batch, not only the approved subset.

Reason:

- the model should be able to see what it asked for
- trace and replay stay faithful to the model response
- denials remain interpretable

### 2. Rejected calls must remain explicit

Rejected tool calls should not disappear silently.

Phase 1 should represent them as synthetic loop-visible denial results
with an explanation.

### 3. Raw and processed results must remain distinct

Runtime should preserve:

- raw tool results for trace and debugging
- processed tool results for loop writeback

This distinction should be explicit in implementation and observability.

### 4. Default behavior must remain simple

Without custom policies:

- all tools are approved
- tool results are passed through unchanged

This preserves the current simple default runtime behavior.

### 5. Policy failures should not make the runtime brittle

If result processing fails for one tool result, Runtime should fall back
to safe passthrough behavior for that result rather than discarding raw
execution truth.

## Termination, Interruption, and Failure

This ADR also fixes the intended meaning of stopping during tool phase.

### Termination

If a Runtime `TerminationPolicy` decides the run should stop:

- before tool execution starts, the run transitions to `Terminated`
- during a tool phase, remaining tool calls are not executed and the run
  transitions to `Terminated`

Phase 1 should not continue back to the model with partial tool results
after a run-level termination decision.

### Interruption

If the user interrupts during tool phase:

- remaining tool calls are not executed
- the run transitions to `Interrupted`

### Failure

If an unrecoverable runtime or execution error occurs:

- the run transitions to `Failed`

### Denial

Tool-call denial is not itself termination.

If Runtime writes back denial results as part of a completed tool phase,
the next step may still proceed through normal `LoopDecision`.

## Non-Goals

This ADR does not require phase 1 to support:

- tool argument rewriting
- model-facing tool routing
- parallel tool execution
- branching or search semantics
- batch-level result processing
- reflection or verification policy implementation

Those may be added later without changing this ownership decision.

## Recommended Implementation Direction

Kora should prefer a refactor where Runtime becomes the explicit owner
of the execution loop rather than adding callback seams inside
`Kernel.run()`.

Reason:

- ownership becomes clearer
- policy invocation stays Runtime-owned
- future lifecycle phases fit more naturally
- callback-based mixed ownership is avoided

## Implementation Order

Recommended order:

1. expose smaller Kernel execution primitives
2. move tool-phase sequencing and writeback into Runtime
3. integrate `ToolSelectionPolicy`
4. integrate `ToolResultProcessingPolicy`
5. enrich trace or event surfaces if needed
6. expose stable binding through agent/session/config layers

Supporting breakdown:

- [tool-phase-runtime-refactor-breakdown.md](/Users/xushiting/Workspace/kora/docs/architecture/tool-phase-runtime-refactor-breakdown.md)

Supporting design draft:

- [tool-phase-runtime-ownership-and-policy-control.md](/Users/xushiting/Workspace/kora/docs/architecture/tool-phase-runtime-ownership-and-policy-control.md)

## Consequences

### Positive

- makes tool policy seams real rather than aspirational
- aligns Runtime ownership with the lifecycle model
- keeps Kernel focused on execution primitives
- creates a clean boundary for verification, reflection, and memory
  extensions
- preserves simple default behavior while enabling richer policy
  strategies

### Negative

- requires a meaningful Runtime / Kernel refactor
- may require follow-on trace or event-surface changes
- increases the explicit control responsibilities of Runtime

### Risks

- if ownership is only partially moved, semantics may become more
  confusing rather than less
- if trace does not preserve raw vs processed distinctions, debugging
  quality may regress
- if config is added before the seam is operational, unstable interfaces
  may leak into user-facing APIs

## Decision Test For Future Changes

Future proposals involving tool use should be checked against this rule:

- if the proposal changes what gets executed, what gets written back, or
  what transition happens after a tool batch, Runtime should own it
- if the proposal changes only how one tool call is mechanically
  executed, Kernel may own it

This keeps the control boundary durable as Kora grows.
