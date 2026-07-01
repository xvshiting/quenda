# Hook Interface Drafts

## Status

Draft (2026-06-26)

## Purpose

This document defines concrete interface drafts for the first four hook
seams proposed in
[hook-mvp-prioritization.md](/Users/xushiting/Workspace/quenda/docs/architecture/hook-mvp-prioritization.md):

- `TraceSink`
- `TerminationPolicy`
- `ToolSelectionPolicy`
- `ToolResultProcessingPolicy`

The goal is not only to describe the desired interfaces, but also to
state clearly which seams are directly implementable on top of the
current Quenda runtime, and which seams require a preceding Runtime /
Kernel ownership refactor.

This is an architecture draft, not an ADR. It should guide API review
and implementation planning.

## Design Rules

These four seams all follow the same design rules:

- Runtime owns policy invocation
- Kernel remains a small execution engine
- Kernel may keep hard safety guards
- policy seams should use small typed contracts
- default implementations should preserve current behavior
- raw execution data must remain observable even when processed data is
  fed back into the loop

## Current Implementation Constraints

The current Quenda execution flow creates an important constraint.

Today:

- `Kernel.run()` yields a `model` step
- then Kernel itself executes any returned tool calls
- then Kernel itself appends raw tool results back into `messages`

This means Runtime can observe steps, but it does not fully own:

- tool-call gating before execution
- tool-result shaping before message writeback

That affects implementation readiness significantly.

## Implementation Readiness Summary

| Seam | Target Layer | Current Readiness | Notes |
|---|---|---|---|
| `TraceSink` | Runtime | Directly implementable | Hook point already exists in `Run._emit()` |
| `TerminationPolicy` | Runtime | Implementable with localized Runtime changes | Requires explicit stop propagation to the running Kernel loop |
| `ToolSelectionPolicy` | Runtime | Not directly implementable | Requires Runtime ownership of tool-call approval before execution |
| `ToolResultProcessingPolicy` | Runtime | Not directly implementable | Requires Runtime ownership of tool-result writeback before messages are updated |

Recommended interpretation:

- `TraceSink` is a phase-1 implementation seam
- `TerminationPolicy` is a phase-1.5 seam
- `ToolSelectionPolicy` and `ToolResultProcessingPolicy` should be
  treated as target contracts for the next Runtime / Kernel refactor,
  not as drop-in seams on the current code path

## Kernel Guard vs Runtime Policy

Quenda should keep a clear distinction between:

- Kernel hard guards
- Runtime strategy policies

Example:

- `Kernel.max_iterations` remains a hard execution safeguard
- `TerminationPolicy` remains a Runtime-level stopping strategy

This distinction matters because:

- Kernel must still prevent runaway execution even if no policy is
  configured
- Runtime has the broader state needed for strategy decisions

The same principle applies to tool seams:

- Kernel may continue to execute tools
- but policy ownership should move toward Runtime

## Seam 1: TraceSink

## Role

- observer

## Responsibility

`TraceSink` records structured runtime events for debugging, replay,
evaluation, or export.

It must not change control flow.

## Invocation Point

Primary hook point:

- `Run._emit()`

This is already the narrowest and most stable place to observe the full
run lifecycle.

## Interface Draft

```python
from typing import Protocol
from quenda.runtime.events import AnyEvent


class TraceSink(Protocol):
    """
    Observer for runtime events.

    Runtime calls record() for each event emitted. Implementations must
    not raise exceptions into the runtime.
    """

    def record(self, event: AnyEvent) -> None:
        """Record one runtime event."""
        ...
```

## Default Implementation

```python
class NullTraceSink:
    """No-op trace sink."""

    def record(self, event: AnyEvent) -> None:
        pass
```

## First Useful Official Implementation

```python
class JsonlTraceSink:
    """
    Append serialized events to a JSONL file.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def record(self, event: AnyEvent) -> None:
        ...
```

## Error Handling

Recommended rule:

- trace sinks must not crash the run
- Runtime should suppress sink failures
- optional diagnostics may be logged later, but should not propagate

## Readiness

This seam is directly implementable on the current architecture.

## Seam 2: TerminationPolicy

## Role

- policy

## Responsibility

`TerminationPolicy` decides whether the run should stop after a
completed step.

This is a Runtime strategy seam, not a Kernel execution guard.

## Invocation Point

Primary hook point:

- inside the Runtime step loop in `Run.execute()`
- after Runtime updates step/accounting state
- before Runtime allows the loop to continue

