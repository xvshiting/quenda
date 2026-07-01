# Tool Phase Runtime Refactor Breakdown

## Status

Draft (2026-06-29)

## Purpose

This document turns
[tool-phase-runtime-ownership-and-policy-control.md](/Users/xushiting/Workspace/quenda/docs/architecture/tool-phase-runtime-ownership-and-policy-control.md)
into an implementation-oriented breakdown.

It answers:

- how to stage the refactor safely
- what each phase should deliver
- what should remain stable across phases
- which risks to watch at each step

The goal is to make the tool-phase ownership shift tractable without
forcing one large rewrite.

## Summary

Recommended delivery order:

1. extract Kernel execution primitives
2. move tool-phase sequencing into Runtime
3. integrate `ToolSelectionPolicy`
4. integrate `ToolResultProcessingPolicy`
5. improve trace and event surfaces
6. add higher-level binding and configuration

Recommended project rule:

- do not expose new user-facing configuration for tool policies until
  phases 1 through 4 are complete

## Guiding Constraints

The refactor should preserve these invariants throughout.

### 1. Default behavior must remain equivalent

Without custom policies, the runtime should still behave like today's
default model-tool loop.

### 2. Public policy concepts should remain stable

These concepts should survive the refactor:

- `ToolSelectionPolicy`
- `ToolResultProcessingPolicy`
- requested tool batch
- raw vs processed tool result

### 3. Kernel should shrink in control ownership, not disappear

Kernel should remain the execution engine for:

- model invocation
- tool execution
- hard guards

### 4. Runtime should become the lifecycle owner

Runtime should own:

- when a tool phase begins
- what executes
- what gets written back
- when the next loop step happens

## Phase 0: Preconditions Review

This is not a code change phase. It is a review gate.

Before implementation begins, the team should confirm:

- `ADR-020`, `ADR-021`, and `ADR-022` are the agreed vocabulary and
  boundary
- the target design in
  [tool-phase-runtime-ownership-and-policy-control.md](/Users/xushiting/Workspace/quenda/docs/architecture/tool-phase-runtime-ownership-and-policy-control.md)
  is accepted as the implementation direction
- `Option B` is the chosen approach:
  Runtime becomes explicit loop owner

Deliverable:

- explicit team agreement on target ownership

Risk if skipped:

- implementation may drift back toward callback-based mixed ownership

## Phase 1: Extract Kernel Primitives

### Goal

Separate execution primitives from the current monolithic
`Kernel.run(messages)` loop.

### What changes

Kernel should expose smaller operations for Runtime to call directly.

Target capability shape:

- invoke model once
- execute one tool call
- optionally execute a list of tool calls sequentially

The important shift is:

- Runtime should no longer need to enter a generator that owns the whole
  loop

### Expected result

By the end of this phase, Runtime can assemble its own loop using
Kernel-backed primitives.

### What should remain unchanged

- model response normalization
- tool lookup and execution mechanics
- existing hard guards where still relevant

### Risks

- duplicating logic between old and new Kernel entry points
- leaking Runtime-specific semantics into Kernel

### Review checklist

- does Kernel still avoid policy decisions
- can Runtime invoke model and tool execution independently
- is the old `Kernel.run()` path either preserved temporarily or clearly
  deprecated

## Phase 2: Move Tool-Phase Sequencing Into Runtime

### Goal

Make Runtime the explicit owner of:

- model response handling
- tool phase entry
- tool execution sequencing
- writeback timing
- next-step loop transitions

### What changes

Runtime should drive the loop directly:

1. build context
2. invoke model
3. inspect response
4. decide complete vs tool phase
5. execute tool phase
6. write back tool phase results
7. continue or stop

At this phase, Runtime may still preserve current default behavior:

- approve all tools
- pass through all tool results unchanged

### Expected result

Tool phase becomes Runtime-owned even before custom policies are wired
in.

### What should remain unchanged

- external default user experience
- message schema
- assistant tool-call message + user tool-result message writeback model

### Risks

- regressions in loop semantics
- inconsistent event emission between model and tool steps
- accidental double writeback

### Review checklist

- does Runtime decide when the tool phase starts
- does Runtime own message writeback after tool execution
- does Kernel stop appending tool results to messages internally

## Phase 3: Integrate `ToolSelectionPolicy`

### Goal

Turn tool-call approval into a real Runtime seam.

### What changes

After a `ModelResponse` with tool calls:

1. Runtime builds `ToolSelectionRequest`
2. Runtime calls `ToolSelectionPolicy`
3. Runtime partitions approved vs rejected calls
4. Runtime executes only approved calls
5. Runtime preserves rejection information

### Required semantics

Phase-1 semantics should be:

- approval or rejection only
- no argument rewriting
- no model-visible tool-list filtering
- request-order preservation

### Expected result

`ToolSelectionPolicy` becomes genuinely operational instead of
documentation-only.

### What should remain unchanged

- `AllowAllToolSelectionPolicy` should preserve default behavior
- the model still sees the same available tool set at invocation time

### Risks

- rejected calls disappearing silently
- the assistant writeback reflecting only approved calls instead of the
  original requested batch
- policy and tool registry concepts getting conflated

### Review checklist

- are rejected calls represented explicitly
- does Runtime preserve the original requested tool batch in writeback
- can the run proceed when all calls are rejected

