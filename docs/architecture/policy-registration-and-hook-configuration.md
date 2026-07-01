# Policy Registration and Hook Configuration

## Status

Draft (2026-06-26)

## Purpose

This document turns the strategy-hook direction into a concrete
configuration model.

It focuses on one practical goal:

- a downstream user should be able to write a small policy
  implementation and attach it to a well-defined lifecycle stage
  through programmatic registration or configuration, without modifying
  Kora core

This document answers:

- what a user-facing hook model should look like
- how policies should be registered
- how configuration should bind policies to lifecycle stages
- how defaults and overrides should work

## Problem Statement

Kora is moving toward a lifecycle-hook and policy-driven design.

That direction is only useful if downstream users can actually consume
it easily. In practice, this means the framework should not require
users to:

- patch core runtime code
- subclass large framework classes
- wire dozens of callbacks manually
- understand deep internal control flow before trying a new strategy

The desired experience is much simpler:

1. a user writes a small policy object or function
2. the user attaches it to a named lifecycle stage
3. the agent configuration activates it
4. Kora invokes it at the appropriate stage

This matches the broader framework goals:

- simple defaults
- explicit extension points
- policy replacement without forking

## Design Principles

### 1. Named stages, not arbitrary callback soup

Users should register against explicit, documented lifecycle stages such
as:

- `compression`
- `memory_retrieval`
- `memory_write`
- `model_selection`
- `tool_selection`
- `termination`

They should not have to guess which `before_x` / `after_x` callback is
the right one.

### 2. Small interfaces

Each policy seam should expose a small contract with:

- clearly defined input context
- a small decision object or return type
- a single responsibility

This is more in line with a Unix-style framework than exposing one large
manager object.

### 3. Programmatic first, config second

The first-class extension path should be Python registration.

Configuration-based loading should also exist, but it should be built on
top of the same programmatic interface rather than inventing a second
policy mechanism.

### 4. Defaults must remain valid

Every policy seam should have a framework default.

Users should be able to override only the stages they care about.

### 5. Explicit over implicit

The configuration should make it obvious:

- which stage is being overridden
- which implementation is being used
- what happens when a policy is missing

## Proposed Terminology

To keep naming consistent, the following terms are recommended.

### Lifecycle Stage

A named point in the agent execution lifecycle where Kora allows
strategy substitution.

Examples:

- `context_assembly`
- `compression`
- `memory_retrieval`
- `tool_selection`

### Policy

A strategy object that makes a decision at a lifecycle stage.

Examples:

- `CompressionPolicy`
- `MemoryRetrievalPolicy`
- `ToolSelectionPolicy`
- `TerminationPolicy`

### Middleware

A wrapper around a stage that can act before and after execution.

This is more appropriate for execution-oriented seams such as:

- model invocation
- tool execution
- persistence

### Observer

A read-only extension that receives structured events or traces.

This is more appropriate for:

- metrics
- logging
- evaluation
- trace export

## Recommended User Experience

The target user experience should look like this.

### Programmatic registration

```python
agent = Agent(
    name="research-agent",
    system_prompt="...",
    tools=[...],
    model=model,
    policies={
        "compression": MyCompressionPolicy(),
        "memory_retrieval": MyMemoryRetrievalPolicy(),
        "tool_selection": MyToolSelectionPolicy(),
        "termination": MyTerminationPolicy(),
    },
)
```

This should be the primary extension path for researchers and downstream
developers.

### Configuration-based registration

Kora already has a `config.yaml` loading path for agent packages. Policy
configuration should integrate naturally with that shape.

Example:

```yaml
policies:
  compression:
    factory: mypkg.policies:SmartCompressionPolicy
  memory_retrieval:
    factory: mypkg.memory:RecencyAwareMemoryPolicy
  tool_selection:
    factory: mypkg.tools:SafeToolSelectionPolicy
  termination:
    factory: mypkg.runtime:BudgetAwareTerminationPolicy
```

This should resolve into the same runtime policy registry used by the
programmatic API.

## Proposed Architecture

Recommended dependency direction:

```text
Agent config
  -> policy registration map
  -> lifecycle stage binding
  -> runtime policy invocation
```

This implies three separable concerns:

### 1. Stage definition

Kora core defines the official lifecycle-stage names and contracts.

Examples:

- `compression`
- `memory_retrieval`
- `memory_write`
- `model_selection`
- `tool_selection`
- `tool_result_processing`
- `termination`
- `trace_sink`

### 2. Policy implementation

Users or official extensions provide the implementation object.

This object should satisfy a small stage-specific protocol.

### 3. Policy binding

Agent configuration decides which policy implementation is active for
which stage.

## Recommended Registration Model

### Option A: flat stage-to-policy map

Recommended initial design:

```python
policies={
    "compression": CompressionPolicy(...),
    "memory_retrieval": MemoryRetrievalPolicy(...),
}
```

Advantages:

- simple to understand
- easy to serialize into config
- easy to validate
- works well for one-policy-per-stage seams

This is the best default starting point.

### Option B: named policy registry plus references

Possible future shape:

```python
policy_registry.register("smart-compression", SmartCompressionPolicy())

agent = Agent(
    ...,
    policies={
        "compression": "smart-compression",
    },
)
```

This may become useful later for:

- shared named strategies
- agent package distribution
- reusable official presets

But it is not necessary for the first version.

