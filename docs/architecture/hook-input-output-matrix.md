# Hook Input / Output Matrix

## Status

Draft (2026-06-29)

## Purpose

This document provides a single matrix view of Quenda's current and
planned hook seams.

For each seam, it answers four implementation-critical questions:

- at which lifecycle stage it runs
- what structured context it receives
- what output or decision it returns
- which state transition or data-path change it can affect

This document is intended to make hook design and implementation more
mechanical and less ambiguous.

It should be read together with:

- [ADR-020](/Users/xushiting/Workspace/quenda/docs/decisions/020-runtime-terminology-and-execution-units.md)
- [ADR-021](/Users/xushiting/Workspace/quenda/docs/decisions/021-runtime-lifecycle-and-state-machine.md)
- [ADR-022](/Users/xushiting/Workspace/quenda/docs/decisions/022-keep-core-minimal-and-push-strategies-to-policies.md)
- [ADR-023](/Users/xushiting/Workspace/quenda/docs/decisions/023-runtime-owns-tool-phase-and-policy-control.md)

## How To Read This Matrix

Each seam is described along these dimensions:

- `Stage`: the lifecycle state or boundary where Runtime invokes it
- `Input Context`: the structured facts available to the seam
- `Output / Decision`: the returned object or effect
- `Data-Path Impact`: whether the seam changes payloads written into the
  loop or storage
- `Transition Impact`: whether the seam can affect state transitions
- `Status`: current maturity in Quenda

## Transition Impact Legend

To keep transition semantics precise, this document uses the following
impact categories.

| Impact | Meaning |
|---|---|
| `None` | No control-flow effect. Observer only. |
| `Executes Optional State` | Can cause entry into an optional phase, but does not itself choose the next legal terminal or loop state. |
| `Constrains Phase Work` | Does not choose the next top-level state directly, but changes what work occurs inside the current phase. |
| `Chooses Next State` | Can directly determine the next runtime state from a boundary. |
| `Terminal` | Can end the run by driving transition to `Completed`, `Terminated`, `Interrupted`, or `Failed`. |

## Current Official Seam Set

These are the seams Quenda already has or has already named explicitly in
design work.

| Seam | Role | Stage | Input Context | Output / Decision | Data-Path Impact | Transition Impact | Status |
|---|---|---|---|---|---|---|---|
| `CompressionPolicy` | Policy | `CompressionCheck` | `CompressionStats`: estimated input tokens, message count, context window, reserved output tokens, summary token count, hot message count, session identity, agent identity, mode, cumulative usage | `CompressionDecision`: `compress`, `keep_last_n_messages`, `target_budget_tokens`, `archive_raw_messages`, `summarizer_id`, `reason` | Indirect: if `compress=True`, Runtime later rewrites session history through `CompressionRunning` | `Executes Optional State`: `CompressionCheck -> CompressionRunning` or `CompressionCheck -> ContextPrepared` | Implemented |
| `TraceSink` | Observer | All emitted event boundaries via `Run._emit()` | `AnyEvent` | `None` from caller perspective; sink performs side-effectful recording | None to runtime data path; observer only | `None` | Implemented |
| `TerminationPolicy` | Policy | After each completed observable step, before Runtime continues the loop | `TerminationState`: step counts, tool rounds, elapsed time, cumulative token usage, error counts, run/session/agent identity, last step type, last stop reason | `TerminationDecision`: `should_stop`, `reason` | None directly; may stop further writes or calls by ending the run | `Chooses Next State`: typically drives `LoopDecision -> Terminated`, and under current semantics may also stop before next phase starts | Implemented |
| `ToolSelectionPolicy` | Policy | Inside `ToolPhaseRunning`, after `ModelResponded`, before any tool execution | `ToolSelectionRequest`: requested `tool_calls`, `available_tools`, run/session/agent identity, `step_count`, `tool_round_count` | `ToolSelectionDecision`: `approved`, `rejected` | Yes: determines which tool calls execute and which denial results must be synthesized into loop writeback | `Constrains Phase Work`: affects work inside `ToolPhaseRunning`; does not itself choose `Completed` / `Terminated` / etc. | Target contract; enabled by ADR-023 refactor |
| `ToolResultProcessingPolicy` | Policy | Inside `ToolPhaseRunning`, after one approved tool execution completes, before tool-result writeback | `ToolResultEnvelope`: `call_id`, `tool_name`, `raw_content`, `is_error`, `duration_ms`, display metadata | `ProcessedToolResult`: processed `content`, `is_error`, display metadata | Yes: determines loop-facing tool result payload while preserving raw result for trace/debugging | `Constrains Phase Work`: affects writeback contents, not top-level next state directly | Target contract; enabled by ADR-023 refactor |

## Tool-Phase Transition Semantics

Because tool seams are the easiest to confuse, the matrix below expands
their exact transition relationship under `ADR-023`.