## Phase 4: Integrate `ToolResultProcessingPolicy`

### Goal

Turn tool-result shaping into a real Runtime seam.

### What changes

For each approved tool call:

1. Kernel returns raw execution output
2. Runtime builds `ToolResultEnvelope`
3. Runtime applies `ToolResultProcessingPolicy`
4. Runtime writes back processed result
5. Runtime keeps raw result available for trace/debugging

### Required semantics

This phase should enforce:

- raw result remains observable
- processed result is loop-facing
- processing failure falls back safely

### Expected result

Tool-result shaping becomes controllable without compromising execution
truth.

### What should remain unchanged

- `PassthroughToolResultProcessingPolicy` preserves current behavior

### Risks

- raw and processed data getting mixed together
- loss of debugging truth after truncation or redaction
- policy failure breaking run execution

### Review checklist

- is raw result still available after processing
- is processed result the only content written back into loop messages
- does failure in processing fall back to passthrough

## Phase 5: Tighten Trace And Event Surfaces

### Goal

Ensure observability matches the new Runtime-owned tool phase.

### What changes

The team should evaluate whether current events are sufficient to
capture:

- requested tool batch
- approved vs rejected calls
- raw tool result
- processed tool result
- tool-phase completion outcome

This may require:

- new runtime events
- richer payloads on existing events
- trace-only structured records without user-facing event impact

### Expected result

Trace becomes adequate for:

- debugging
- replay
- policy evaluation
- research comparison

### What should remain unchanged

- trace remains observer-only
- trace failures must not crash the run

### Risks

- raw/processed divergence becoming invisible
- denial semantics becoming hard to audit
- event model becoming overloaded with UI concerns

### Review checklist

- can trace explain what the model asked for vs what actually happened
- can trace distinguish denial from execution failure
- can trace show raw vs processed results

## Phase 6: Add Higher-Level Binding

### Goal

Expose the now-stable seams through normal framework binding paths.

### Recommended order inside this phase

1. agent-level / session-level defaults
2. run-level overrides
3. config-driven loading

### Why this order

Because the natural conceptual ownership is:

- agent/session defines the normal strategy
- run-level is an override
- config is a convenience layer over programmatic binding

### Expected result

Users can smoothly swap in custom policies without modifying core code.

### What should remain unchanged

- programmatic registration should stay the primary reference API
- config loading should reuse the same policy contracts

### Risks

- freezing unstable config schema too early
- creating multiple inconsistent binding paths

### Review checklist

- can a user replace a tool policy with a small object
- do run-level overrides cleanly supersede session defaults
- does config loading map to the same runtime seam as programmatic
  binding

## Recommended PR Breakdown

One practical way to map the phases to pull requests is:

1. `PR-1`: extract Kernel single-step primitives
2. `PR-2`: Runtime-owned loop skeleton with default tool phase
3. `PR-3`: operational `ToolSelectionPolicy` with denial semantics
4. `PR-4`: operational `ToolResultProcessingPolicy` with raw/processed
   split
5. `PR-5`: trace/event enrichment for tool phase
6. `PR-6`: agent/session/config policy binding

This keeps each review focused on one ownership shift at a time.

## Testing Strategy By Phase

### Phases 1-2

Focus on execution equivalence:

- same completion behavior
- same basic tool loop behavior
- no duplicate or missing writeback

### Phase 3

Focus on gating correctness:

- allow-all matches current behavior
- denylist blocks execution but preserves visibility
- all-rejected batches still produce a valid next-step context

### Phase 4

Focus on result-shaping correctness:

- raw and processed outputs diverge correctly
- passthrough matches current behavior
- truncation / line-limiting affect loop writeback only

### Phase 5

Focus on observability:

- trace distinguishes requested, approved, rejected, executed, and
  written-back artifacts

### Phase 6

Focus on usability:

- policy binding works at the intended scope
- configuration maps correctly onto programmatic behavior

## Open Questions To Keep Explicit

These do not block the refactor, but they should stay visible.

### 1. Should all-rejected tool batches increment `tool_round_count`

Recommended initial answer:

- yes, if the runtime entered a tool phase and wrote back denial results

Reason:

- the model attempted a tool-use round, even though no tool executed

### 2. Should denied-call outputs use `ToolResult` or a separate type

Recommended initial answer:

- use synthetic `ToolResult`-shaped loop payloads in phase 1

Reason:

- it minimizes schema churn while keeping denials visible

### 3. Should `TerminationPolicy` inspect current tool-batch state

Recommended initial answer:

- not required for the first unlock, but plan for it

Reason:

- richer termination inputs are valuable, but should not delay ownership
  refactor

### 4. Should tool processing operate on each result or on the whole batch

Recommended initial answer:

- per-result first
- batch-level processing later if needed

Reason:

- per-result processing fits the current policy shape and is easier to
  land safely

## Definition Of Done

The refactor should be considered complete when:

- Runtime, not Kernel, owns tool-phase sequencing
- Runtime, not Kernel, owns tool-result writeback
- `ToolSelectionPolicy` is operational
- `ToolResultProcessingPolicy` is operational
- default behavior remains simple and equivalent
- trace can distinguish requested / executed / written-back artifacts

At that point, the tool seams stop being aspirational and become real
framework extension points.