## Recommended Stage Set for Initial Support

The first configurable stages should be the ones with the best mix of:

- high research value
- low ambiguity
- good fit with the current Kora architecture

Recommended initial stages:

- `compression`
- `memory_retrieval`
- `memory_write`
- `model_selection`
- `tool_selection`
- `tool_result_processing`
- `termination`
- `trace_sink`

These are strong initial candidates because they are both strategically
important and narrow enough to define small interfaces.

## Policy Interface Shape

The framework should avoid one universal policy base class.

Instead, each stage should have its own small contract.

### Example direction

Instead of:

```python
class AgentHook:
    def before_run(...): ...
    def after_run(...): ...
    def before_model(...): ...
    def after_model(...): ...
```

prefer:

```python
class CompressionPolicy(Protocol):
    def should_compress(self, stats: CompressionStats) -> CompressionDecision:
        ...
```

```python
class ToolSelectionPolicy(Protocol):
    def select_tools(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        ...
```

This keeps each seam understandable in isolation.

## Configuration Model

Kora already has a machine-readable agent configuration path via
`config.yaml`. Policy configuration should fit that model rather than
requiring a second unrelated configuration system.

### Proposed config shape

```yaml
model:
  provider: openai
  name: gpt-5.5

compression:
  enabled: true
  threshold_ratio: 0.8

policies:
  compression:
    factory: mypkg.policies:SmartCompressionPolicy
  model_selection:
    factory: mypkg.routing:CostAwareModelSelectionPolicy
    config:
      preferred_models:
        - openai/gpt-5.5-mini
        - anthropic/claude-sonnet
  termination:
    factory: mypkg.runtime:BudgetTerminationPolicy
    config:
      max_tool_rounds: 12
```

### Recommended semantics

- `factory` points to an importable constructor or class
- `config` is an opaque dictionary passed to the factory
- if a stage is omitted, Kora uses its built-in default
- if a stage name is unknown, configuration validation should fail

## Programmatic API Design

The programmatic API should remain the canonical interface.

Recommended direction:

```python
agent = Agent(
    ...,
    policies={
        "compression": SmartCompressionPolicy(),
        "termination": BudgetTerminationPolicy(max_tool_rounds=12),
    },
)
```

This should be equivalent in behavior to config-based registration.

The config loader should simply resolve configured policies and inject
them into the same agent construction path.

## Default and Override Semantics

To keep the system predictable, policy precedence should be explicit.

Recommended order:

1. framework default
2. official package override
3. agent package config override
4. explicit programmatic override

This means:

- users can override a default without replacing everything
- agent packages can ship recommended strategies
- local Python code can still take precedence for experiments

## Validation Rules

Policy binding should be validated before execution starts.

Recommended validation:

- stage names must be recognized
- the object bound to a stage must satisfy the expected stage protocol
- duplicate bindings should follow explicit override precedence
- config-based factories must resolve clearly or fail fast

This is important because research users need predictable failure modes.

## Interaction with Existing Kora Architecture

The current Kora architecture already suggests where this should fit.

### Agent

`Agent` is the most natural top-level place for policy registration,
because it already owns:

- tools
- model
- storage
- compression policy

Long term, existing single-purpose fields such as
`compression_policy` can be generalized into a broader policy binding
surface without breaking current behavior immediately.

### Host loader

`config.yaml` loading is already handled in the Host layer. That makes
it the natural place to resolve policy factories from configuration.

### Runtime

Runtime is the best place to invoke most policies, because it already
orchestrates:

- context assembly
- session execution
- compression
- loop control

### Kernel

Kernel should remain small. It should consume stage-specific decisions,
not become the main policy-registration surface.

## Backward Compatibility

This should be introduced incrementally.

Recommended compatibility strategy:

- keep existing dedicated fields such as `compression_policy`
- allow the new `policies` map to coexist with them temporarily
- define clear precedence when both are set
- migrate individual seams one at a time

This keeps current users working while opening the broader extension
model.

## Risks

### Risk 1: Too many configurable stages too early

If the first version exposes too many stages, users will be overwhelmed
and interfaces will be unstable.

Mitigation:

- start with a small initial stage set
- keep stage-specific protocols narrow

### Risk 2: Configuration becomes too magical

If config-based factories become opaque, users will struggle to debug
what is actually active.

Mitigation:

- keep config explicit
- validate eagerly
- expose active-policy summaries in diagnostics

### Risk 3: Policy interfaces drift into one giant abstraction

If all stages are forced into one universal hook class, the system will
become harder to reason about.

Mitigation:

- keep stage-specific protocols
- separate policy, middleware, and observer roles

## Recommended Near-Term Plan

### Phase 1

- define official lifecycle-stage names
- introduce a top-level `policies` binding model
- support programmatic registration first

### Phase 2

- extend `config.yaml` to support policy factories
- validate stage bindings in the loader
- expose diagnostics for active policy configuration

### Phase 3

- generalize beyond compression
- add official default policies for high-value stages
- publish extension examples for downstream agent authors

## Final Recommendation

Kora should make lifecycle strategy extension feel lightweight:

- users write a small policy object
- users bind it to a named stage
- configuration activates it
- the framework invokes it at the correct time

This is both more usable for downstream agent builders and more aligned
with a Unix-style framework than requiring users to patch core runtime
logic or adopt a large inheritance hierarchy.