| Seam | Entry Boundary | Exit Boundary | What It Can Change | What It Cannot Change In Phase 1 |
|---|---|---|---|---|
| `ToolSelectionPolicy` | `ModelResponded -> ToolPhaseRunning` | Remains inside `ToolPhaseRunning` | Which calls execute, which calls are rejected, whether denial results must be synthesized, whether the batch is effectively all-denied | It does not rewrite tool arguments, hide tools from the model, or directly choose `Completed` / `Failed` / `Terminated` |
| `ToolResultProcessingPolicy` | After one approved call executes inside `ToolPhaseRunning` | Still inside `ToolPhaseRunning`, before writeback commit | The loop-facing content of a tool result, including truncation, redaction, or summarization | It does not erase raw execution truth, skip assistant requested-call writeback, or directly choose the next runtime state |
| `TerminationPolicy` during tool phase | After a tool execution step or other completed observable step | `Terminated` if triggered | Whether remaining calls in the batch are skipped because the whole run ends | It does not, in phase 1, continue back to the model with partial results after run-level termination |

## Near-Term Runtime Seam Matrix

These seams are either already implied by existing ADRs or strongly
recommended by the current architecture direction, but do not yet all
have finalized code contracts.

| Proposed Seam | Role | Stage | Input Context | Output / Decision | Data-Path Impact | Transition Impact | Status |
|---|---|---|---|---|---|---|---|
| `ContextAssemblyPolicy` | Policy | Before `ContextPrepared` is finalized | Candidate prompt parts: system prompt, summary blocks, recent messages, optional overlays, budget facts, session metadata | Proposed effective context or filtered context components | Yes: changes the exact prompt/context sent to `ModelInvoking` | `Constrains Phase Work`: shapes `ContextPrepared`, but normally does not choose terminal state | Planned seam; contract not finalized |
| `VerificationPolicy` | Policy | `VerificationRunning`, typically after `ModelResponded` or `ToolBatchCompleted` | Candidate answer, model stop reason, requested tool batch, tool results, raw/processed outputs, run metadata, optional verifier-specific evidence | Verification decision such as accept, reject, retry, continue, terminate, fail, or hand off to reflection | Usually none directly to stored data; primarily changes control outcome | `Chooses Next State`: may send `VerificationRunning -> LoopDecision`, `ReflectionRunning`, `Completed`, `Terminated`, or `Failed` depending on final contract | Planned seam; lifecycle slot reserved |
| `ReflectionPolicy` | Policy | `ReflectionRunning`, usually after verification or no-progress detection | Recent trajectory slice, tool history, prior failures, verification feedback, budgets, run metadata | Reflection artifact or next-action guidance, possibly plus a decision to continue or stop | Possible: may append reflection memory or reflective prompt material for next step | `Chooses Next State`: usually back to `ModelInvoking`, but may also terminate or fail if policy says no viable repair path | Planned seam; lifecycle slot reserved |
| `MemoryRetrievalPolicy` | Policy | `MemoryReadRunning`, before `ContextPrepared` | Retrieval query context, current user message, recent messages, summaries, budgets, session/agent metadata, candidate memories | Selected memories or ranked memory set to include in context | Yes: changes what long-term memory material enters the prompt | `Constrains Phase Work`: affects `MemoryReadRunning -> ContextPrepared` content, not top-level terminal outcome directly | Planned seam |
| `MemoryWritePolicy` | Policy | `MemoryWriteRunning`, after `ToolBatchCompleted` or after `Completed` | Recent trajectory slice, final/partial answer, tool results, summaries, usage and metadata, candidate memory writes | Write set, deduplicated memory entries, retention metadata, or no-op | Yes: changes persistent memory store contents | `Executes Optional State`: influences work performed in `MemoryWriteRunning`; usually returns to `LoopDecision` or post-completion flow | Planned seam |
| `MemoryCompactionPolicy` | Policy | `MemoryCompactionRunning` | Existing memory inventory, size / retention stats, trust metadata, compaction budget | Compaction plan or no-op | Yes: rewrites memory-store layout or retained set | `Executes Optional State` | Planned seam |

## Observer And Middleware Matrix

Not every extension point should be a policy. Some are better modeled as
observers or wrappers.

| Seam Type | Example Seam | Stage | Input Context | Output / Decision | Transition Impact | Notes |
|---|---|---|---|---|---|---|
| Observer | `TraceSink` | Any emitted event boundary | `AnyEvent` | None | `None` | Must never affect control flow |
| Middleware | Future model invocation middleware | Around `ModelInvoking` | Model request, effective context, tool schema, runtime metadata | Wrapped model result or instrumentation side effects | Usually `Constrains Phase Work`; should not choose terminal state unless explicitly designed as policy+middleware hybrid | Good for telemetry, retries, provider adaptation |
| Middleware | Future tool execution middleware | Inside `ToolPhaseRunning`, around one tool call | Approved `ToolCall`, runtime metadata | Wrapped raw `ToolResult` or instrumentation side effects | `Constrains Phase Work` | Good for timeout wrappers, sandbox adapters, structured logging |

