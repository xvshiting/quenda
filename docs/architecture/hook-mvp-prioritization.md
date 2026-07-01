# Hook MVP Prioritization

## Status

Draft (2026-06-26)

## Purpose

This document proposes the first implementation wave for Kora's
lifecycle hook and policy system.

It focuses on one practical question:

- if Kora should become a hookable, policy-driven agent framework,
  which seams should be implemented first

The goal is not to define the full long-term hook surface. The goal is
to identify the smallest high-value set that:

- is useful for downstream agent builders
- matches current agent research practice
- fits Kora's current architecture
- can be implemented without destabilizing the core runtime

## Recommendation

The first MVP wave should prioritize these four seams:

1. `TraceSink`
2. `TerminationPolicy`
3. `ToolSelectionPolicy`
4. `ToolResultProcessingPolicy`

In addition, the existing `CompressionPolicy` should be treated as the
reference pattern for policy-style extension in Kora.

This gives Kora one seam in each of four important categories:

- observability
- runtime control
- tool-use decision making
- tool feedback shaping

Together, they create a useful minimum platform for experimentation
without forcing Kora to solve the entire lifecycle at once.

## Why These Four First

### 1. `TraceSink` is foundational

Without a structured trajectory surface, it is hard to:

- compare different strategies
- evaluate agent behavior offline
- export runs into benchmarks
- debug policy behavior
- support later RL or optimization workflows

`TraceSink` is also low-risk because it can begin as an observer-only
surface that does not change control flow.

### 2. `TerminationPolicy` is high-value and low-ambiguity

Stopping rules are one of the most common strategy surfaces in practical
agent work.

Users often want to control:

- maximum number of steps
- maximum tool rounds
- time budget
- token or cost budget
- when to stop after repeated failure

This seam is narrow, easy to explain, and useful across almost every
agent domain.

### 3. `ToolSelectionPolicy` unlocks many real agent experiments

Tool use is one of the most important and most failure-prone parts of an
agent system.

A tool-selection seam supports:

- allowing or denying risky tools
- rerouting tool choices
- learned or heuristic tool preferences
- environment-specific tool gating

It is also a natural fit for Kora because tools are already explicit
runtime objects.

### 4. `ToolResultProcessingPolicy` improves the observation loop

Many agent systems fail not because the tool call was wrong, but because
the tool output fed back into the model was too long, too noisy, or too
raw.

A tool-result processing seam enables:

- truncation
- summarization
- normalization
- tagging
- redaction

This is especially valuable for coding, browsing, and long-output tool
workflows.

### 5. `CompressionPolicy` already demonstrates the right pattern

Kora already has a useful policy seam in compression:

```text
Runtime -> compression_policy.should_compress(stats) -> CompressionDecision
```

This is an excellent template because it shows:

- a named stage
- a typed input object
- a typed decision object
- runtime-owned invocation
- host / runtime separation of concerns

The first MVP should reuse this design style rather than inventing a
different extension idiom.

## Why Not Start Elsewhere

Some other seams are important, but less suitable for the first wave.

### Context assembly

This is strategically important, but it is also easy to over-design.
Starting here risks turning phase 1 into a large prompt-engineering
abstraction project.

### Memory policies

Memory is central to long-running agents, but the seam surface is wider:

- retrieval
- write
- delete
- trust
- expiry
- compression

It is better to let the first wave stabilize smaller policy patterns
before introducing a memory subsystem.

### Reflection / verification

This is valuable, but depends on having:

- good trace surfaces
- explicit stopping rules
- stable tool observation surfaces

It benefits from the first MVP, rather than replacing it.

### Planner / workflow seams

These are high-value for advanced research, but they are also more
architecturally invasive. They should build on stable lower-level seams.

## MVP Scope

The first hook MVP should aim to deliver:

- one observer-style seam
- three policy-style seams
- compatibility with the current runtime
- minimal configuration and registration support
- no mandatory changes to existing agents

It should not attempt to deliver:

- a complete lifecycle hook framework
- full memory architecture
- multi-agent orchestration hooks
- a universal hook base class

## Proposed MVP Interfaces

These interfaces are intentionally minimal and illustrative. The exact
final type names may differ, but the seam shape should stay small.

### 1. `TraceSink`

Role:

- observer

Purpose:

- receive structured runtime events and trajectories

Minimal direction:

```python
class TraceSink(Protocol):
    def record(self, event: TraceEvent) -> None:
        ...
```

Minimum useful output should cover:

- run start
- model response
- tool execution
- interruption
- termination
- run completion

Recommended first implementation:

- a no-op default sink
- a JSONL trace sink for local replay and analysis

### 2. `TerminationPolicy`

Role:

- policy

Purpose:

- decide whether execution should continue, stop, or stop with a reason

Minimal direction:

```python
class TerminationPolicy(Protocol):
    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        ...
```

Minimum input should include:

