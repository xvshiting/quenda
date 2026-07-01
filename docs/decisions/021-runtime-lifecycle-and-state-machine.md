# ADR-021: Runtime Lifecycle and State Machine

## Status

Proposed (2026-06-26)

## Context

Quenda is moving toward a hookable, policy-driven runtime. That direction
requires more than a list of hook interfaces. It also requires a clear
model of:

- which runtime states exist
- which transitions are legal
- which layer owns each transition
- where policies should make decisions

Without that model, several design problems remain underspecified:

- what exactly a termination policy is allowed to stop
- whether a policy stops a run, a tool phase, or the next loop
  iteration
- when tool-call approval is supposed to happen
- when processed tool results are written back to the loop
- where future verification or reflection phases would fit

Today, much of Quenda's lifecycle is implicit in `Run.execute()` and
`Kernel.run()`. The framework needs an explicit runtime state machine so
that hooks, policies, and phase transitions can be designed coherently.

## Decision

Quenda should define its runtime execution model as an explicit state
machine centered on the `Run`.

Recommended principles:

- `Run` is the lifecycle container
- `Runtime` owns phase transitions and policy invocation
- `Kernel` remains a guarded execution engine
- state transitions should be explicit and documented
- policies should be attached to phase boundaries and transitions, not
  scattered as ad-hoc callbacks

## State Machine Overview

The recommended lifecycle has the following core states:

1. `Pending`
2. `Started`
3. `CompressionCheck`
4. `CompressionRunning`
5. `ContextPrepared`
6. `ModelInvoking`
7. `ModelResponded`
8. `ToolPhaseRunning`
9. `ToolBatchCompleted`
10. `LoopDecision`
11. `Completed`
12. `Terminated`
13. `Interrupted`
14. `Failed`

Future optional extension states may include:

- `VerificationRunning`
- `ReflectionRunning`
- `ModelSwitching`

These are not required in the first implementation, but the state
machine should leave room for them.

## Core State Definitions

### 1. `Pending`

The run has been created but has not started execution yet.

### 2. `Started`

The run has accepted a new user message and entered active execution.

This is the state where:

- run metadata becomes active
- start events can be emitted
- session-level mutations for the new run begin

### 3. `CompressionCheck`

Runtime evaluates whether pre-run compression should happen before the
next effective model context is assembled.

This is the natural home for:

- compression stats calculation
- `CompressionPolicy.should_compress()`

### 4. `CompressionRunning`

Runtime is actively executing a compression action.

This state is optional on a given run and is entered only if compression
is needed.

### 5. `ContextPrepared`

Runtime has constructed the effective context for the next model
invocation.

This includes, as applicable:

- system prompt
- summary blocks
- recent messages
- any approved runtime overlays

This is the natural seam for future context-assembly policies.

### 6. `ModelInvoking`

Runtime is invoking the model through Kernel / Provider execution.

This is the active model-call state.

### 7. `ModelResponded`

A model step has completed and produced a `ModelResponse`.

This state exists before the runtime decides what to do next.

The response may contain:

- final content
- tool calls
- a stop reason

### 8. `ToolPhaseRunning`

Runtime is executing the tool batch returned by the most recent model
step.

This state covers the full tool phase, not only one tool call.

It is the natural conceptual seam for:

- tool-call approval
- tool-execution middleware
- per-call result observation

### 9. `ToolBatchCompleted`

The current tool phase has finished producing its full set of tool
results, whether all calls were executed or some were denied or failed.

This is a boundary state before Runtime decides what the next phase
should be.

### 10. `LoopDecision`

Runtime decides which legal state comes next.

This is the most important control state for future policy design.

Typical outgoing transitions are:

- back to `ModelInvoking`
- to `Completed`
- to `Terminated`
- to `Interrupted`
- to `Failed`
- later, possibly to `VerificationRunning`

### 11. `Completed`

The run ended successfully through normal loop completion.

### 12. `Terminated`

The run ended because a runtime policy decided it should stop.

This is distinct from interruption and failure.

### 13. `Interrupted`

The run ended because an external stop signal interrupted it.

### 14. `Failed`

The run ended because of an unrecoverable runtime or execution error.

## Recommended Transition Graph

The recommended default transition flow is:

```text
Pending
  -> Started
  -> CompressionCheck
     -> CompressionRunning
     -> ContextPrepared
  -> ModelInvoking
  -> ModelResponded
     -> Completed
     -> ToolPhaseRunning
  -> ToolBatchCompleted
  -> LoopDecision
     -> ModelInvoking
     -> Completed
     -> Terminated
     -> Interrupted
     -> Failed
```