Runtime is the correct owner because it already has access to:

- step count
- cumulative usage
- elapsed time
- error state
- session and run metadata

## Interface Draft

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TerminationState:
    """
    Runtime-owned snapshot passed into TerminationPolicy.
    """

    run_id: str
    session_id: str
    agent_name: str
    step_count: int
    tool_round_count: int
    elapsed_time_ms: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    error_count: int
    consecutive_error_count: int
    last_step_type: str | None = None
    last_stop_reason: str | None = None


@dataclass(frozen=True)
class TerminationDecision:
    """
    Output returned by TerminationPolicy.
    """

    should_stop: bool
    reason: str = ""


class TerminationPolicy(Protocol):
    """
    Runtime stopping policy.

    Called after each completed step to decide whether execution should
    continue.
    """

    def should_terminate(
        self,
        state: TerminationState,
    ) -> TerminationDecision:
        ...
```

## Default Implementation

```python
class NeverTerminatePolicy:
    """Default: never stop early."""

    def should_terminate(
        self,
        state: TerminationState,
    ) -> TerminationDecision:
        return TerminationDecision(should_stop=False)
```

## First Useful Official Implementations

- `MaxStepsTerminationPolicy`
- `TimeBudgetTerminationPolicy`
- `TokenBudgetTerminationPolicy`
- `ConsecutiveErrorTerminationPolicy`
- `CompositeTerminationPolicy`

## Important Implementation Note

`break` in the Runtime loop is not enough by itself. The running Kernel
loop must also receive a stop signal.

Therefore, this seam requires:

- Runtime-level decision logic
- plus explicit stop propagation into the currently running execution
  loop

That stop propagation may reuse:

- existing interrupt signaling
- or a dedicated Runtime-managed stop mechanism

## Readiness

This seam is implementable with localized Runtime changes, but it is not
purely additive. Stop propagation must be designed intentionally.

## Seam 3: ToolSelectionPolicy

## Role

- policy

## Responsibility

`ToolSelectionPolicy` approves, rejects, or filters tool calls after the
model requests them and before tools are executed.

Phase 1 scope is intentionally narrow:

- execution approval only
- not model-facing tool routing
- not tool-argument rewriting
- not planner behavior

## Target Layer Ownership

Recommended target ownership:

- Runtime owns tool-call approval
- Kernel owns tool execution mechanics

That is the right architecture, but it is not the current execution
shape yet.

## Interface Draft

```python
from dataclasses import dataclass
from typing import Protocol
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolCall


@dataclass(frozen=True)
class ToolSelectionRequest:
    """
    Runtime-owned input to ToolSelectionPolicy.
    """

    run_id: str
    session_id: str
    agent_name: str
    step_count: int
    tool_round_count: int
    tool_calls: list[ToolCall]
    available_tools: list[Tool]


@dataclass(frozen=True)
class RejectedToolCall:
    """
    A rejected tool call plus an explanation.
    """

    call: ToolCall
    reason: str


@dataclass(frozen=True)
class ToolSelectionDecision:
    """
    Partition of approved and rejected calls.
    """

    approved: list[ToolCall]
    rejected: list[RejectedToolCall]


class ToolSelectionPolicy(Protocol):
    """
    Policy for tool execution approval/filtering.
    """

    def select_tools(
        self,
        request: ToolSelectionRequest,
    ) -> ToolSelectionDecision:
        ...
```

## Default Implementation

```python
class AllowAllToolSelectionPolicy:
    """Default: approve every requested tool call."""

    def select_tools(
        self,
        request: ToolSelectionRequest,
    ) -> ToolSelectionDecision:
        return ToolSelectionDecision(
            approved=list(request.tool_calls),
            rejected=[],
        )