- step count
- tool round count
- elapsed time
- usage totals if available
- last error or failure count if available

Minimum output should include:

- continue or stop
- reason

Recommended first implementations:

- default "never stop early" policy
- max-steps policy
- budget-aware policy

### 3. `ToolSelectionPolicy`

Role:

- policy

Purpose:

- decide how requested tool calls should be filtered, allowed, denied,
  or reranked before execution

Minimal direction:

```python
class ToolSelectionPolicy(Protocol):
    def select(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        ...
```

Minimum input should include:

- requested tool calls
- available tools
- current run or session metadata

Minimum output should include:

- approved tool calls
- rejected tool calls with reasons if relevant

Recommended first implementations:

- allow-all default policy
- denylist or allowlist policy
- simple risk-gating policy

### 4. `ToolResultProcessingPolicy`

Role:

- policy

Purpose:

- transform raw tool output before it is surfaced back into the agent
  loop

Minimal direction:

```python
class ToolResultProcessingPolicy(Protocol):
    def process(self, result: ToolResultEnvelope) -> ToolResultEnvelope:
        ...
```

Minimum input should include:

- tool name
- raw content
- error flag
- metadata such as duration and summary if available

Recommended first implementations:

- passthrough default policy
- truncation policy
- line-limit or character-limit policy

## Mapping to Kora Layers

The first MVP should align with existing layer responsibilities.

### `TraceSink`

Best home:

- Runtime events, with optional Host persistence/export

Why:

- Runtime already emits meaningful execution events
- Host can own serialization or external destinations

### `TerminationPolicy`

Best home:

- Runtime loop control

Why:

- Runtime already manages execution progress and step accounting
- termination is a loop-orchestration concern, not a Kernel concern

### `ToolSelectionPolicy`

Best home:

- Runtime, immediately before tool execution

Why:

- tool requests are already visible at that level
- this avoids pushing risk logic into Kernel internals

### `ToolResultProcessingPolicy`

Best home:

- Runtime, immediately after tool execution and before feedback is
  emitted or persisted

Why:

- this is the right place to shape observations without changing tool
  implementation itself

## Registration Model

The MVP should reuse the general policy-registration direction already
described in
[policy-registration-and-hook-configuration.md](/Users/xushiting/Workspace/kora/docs/architecture/policy-registration-and-hook-configuration.md).

Recommended programmatic shape:

```python
agent = Agent(
    ...,
    policies={
        "termination": MaxStepsTerminationPolicy(max_steps=8),
        "tool_selection": SafeToolSelectionPolicy(),
        "tool_result_processing": TruncatingToolResultPolicy(max_chars=4000),
    },
    trace_sink=JsonlTraceSink("runs.jsonl"),
)
```

This can later be normalized further into a unified registration model,
but phase 1 should optimize for clarity rather than perfect symmetry.

Recommended configuration direction:

```yaml
policies:
  termination:
    factory: mypkg.runtime:MaxStepsTerminationPolicy
    config:
      max_steps: 8
  tool_selection:
    factory: mypkg.tools:SafeToolSelectionPolicy
  tool_result_processing:
    factory: mypkg.tools:TruncatingToolResultPolicy
    config:
      max_chars: 4000

trace:
  sink:
    factory: mypkg.trace:JsonlTraceSink
    config:
      path: runs.jsonl
```

## Backward Compatibility

The first MVP should not force migration of existing agents.

Recommended compatibility rules:

- if no new policy is configured, current behavior remains the default
- existing compression behavior stays unchanged
- new seams are opt-in
- default implementations should match current runtime behavior as
  closely as possible

## Evaluation Criteria

The first hook MVP should be considered successful if it enables users
to:

1. export a structured run trace without patching core
2. stop an agent after a custom number of steps or tool rounds
3. deny or filter tools through a small policy object
4. truncate or reshape tool output before it returns to the model

If these four are possible, Kora will already have a credible first
policy platform.

## Risks

### Risk 1: Too many seams in the first wave

If phase 1 introduces too many lifecycle abstractions, the interfaces
will be unstable and confusing.

Mitigation:

- keep the first wave to four seams plus the existing compression
  pattern

### Risk 2: Inconsistent extension styles

If trace, policies, and compression all use different registration
models, the user experience will become fragmented.

Mitigation:

- keep naming and registration direction consistent across all seams

### Risk 3: Tool-result shaping changes semantics unexpectedly

If processed tool results differ too much from raw output, debugging can
become harder.

Mitigation:

- preserve raw output in trace when possible
- make result-processing policies explicit and observable

## Suggested Next Step

After this MVP prioritization is accepted, the next design pass should
define:

- the concrete `TraceEvent` model
- the concrete `TerminationState` and `TerminationDecision` objects
- the exact request / decision contracts for tool selection
- the exact result envelope for tool-result processing

That should be the point where design moves from prioritization into
implementation-ready interface definitions.