Expanded view:

```text
Pending
  -> Started

Started
  -> CompressionCheck

CompressionCheck
  -> CompressionRunning
  -> ContextPrepared

CompressionRunning
  -> ContextPrepared
  -> Failed

ContextPrepared
  -> ModelInvoking

ModelInvoking
  -> ModelResponded
  -> Interrupted
  -> Failed

ModelResponded
  -> Completed
  -> ToolPhaseRunning
  -> Failed

ToolPhaseRunning
  -> ToolBatchCompleted
  -> Interrupted
  -> Failed

ToolBatchCompleted
  -> LoopDecision

LoopDecision
  -> ModelInvoking
  -> Completed
  -> Terminated
  -> Interrupted
  -> Failed
```

## Transition Ownership

### Host

Host owns:

- run creation inputs
- storage and persistence surfaces
- pre-run configuration and environment wiring

Host does not own the internal loop transitions.

### Runtime

Runtime owns:

- lifecycle state transitions
- policy invocation
- loop decision logic
- session mutation timing
- event emission

This is the correct layer for:

- termination policy
- compression policy
- future context assembly policy
- future verification policy

### Kernel

Kernel owns:

- model invocation mechanics
- tool execution mechanics
- hard execution guards

Kernel should not own high-level policy transitions.

It should remain the execution engine that Runtime drives.

## Hook and Policy Placement

This state machine implies the following placements.

### `CompressionPolicy`

State boundary:

- `CompressionCheck`

Decision:

- whether to enter `CompressionRunning` or continue directly to
  `ContextPrepared`

### `TraceSink`

Placement:

- observer across state transitions and emitted events

This seam does not choose transitions. It observes them.

### `TerminationPolicy`

State boundary:

- `LoopDecision`

Role:

- determine whether the run should move to `Terminated`
- not whether Kernel's hard guard should exist

### `ToolSelectionPolicy`

Target state boundary:

- between `ModelResponded` and `ToolPhaseRunning`

Important note:

- current code does not fully expose this seam yet
- this is the target architectural location

### `ToolResultProcessingPolicy`

Target state boundary:

- between `ToolPhaseRunning` and `ToolBatchCompleted`

More precisely:

- after raw tool execution completes
- before processed observations are written back into the agent loop

### Future `VerificationPolicy`

Suggested boundary:

- between `ModelResponded` or `ToolBatchCompleted` and `LoopDecision`

This leaves room for a future `VerificationRunning` state.

## What Termination Means

This ADR makes a key distinction:

- `Completed` means normal successful completion
- `Terminated` means a policy stopped the run
- `Interrupted` means an external signal stopped the run
- `Failed` means an unrecoverable error stopped the run

This matters because a "termination policy" should not be treated as a
generic "stop everything somehow" callback.

A termination policy decides a specific transition:

- `LoopDecision -> Terminated`

It does not define:

- user interruption behavior
- kernel hard limits
- tool-call denial semantics

## What Tool-Phase Control Means

Tool-related policies need more than a generic stop/continue flag.

The state machine should support reasoning at three different levels:

- the model step that requested a tool batch
- the tool phase executing that batch
- the loop decision after the tool phase completes

This is why future policies may need access to:

- the current tool-call batch
- the results of the current batch
- recent tool-phase history

That information belongs in transition-state or loop-decision inputs,
not only in budget-style counters.

## Consequences

### Positive

- clarifies what each hook is actually allowed to influence
- makes outcome semantics explicit
- gives Runtime a clear ownership boundary
- makes future policy design more coherent
- prepares the system for richer loop control without inflating Kernel

### Negative

- some current implementation boundaries do not yet match the target
  state machine
- tool-related seams will require Runtime / Kernel refactoring to align
  with this model

## Relationship to Existing Decisions

This ADR builds directly on:

- `ADR-015` for compression policy structure
- `ADR-017` for keeping higher-order orchestration out of core
- `ADR-019` for prioritizing strategy hooks over rich UI
- `ADR-020` for stable runtime terminology

## Recommendation

Quenda should treat this lifecycle state machine as the canonical
architectural model for future hook and policy work.

In particular:

- Runtime should own transition logic
- policies should be attached to explicit phase boundaries
- Kernel should remain a guarded execution engine
- future hook design should follow legal transitions in this state
  machine rather than ad-hoc insertion points
