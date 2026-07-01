# Tool Phase Runtime Ownership and Policy Control

## Status

Draft (2026-06-29)

## Purpose

This document defines the next runtime refactor needed to make
`ToolSelectionPolicy` and `ToolResultProcessingPolicy` real execution
seams rather than target contracts.

It focuses on one architectural shift:

- **Runtime must own the tool phase**

That means Runtime, not Kernel, should own:

- tool-batch acceptance
- tool-call approval
- per-call execution sequencing
- raw vs processed result handling
- message writeback timing
- tool-phase completion and next loop decision

This document is implementation-ready in intent, but it does not
prescribe exact class names or file boundaries.

## Why This Refactor Matters

Today, Quenda already has:

- a stable lifecycle vocabulary in
  [ADR-020](/Users/xushiting/Workspace/quenda/docs/decisions/020-runtime-terminology-and-execution-units.md)
- a runtime state machine in
  [ADR-021](/Users/xushiting/Workspace/quenda/docs/decisions/021-runtime-lifecycle-and-state-machine.md)
- target hook contracts for tool policies in
  [hook-interface-drafts.md](/Users/xushiting/Workspace/quenda/docs/architecture/hook-interface-drafts.md)

But the current execution path still gives Kernel ownership of the
critical handoff points needed for tool policies:

- the handoff between model response and tool execution
- the handoff between raw tool result and message writeback

As a result:

- `ToolSelectionPolicy` cannot truly gate execution before tools run
- `ToolResultProcessingPolicy` cannot truly shape results before they
  re-enter the loop
- Runtime cannot cleanly define tool-phase semantics for denial,
  partial execution, or phase-level stopping

If Quenda wants real policy seams instead of interface placeholders, this
ownership boundary has to move.

## Current Ownership Problem

Today the execution flow is effectively:

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
  -> continues next model iteration
```

This creates four problems.

### 1. Runtime only observes, but does not control

Runtime can see `KernelStep` events, but it does not own the decision
point before tool execution starts.

### 2. Tool result shaping is too late

By the time Runtime observes a `ToolResult`, Kernel has already decided
that raw output is the material to write back into the loop.

### 3. Tool-phase semantics stay implicit

Because Kernel internally owns execution and writeback, Quenda has no
clear place to define:

- denied tool calls
- synthetic tool denial results
- partial tool-batch completion
- stop semantics inside a tool phase

### 4. Policy ownership becomes misleading

The current policy interfaces suggest Runtime-owned control, but the
current code path still makes Kernel the effective owner of the phase.

## Design Goals

This refactor should achieve the following.

### 1. Make tool policies real

`ToolSelectionPolicy` and `ToolResultProcessingPolicy` should become
actual execution seams.

### 2. Keep Kernel small

Kernel should still own execution mechanics, not strategy semantics.

### 3. Preserve simple default behavior

If no custom policies are configured, behavior should remain equivalent
to today's default loop.

### 4. Keep the model-tool loop legible

The refactor should make lifecycle and state transitions clearer, not
more obscure.

### 5. Support future verification and memory phases

The tool phase should become a clean runtime boundary that later phases
can attach to.

## Non-Goals

This refactor should not attempt to solve everything at once.

Out of scope for phase 1:

- model-facing tool routing
- tool argument rewriting
- planner semantics
- parallel tool execution
- search / branching behavior
- reflection / verification policy implementation
- partial-batch continuation after a run-level termination decision

Those may come later, but they should not block tool-phase ownership.

## Recommended Boundary

The ownership split should become:

### Runtime owns

- loop transitions
- policy invocation
- tool-batch acceptance
- approved vs rejected partitioning
- per-call sequencing
- raw / processed distinction
- assistant tool-call writeback
- tool-result writeback
- tool-phase completion semantics
- loop decision after tool phase

### Kernel owns

- model invocation mechanics
- tool registry lookup
- individual tool execution mechanics
- execution-time hard guards and invariants

This keeps the boundary aligned with the broader Quenda direction:

- Runtime owns control flow
- Kernel owns execution primitives

## Recommended Tool-Phase Model

Quenda should treat one tool phase as a Runtime-owned interval with the
following internal subphases:

1. tool batch requested
2. tool selection evaluated
3. approved calls executed
4. raw results observed
5. processed results prepared
6. writeback committed
7. tool batch completed
8. loop decision made

These do not all need separate top-level runtime states in phase 1, but
they should be explicit in the design.

## Terminology For This Refactor

This document uses the runtime terms already standardized in `ADR-020`,
plus the following tool-phase-specific terms.

### Requested Tool Batch

The exact ordered list of tool calls returned by one `ModelResponse`.

### Approved Tool Batch

The ordered subset of requested tool calls that Runtime allows to
execute after `ToolSelectionPolicy` runs.

### Rejected Tool Calls

The ordered subset of requested tool calls that Runtime does not allow
to execute, together with a reason.

### Raw Tool Result

The direct execution output returned by the tool layer before any
policy-driven shaping.

### Processed Tool Result

The loop-facing tool result after
`ToolResultProcessingPolicy.process_result()`.

### Writeback Payload

The exact message content Runtime writes back into conversation history
for the next model step.

In the current Quenda model, this remains:

- one assistant message containing requested tool calls
- one user message containing tool results

### Tool Phase Outcome

The final status of one tool phase.

Phase-1 outcomes should be limited to:

- `completed`
- `interrupted`
- `failed`
- `terminated`

## Target Execution Flow

The recommended runtime-owned loop shape is:

```text
ContextPrepared
  -> ModelInvoking
  -> ModelResponded
  -> LoopDecision
     -> Completed
     -> ToolPhaseRunning

