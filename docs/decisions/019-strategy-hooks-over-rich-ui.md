# ADR-019: Prioritize Strategy Hooks Over Rich UI

## Status

Proposed (2026-06-26)

## Context

Quenda already includes a usable default interaction surface:

- REPL
- slash commands
- selector
- interaction request handling

These are useful for demos, local workflows, and a good single-agent
default experience.

However, if Quenda's long-term goal is to become:

- an extensible agent framework
- infrastructure for downstream specialized agents
- a substrate for multi-agent systems
- a runtime for strategy experimentation and agent research

then rich UI should not be the main architectural priority.

The more important questions are:

- can downstream agents reliably hook into key execution stages
- does the framework separate mechanism from strategy
- are defaults simple enough to be replaced
- can good strategies be promoted into official implementations or
  configurable modules over time

Recent agent research reinforces this direction. The center of gravity
is increasingly:

- interleaved reasoning and acting
- tool-use policy
- long-term memory
- reflection and verification
- search and workflow optimization
- trajectory-level training and evaluation
- agent safety, especially memory and tool risk

not terminal UI, slash-menu richness, or front-end interaction details.

## Decision

Quenda should evolve primarily as a **hookable, policy-driven agent
framework**, rather than primarily as a richer REPL / menu / command UI
system.

Recommended principle:

- **Core provides stages, protocols, and default implementations**
- **agents and extensions provide strategies**
- **mature strategies flow back into official implementations or
  configurable modules**

This implies:

- UI remains important, but is treated as a default or reference
  implementation
- core evolution should focus on lifecycle hooks, policy seams, and
  trace surfaces
- multi-agent orchestration should continue to live above core

## Why This Direction Matters

### 1. It matches the long-term role of an agent framework

The enduring value of an agent framework is not whether its default UI
is rich. It is whether the framework can host different agent strategies
and research patterns cleanly.

### 2. It aligns better with research-community needs

Recent work consistently emphasizes:

- intertwined reasoning and acting loops
- memory retrieval, writing, deletion, and compression
- tool selection and tool interface quality
- reflection, verification, and repair
- search, backtracking, and workflow optimization
- structured trajectory export for training and evaluation

These concerns all require stable lifecycle seams.

### 3. It prevents default UX from defining framework boundaries

If REPL, menus, selectors, and UI-centric abstractions become dominant
too early, the framework starts inheriting the shape of one default
front-end.

The better rule is:

- front-ends consume framework capabilities
- front-ends do not define framework capabilities

### 4. It helps future multi-agent and training systems integrate cleanly

Upper-layer multi-agent systems and training systems care more about:

- standardized trajectories
- pluggable strategies
- clear intermediate state
- exportable observations

than about command-line completion details.

## Design Principles

Future core evolution should follow these principles.

### 1. Mechanism over policy

The framework should provide mechanisms:

- lifecycle stages
- state objects
- data protocols
- default implementations

Policy should remain with agents or extension layers.

### 2. Stable seams over ad-hoc callbacks

The project should avoid scattering one-off callbacks throughout the
runtime.

Preferred forms:

- typed policy interfaces
- middleware-style wrappers
- structured observer hooks

### 3. Simple default, rich extension

Default behavior should remain understandable and replaceable.

Complex strategies should be validated in downstream agents or official
extensions before becoming part of core.

### 4. Multi-agent stays above core

Multi-agent orchestration remains an upper-layer concern.

Core should provide:

- reliable single-agent execution
- lifecycle hooks
- trace and state surfaces

It should not directly absorb orchestration logic.

## What Core Should Prioritize

Core should prioritize:

- context assembly hooks
- memory policy hooks
- tool-use hooks
- reflection / verification hooks
- termination / budget hooks
- persistence / compression hooks
- trace / observability hooks

These have substantially higher long-term value than richer slash-menu
navigation, selector animations, or REPL polish.

## What Should Remain Default Implementations

The following should continue to exist, but mainly as default or
reference implementations:

- REPL
- slash command system
- selector
- interaction UI
- status bar and terminal UX

These matter for usability, but should not be the main driver of core
abstraction design.

## Relationship to Existing ADRs

This direction is consistent with recent architectural decisions:

- `ADR-015` already treats compression as a policy seam
- `ADR-017` already keeps multi-agent orchestration out of core
- `ADR-018` already prevents provider payloads from defining core
  abstractions

This ADR extends those principles into agent-strategy design.

## Consequences

### Positive

- gives Quenda a clearer framework identity
- better supports downstream agents and research extensions
- makes strategy comparison and promotion easier
- improves compatibility with evaluation, training, and optimization
  workflows
- prevents UI abstractions from becoming architectural drivers

### Negative

- user-visible interaction improvements may ship more slowly in the
  short term
- designing stable hook seams requires care
- the framework surface will gain some abstraction cost

### Risks

- if hooks are too granular, abstraction noise increases
- if hooks are too coarse, research extensibility suffers
- if policies and observers are not separated clearly, the system may
  degrade into callback soup

## Recommendation

Quenda should make its next core investment in:

- lifecycle hooks
- policy extension points
- structured traces
- official strategy implementations

not in richer UI and command-navigation infrastructure.

UI should continue to exist, but primarily as a default front-end rather
than the main architectural axis.
