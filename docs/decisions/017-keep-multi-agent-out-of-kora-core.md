# ADR-017: Keep Multi-Agent Out of Quenda Core

## Status

Proposed

## Context

Quenda is evolving into a layered single-agent framework with clear
boundaries:

```text
Interface -> Host -> Runtime -> Kernel
```

Its strongest current value comes from making one agent reliable,
inspectable, and composable:

- model-tool loop execution
- session and run lifecycle
- tool registration and safety boundaries
- instruction composition
- persistence
- context compression
- session branching

At the same time, multi-agent systems are an attractive direction. They
promise:

- planner / worker workflows
- reviewer / implementer loops
- specialist delegation
- parallel task decomposition

However, multi-agent orchestration introduces a different class of
complexity:

- agent-to-agent communication
- task routing
- shared state or memory coordination
- failure recovery across agents
- branch and session relationships between agents
- scheduling and cancellation semantics

These concerns are materially different from the core problem Quenda is
currently solving.

## Decision

Quenda core should remain a **single-agent framework**.

Multi-agent orchestration should be implemented in a **separate
upper-layer library or package**, built on top of Quenda's public
primitives rather than folded into the core package.

In practical packaging terms, the preferred direction is:

- `quenda`: core framework
- `quenda-code`: official coding agent
- future package such as `quenda-multiagent` or `quenda-orchestrator`:
  optional multi-agent orchestration layer

## Why This Boundary Matters

This separation keeps Quenda focused on the smallest complete problem:

- how one agent should run correctly
- how one session should persist and evolve
- how one Host environment should load, authorize, and store execution
  state

If multi-agent orchestration is introduced too early into core, several
risks appear:

- core APIs become larger and less predictable
- Runtime starts absorbing orchestration semantics that do not belong to
  single-agent execution
- Host may need new coordination concepts before persistence and branch
  semantics are stable
- contributors must understand far more concepts before using the
  framework effectively

## Layer Fit

Multi-agent orchestration does not fit cleanly into the existing inner
layers.

### Kernel

Kernel should remain unaware of:

- multiple agents
- delegation
- agent routing
- orchestration graphs

Kernel only owns one model-tool loop.

### Runtime

Runtime should continue to own:

- one Agent
- one Session
- one Run lifecycle

It should not grow into a generalized multi-agent scheduler or router.

### Host

Host may eventually help configure or launch orchestrated systems, but it
should not force every Quenda consumer to adopt multi-agent concepts as
part of the base framework.

## Recommended Architecture

The correct dependency direction is:

```text
quenda-multiagent
  -> quenda
```

Not:

```text
quenda
  -> internal multi-agent orchestration layer
```

That means the multi-agent layer should consume Quenda primitives such as:

- Agent
- Session
- Run
- events
- Host persistence and branch facilities
- tool and instruction systems

But the Quenda core package should not expose multi-agent orchestration as
one of its default responsibilities.

## What Core Should Provide Instead

Keeping multi-agent out of core does not mean ignoring future
orchestration needs.

Core should provide clean primitives that make orchestration possible
later:

- stable single-agent execution semantics
- durable session state
- branchable conversation state
- observable run events
- explicit Host-owned persistence
- composable tool and instruction loading

These primitives are more valuable long-term than prematurely adding a
first multi-agent abstraction that later proves wrong.

## What the Separate Multi-Agent Package Can Own

A future orchestration package can explore:

- planner / worker patterns
- reviewer loops
- agent handoff protocols
- delegation tools
- shared work queues
- coordination policies
- orchestration UIs or traces

This lets the orchestration layer evolve faster without destabilizing
Quenda core.

## Relationship to Roadmap

Multi-agent should move from "core framework feature" to "future
extension layer".

That means:

- it can stay on the roadmap
- it should not be treated as a requirement for Quenda core maturity
- core stabilization should proceed without waiting for it

## Non-Goals

This ADR does not define:

- the exact API of a future multi-agent package
- how agents delegate to each other
- whether orchestration is graph-based, queue-based, or tool-based
- packaging name choices for the future extension

Those questions belong to the future orchestration layer, not to the
core framework boundary.

## Consequences

### Positive

- keeps core API smaller and clearer
- protects Runtime and Host boundaries from orchestration creep
- reduces maintenance burden in the core package
- allows faster experimentation in a separate package
- aligns with Quenda's current real strengths

### Negative

- users wanting multi-agent workflows need an additional package later
- some future abstractions may need careful bridging APIs
- orchestration demos may feel less "all in one" in the short term

## Recommendation

Quenda should explicitly define itself as a single-agent framework.

Multi-agent coordination should be treated as an optional upper-layer
package built on top of Quenda, not as part of Quenda core itself.