ToolPhaseRunning
  -> select tool calls
  -> execute approved calls
  -> process raw results
  -> write back assistant tool-call message
  -> write back tool-result message
  -> ToolBatchCompleted

ToolBatchCompleted
  -> LoopDecision
     -> ModelInvoking
     -> Completed
     -> Terminated
     -> Interrupted
     -> Failed
```

This keeps the public lifecycle from `ADR-021` intact while making the
internal ownership of `ToolPhaseRunning` explicit.

## Recommended Runtime Behavior

### 1. After `ModelResponded`, Runtime decides whether to enter tool phase

If the model response:

- has terminal content and no tool calls: Runtime may complete normally
- has tool calls: Runtime enters `ToolPhaseRunning`

At this boundary, Runtime may also apply `TerminationPolicy` before
allowing tool execution to begin.

That preserves the rule that Runtime owns phase transitions.

### 2. Runtime constructs `ToolSelectionRequest`

Runtime builds the request using:

- requested tool calls
- currently available tools
- run/session/agent identity
- current step counters

Phase 1 should keep this contract small and aligned with the existing
`src/quenda/runtime/tool_policy.py` interface.

### 3. Runtime invokes `ToolSelectionPolicy`

The policy returns:

- approved calls
- rejected calls

Important scope rule:

- policy controls execution approval only
- it does not modify the model-visible tool list
- it does not rewrite tool arguments in phase 1

### 4. Runtime preserves requested tool-call message

Regardless of approvals or rejections, Runtime should preserve the
assistant-side record of what the model requested.

That means the assistant writeback should reflect the original requested
tool batch, not only the approved subset.

Reason:

- the model should be able to see what it asked for
- trace and replay stay faithful to the model response
- denials remain interpretable

### 5. Runtime executes approved calls in order

Phase 1 should preserve the current sequential semantics:

- execute approved calls in request order
- collect one raw result per approved call
- emit step-level observation as each call finishes

Parallel execution can be added later as a separate design.

### 6. Runtime synthesizes loop-visible results for rejected calls

Rejected calls should not disappear silently.

Recommended rule:

- Runtime creates a synthetic error-like tool result for each rejected
  call
- that synthetic result is included in tool-result writeback
- trace should preserve the explicit rejection reason

Example semantic shape:

```text
Tool execution denied: <reason>
```

This makes denial visible to the next model step without pretending the
tool actually ran.

### 7. Runtime processes raw results before writeback

For each approved call:

1. Kernel returns a raw `ToolResult`
2. Runtime converts it into `ToolResultEnvelope`
3. Runtime invokes `ToolResultProcessingPolicy`
4. Runtime builds the loop-facing processed result

This is the core seam unlocked by the refactor.

### 8. Runtime writes back processed tool results

The message writeback order should remain:

1. assistant message containing requested tool calls
2. user message containing loop-facing tool results

But the second message should now contain:

- processed results for approved calls
- synthetic denial results for rejected calls

not blindly the raw execution output.

### 9. Runtime completes the tool phase explicitly

Only after all approved calls are handled, all rejected calls are
represented, and writeback is committed should Runtime transition to
`ToolBatchCompleted`.

That creates a real boundary for:

- termination checks
- verification
- reflection
- memory write
- trace export

## Recommended Treatment Of Raw vs Processed

The system should preserve a strict distinction:

- raw result is for execution truth, debugging, and trace
- processed result is for loop writeback

This rule should be visible in data flow, not just in comments.

### Required invariant

Processing policy must never erase the existence of raw execution data.

### Recommended implementation rule

Runtime should keep both representations available until the tool phase
ends:

- `raw_result`
- `processed_result`

This is especially important for:

- truncation
- redaction
- summarization
- future verification

## Recommended Treatment Of Errors And Denials

Quenda should distinguish three cases clearly.

### 1. Rejected tool call

- the tool did not run
- Runtime supplies a synthetic denial result to the loop
- trace records the rejection reason explicitly

### 2. Tool execution failure

- the tool was approved and attempted
- Kernel returns or Runtime synthesizes an error `ToolResult`
- that result may still be processed before writeback

### 3. Processing failure

- raw execution succeeded or failed
- result processing policy itself errors

Recommended phase-1 rule:

- processing failure should not discard the raw result
- Runtime should fall back to passthrough behavior for that result
- optional diagnostics may be recorded to trace

This matches the broader Quenda principle that observers and optional
policy logic should not make the runtime brittle.

## Termination And Interruption Semantics

This area needs a crisp rule set.

### Run-level termination

If `TerminationPolicy` decides to stop:

- before tool phase starts: Runtime transitions to `Terminated`
- after a tool execution step: Runtime stops the remaining batch and
  transitions to `Terminated`

Phase 1 should **not** continue back to the model with partial tool
results after a run-level termination decision.

Reason:

- it keeps `Termination` distinct from normal loop continuation
- it avoids ambiguous half-stopped semantics

### Interruption

If the user interrupts during tool phase:

- Runtime stops remaining execution as soon as possible
- run transitions to `Interrupted`
- remaining tool calls in the batch are not executed

### Failure

If an unrecoverable runtime error occurs:

- Runtime transitions to `Failed`
- the tool phase is considered aborted

### Denial is not termination

Rejecting one or more tool calls does not itself terminate the run.

If at least one approved or synthetic result is written back, Runtime
may continue to the next model step through normal `LoopDecision`.

## Legal Phase-1 Cases

The following cases should be considered explicitly supported.

### Case A: all calls approved and all succeed

- execute all calls
- process results
- write back processed results
- continue to `LoopDecision`

### Case B: some calls rejected, others approved

- execute approved calls only
- synthesize denial results for rejected calls
- write back both approved-result outputs and denial outputs
- continue to `LoopDecision`

### Case C: all calls rejected

- no real tool executes
- Runtime still writes back denial results
- continue to `LoopDecision`

This is important because the model may recover by choosing a different
tool or strategy on the next step.

### Case D: approved call fails

- capture error result
- optionally process that result
- write back the error result
- continue unless a run-level termination or unrecoverable failure
  occurs

### Case E: run terminates mid-batch

- stop executing remaining calls
- end run as `Terminated`
- do not continue to next model step

## Recommended Contract Stability

The existing policy names and general contract shapes should remain:

- `ToolSelectionPolicy`
- `ToolResultProcessingPolicy`

That continuity is valuable because the current interfaces already
reflect the intended ownership model.

The refactor should therefore aim to:

- preserve the public concepts
- change runtime ownership and data flow underneath them

Possible future expansions can be added later without blocking phase 1,
such as:

- richer tool history in `ToolSelectionRequest`
- policy composition helpers
- explicit batch-level result objects
- verifier access to raw and processed outputs together

## Recommended Implementation Direction

There are two broad ways to unlock the seam.

### Option A: callback seam inside `Kernel.run()`

Kernel could keep the main loop, but call back into Runtime before:

- tool execution
- message writeback

This is possible, but not recommended.

Reason:

- it keeps Runtime control indirect
- ownership stays blurry
- callbacks tend to accumulate phase-coupled complexity

### Option B: Runtime becomes explicit loop owner

Runtime drives:

1. model invocation
2. tool-phase decisions
3. tool execution dispatch
4. writeback
5. next loop decision

Kernel becomes a smaller execution helper for:

- model calls
- tool execution primitives

This is the recommended direction.

Reason:

- ownership becomes obvious
- lifecycle aligns with `ADR-021`
- tool policies become truly Runtime-owned
- future verification and memory phases fit more naturally

## Minimal Refactor Shape

Without prescribing exact code, the minimal target shape should support
the following Runtime-controlled sequence:

```text
messages = build_context(...)