## State-Centric View

The following matrix reverses the perspective: for each important state,
which seams naturally attach there.

| State / Boundary | Natural Seams | Typical Decision Scope |
|---|---|---|
| `CompressionCheck` | `CompressionPolicy` | Whether compression should run before context preparation |
| `CompressionRunning` | None by default; execution seam only | Execute compressor and apply result |
| `MemoryReadRunning` | `MemoryRetrievalPolicy` | Which memories enter the next effective context |
| `ContextPrepared` | `ContextAssemblyPolicy` | What exact prompt/context is passed to the model |
| `ModelInvoking` | Future model middleware | Execution wrapping, observability, provider adaptation |
| `ModelResponded` | `TerminationPolicy`, future `VerificationPolicy` | Whether to stop, accept, or enter tool / verification / reflection paths |
| `ToolPhaseRunning` | `ToolSelectionPolicy`, tool middleware, `ToolResultProcessingPolicy`, `TerminationPolicy` | Which calls execute, how results are shaped, whether run stops during batch |
| `ToolBatchCompleted` | `TerminationPolicy`, future `VerificationPolicy`, future `MemoryWritePolicy` | Whether to continue looping, verify, persist memory, or terminate |
| `LoopDecision` | `TerminationPolicy`, future loop-control policies | Which legal next state is selected |
| `Completed` | Future `MemoryWritePolicy`, observers | Final persistence and export side effects |

## Transition-Centric View

This table is useful when designing a new hook and asking whether it is
allowed to move the state machine or only shape data inside a phase.

| Transition | Current / Proposed Owner | Hook(s) That May Influence It | Allowed Influence Type |
|---|---|---|---|
| `CompressionCheck -> CompressionRunning` | Runtime | `CompressionPolicy` | Decide whether optional phase runs |
| `CompressionCheck -> ContextPrepared` | Runtime | `CompressionPolicy` | Decide no-compression path |
| `ContextPrepared -> ModelInvoking` | Runtime | Future `ContextAssemblyPolicy`, model middleware | Data shaping only; transition remains mandatory in normal path |
| `ModelResponded -> Completed` | Runtime | `TerminationPolicy` indirectly, future `VerificationPolicy` | Accept / stop / verify semantics |
| `ModelResponded -> ToolPhaseRunning` | Runtime | `TerminationPolicy`, `ToolSelectionPolicy` indirectly after entry, future `VerificationPolicy` | Decide whether to enter tool phase or stop first |
| `ToolPhaseRunning -> ToolBatchCompleted` | Runtime | `ToolSelectionPolicy`, `ToolResultProcessingPolicy`, tool middleware | Constrain internal work and writeback before batch completion |
| `ToolBatchCompleted -> LoopDecision` | Runtime | None in phase 1 beyond completion of phase work | Boundary handoff |
| `LoopDecision -> ModelInvoking` | Runtime | `TerminationPolicy`, future `VerificationPolicy`, future `ReflectionPolicy` | Continue loop |
| `LoopDecision -> Completed` | Runtime | Future verification / reflection semantics, natural completion logic | Complete run |
| `LoopDecision -> Terminated` | Runtime | `TerminationPolicy` | Policy stop |
| `LoopDecision -> Interrupted` | Runtime + external signal | External interruption handling | External stop only |
| `LoopDecision -> Failed` | Runtime | Runtime error handling, future verifier fail semantics | Failure |

## Recommended Contract Rules

The matrix implies a small set of design rules for future seams.

### 1. Observer seams should return nothing meaningful to Runtime

If a seam is observer-only, its output should not affect control flow.

### 2. Policies should receive structured facts, not framework internals

Inputs should look like:

- `CompressionStats`
- `TerminationState`
- `ToolSelectionRequest`
- `ToolResultEnvelope`

not large mutable runtime objects.

### 3. Transition-changing seams should be rare and explicit

Most seams should shape:

- context
- batch composition
- result payloads
- persistence

Only a small subset should directly choose next state:

- `TerminationPolicy`
- future `VerificationPolicy`
- future `ReflectionPolicy`

### 4. Data-path shaping and state-transition choice should stay distinct

For example:

- `ToolResultProcessingPolicy` shapes result payloads
- `TerminationPolicy` decides whether the run stops

Those should not collapse into one overloaded seam.

## Suggested Next Use

This matrix should be the reference sheet when:

- reviewing new hook proposals
- deciding whether a seam is a policy, middleware, or observer
- implementing Runtime-owned phase boundaries
- defining config binding for policies

If a future hook cannot be placed cleanly into this matrix, that is a
signal that either:

- the lifecycle model needs refinement
- or the proposed seam is mixing too many responsibilities