```

## First Useful Official Implementations

- `DenylistToolSelectionPolicy`
- `AllowlistToolSelectionPolicy`
- `RiskGatingToolSelectionPolicy`

## Important Implementation Constraint

This seam is not directly implementable on the current execution path.

Today:

- `Kernel.run()` yields a `ModelResponse`
- then, when iteration continues, Kernel itself executes
  `response.tool_calls`
- `ModelResponse` is also a frozen dataclass, so Runtime cannot safely
  mutate `response.tool_calls` in place

Therefore, implementing this seam correctly requires one of:

- moving tool-call execution approval into Runtime
- or introducing an explicit Kernel callback / handoff seam before tool
  execution

Until that refactor exists, this interface should be treated as a target
contract, not as a drop-in implementation seam.

## Runtime Behavior for Rejections

Once the seam exists, rejected calls should remain explicit.

Recommended direction:

- preserve rejection information in trace
- synthesize a structured denied-call observation or tool-error result
  for the loop

That preserves debuggability and makes denials visible to the model.

## Readiness

This seam requires a Runtime / Kernel ownership refactor before it can
be implemented correctly.

## Seam 4: ToolResultProcessingPolicy

## Role

- policy

## Responsibility

`ToolResultProcessingPolicy` transforms raw tool output before that
output is reintroduced into the agent loop.

The seam exists because raw tool output is often too large, too noisy,
or too unsafe to feed back unchanged.

## Target Layer Ownership

Recommended target ownership:

- Kernel owns raw execution
- Runtime owns observation shaping

This keeps execution separate from strategy.

## Interface Draft

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolResultEnvelope:
    """
    Runtime-owned raw tool result container.
    """

    call_id: str
    tool_name: str
    raw_content: str
    is_error: bool
    duration_ms: int
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


@dataclass(frozen=True)
class ProcessedToolResult:
    """
    Processed result to feed back into the loop.
    """

    content: str
    is_error: bool
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


class ToolResultProcessingPolicy(Protocol):
    """
    Policy for shaping tool output before it returns to the agent loop.
    """

    def process_result(
        self,
        result: ToolResultEnvelope,
    ) -> ProcessedToolResult:
        ...
```

## Default Implementation

```python
class PassthroughToolResultProcessingPolicy:
    """Default: return tool output unchanged."""

    def process_result(
        self,
        result: ToolResultEnvelope,
    ) -> ProcessedToolResult:
        return ProcessedToolResult(
            content=result.raw_content,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=result.result_summary,
        )
```

## First Useful Official Implementations

- `TruncatingToolResultProcessingPolicy`
- `LineLimitedToolResultProcessingPolicy`
- `RedactingToolResultProcessingPolicy`
- `CompositeToolResultProcessingPolicy`

## Raw vs Processed Rule

This seam requires an explicit rule:

- traces and debugging should be able to preserve raw output
- the agent loop may consume processed output

This distinction should remain visible in the implementation, not only
in comments.

## Important Implementation Constraint

This seam is also not directly implementable on the current execution
path.

Today:

- Kernel executes tools
- Kernel appends raw tool results back into `messages` internally

That means Runtime can observe tool steps, but it does not yet own the
message writeback point where processed output should be substituted.

Therefore, implementing this seam correctly requires:

- moving tool-result writeback ownership into Runtime
- or introducing an explicit seam between raw execution and message
  append

Until that change exists, this interface should be treated as a target
contract.

## Readiness

This seam requires a Runtime / Kernel ownership refactor before it can
be implemented correctly.

## Registration Direction

These seams should follow the registration model described in
[policy-registration-and-hook-configuration.md](/Users/xushiting/Workspace/quenda/docs/architecture/policy-registration-and-hook-configuration.md).

Recommended direction:

```python
agent = Agent(
    ...,
    policies={
        "termination": MaxStepsTerminationPolicy(max_steps=8),
        "tool_selection": AllowAllToolSelectionPolicy(),
        "tool_result_processing": TruncatingToolResultProcessingPolicy(
            max_chars=4000,
        ),
    },
    trace_sink=JsonlTraceSink("runs.jsonl"),
)
```

## Suggested Official Packaging Model

The framework should define the seam. Official packages should provide
default or reference implementations. Users should be able to replace
them smoothly.

Recommended conceptual split:

- Quenda Core defines lifecycle stages, protocols, and wiring
- official implementations provide default strategies
- downstream users provide their own replacements through code or config

This keeps framework mechanism separate from official policy behavior.

## Recommended Next Implementation Order

1. `TraceSink`
2. `TerminationPolicy`
3. Runtime / Kernel refactor for tool ownership
4. `ToolSelectionPolicy`
5. `ToolResultProcessingPolicy`

This order matches both implementation readiness and architectural risk.

## Final Recommendation

These four drafts are ready for API review, with one important
qualification:

- not all four seams are equally ready for direct implementation on the
  current code path

The most important architectural conclusion is:

- `TraceSink` is directly implementable
- `TerminationPolicy` is close, but needs stop propagation
- tool-related seams should be designed now, but implemented only after
  Runtime owns the relevant parts of tool-loop control