while not done:
    response = invoke_model(messages)
    observe_model_step(response)

    if terminal(response):
        complete_run(...)
        break

    selection = select_tools(response.tool_calls)
    phase_results = []

    for approved_call in selection.approved:
        raw_result = execute_tool(approved_call)
        processed = process_tool_result(raw_result)
        phase_results.append(processed)
        observe_tool_step(raw_result, processed)

        if termination_or_interrupt():
            stop_remaining_calls()
            end_run(...)
            break

    denial_results = synthesize_denials(selection.rejected)
    writeback_tool_phase(
        requested_calls=response.tool_calls,
        loop_results=phase_results + denial_results,
    )
```

The important architectural point is not the exact syntax. It is that
Runtime now owns:

- the sequence
- the policy calls
- the writeback point

## Trace And Event Implications

The current trace surface is usable but may be too narrow once raw and
processed outputs diverge.

Phase-1 unlock does not require a full event redesign, but the design
should leave room for richer trace events such as:

- tool batch requested
- tool call rejected
- tool result processed
- tool phase completed

At minimum, trace must remain able to answer:

- what the model requested
- what actually executed
- what was rejected
- what raw result came back
- what processed result was written into the loop

If the current event model cannot express all of that cleanly, a trace
surface extension should follow soon after the ownership refactor.

## Relationship To Other Design Work

This refactor is the bridge between earlier and later runtime work.

It operationalizes:

- `ADR-019` by prioritizing strategy seams over UI richness
- `ADR-020` by making tool phase and tool batch ownership precise
- `ADR-021` by making `ToolPhaseRunning -> ToolBatchCompleted ->
  LoopDecision` real
- `ADR-022` by keeping strategy in policies rather than hard-coding it
  in core flow

It also enables future work documented in:

- [verification-and-memory-lifecycle-extension.md](/Users/xushiting/Workspace/quenda/docs/architecture/verification-and-memory-lifecycle-extension.md)

because verification, reflection, and memory write need a clean
post-tool boundary.

## Recommended Implementation Order

The implementation sequence should be:

1. move tool-phase sequencing ownership to Runtime
2. stop Kernel from owning tool-result writeback
3. integrate `ToolSelectionPolicy`
4. integrate `ToolResultProcessingPolicy`
5. add denial semantics
6. tighten trace/event surfaces if needed

This keeps the work incremental while still moving the boundary in the
correct direction.

## Final Recommendation

Quenda should not make tool policies configurable before this refactor is
done.

The correct order is:

1. make tool phase Runtime-owned
2. make tool policies real
3. then expose them through agent/session/config binding

That sequencing preserves both framework clarity and future
replaceability.
