# ADR-022: Keep Core Minimal and Push Strategies to Policies

## Status

Proposed (2026-06-29)

## Context

Quenda is intentionally moving toward a hookable, policy-driven agent
framework.

That direction creates an immediate architectural tension:

- richer hooks can improve research flexibility
- more lifecycle states can improve conceptual clarity
- more policy seams can improve downstream extensibility

but all three can also make the framework feel heavier if they are
implemented carelessly.

The main risk is not the existence of hooks themselves. The main risk is
allowing strategy logic, experimental methods, and product-specific
behavior to drift into core until the default framework stops feeling
simple.

Recent design work already established several related principles:

- `ADR-017` keeps multi-agent orchestration out of Quenda core
- `ADR-019` prioritizes strategy hooks over richer UI
- `ADR-020` defines stable runtime terminology
- `ADR-021` defines an explicit runtime lifecycle and state machine

The next required decision is a stricter boundary rule:

- what core is responsible for
- what should remain outside core
- how official implementations should fit into the system

Without that boundary, Quenda risks becoming a framework that is
conceptually extensible but operationally opinionated and difficult to
replace.

## Decision

Quenda core should remain a **minimal single-agent runtime** with
**research-grade extension seams**, while concrete agent strategies
should live in policies, middleware, observers, or official extension
packages rather than in core.

The guiding rule is:

- **core defines execution stages, protocols, defaults, and safety
  guards**
- **policies and extensions define strategy**

Quenda should therefore optimize for:

- a short default execution path
- small, named extension seams
- replaceable strategy implementations
- official reference implementations outside the core runtime logic

In short:

**simple by default, extensible by design**

## What Must Stay In Core

The following responsibilities belong in core.

### 1. Execution mechanism

Core should own the minimal machinery required to run an agent:

- session and run lifecycle
- context assembly pipeline shape
- model invocation mechanism
- tool execution mechanism
- loop control and legal state transitions
- interruption handling
- failure handling

Core should define how execution happens, not which advanced strategy is
best.

### 2. Stable lifecycle stages

Core should define named lifecycle stages and transition boundaries,
such as:

- compression check
- context preparation
- model invocation
- tool phase
- loop decision
- completion / termination / interruption / failure

Optional future states may exist in the lifecycle model, but they should
not become mandatory runtime work unless enabled.

### 3. Small extension protocols

Core should define small contracts for extension seams, for example:

- `CompressionPolicy`
- `TerminationPolicy`
- `ToolSelectionPolicy`
- `ToolResultProcessingPolicy`
- `TraceSink`

These interfaces should be narrow, typed, and stage-specific.

### 4. Hard safety guards

Core should keep non-optional execution guards that prevent runaway or
unsafe runtime behavior even when no custom policy is configured.

Examples include:

- iteration limits
- cancellation propagation
- required validation of tool requests
- invariants around run state transitions

These are engine protections, not user strategy.

### 5. Minimal defaults

Core should provide working defaults so that a user can instantiate an
agent without configuring advanced policies.

Default behavior should remain:

- understandable
- conservative
- replaceable

## What Must Stay Out Of Core

The following responsibilities should not be embedded into core runtime
logic.

### 1. Research strategies

Research-oriented methods should live in policy implementations or
extensions, not in the engine itself.

Examples:

- custom verification heuristics
- reflection and retry strategies
- self-critique loops
- ranking or reranking policies
- search and backtracking strategies
- debate, voting, or ensemble methods

Core may host the seam, but not the experiment.

### 2. Product or domain policy

Behavior that reflects one product's constraints or one domain's goals
should remain outside core.

Examples:

- vertical-specific tool gating
- organization-specific memory retention rules
- domain-specific success criteria
- custom escalation or approval policy
- tenant-specific compliance logic

These are deployment policies, not framework fundamentals.

### 3. Rich memory strategy

Core may define memory read/write seams, but it should not hard-code
particular memory intelligence.

Examples that should remain outside core:

- retrieval ranking strategy
- salience estimation
- writeback heuristics
- compaction or forgetting policy
- long-horizon memory graph design

### 4. Verification and reflection semantics

Core may define lifecycle slots such as `VerificationRunning` or
`ReflectionRunning`, but the substantive logic for:

- what to verify
- how to score sufficiency
- when to retry
- when to reflect
- how many retries are allowed

should remain policy-owned.

### 5. Tool-use strategy

Core may validate and execute tools, but it should not hard-code higher
level tool strategy.

Examples that should stay outside core:

- allowlist / denylist policy
- risk-based gating
- approval workflows
- result truncation strategy
- no-progress detection based on tool history
- tool result repair or summarization heuristics

### 6. Multi-agent orchestration

Multi-agent planning, delegation, voting, supervision, and coordination
should continue to live above core, consistent with `ADR-017`.

### 7. Rich UI behavior as an architectural driver

REPL, slash commands, selectors, and future interface affordances should
remain default consumers of runtime capabilities.

They should not define core abstractions or runtime control flow.

## Official Implementations

Quenda should distinguish clearly between:

- core protocols
- core defaults
- official implementations
- third-party implementations

### Core defaults

Core defaults exist so the framework works out of the box.

They should be:

- small
- unsurprising
- low-policy

### Official implementations

Official implementations are maintained by the project, but should be
treated conceptually as replaceable strategy modules rather than as
engine requirements.

Examples:

- a token-budget termination policy
- a standard JSONL trace sink
- a conservative tool selection policy
- a reference verification policy

Official implementations may ship with the repository, but they should
still respect the same public contracts that downstream users use.

### Third-party implementations

Downstream users should be able to provide their own implementations by:

- writing a small policy object
- registering it programmatically
- binding it through agent configuration

No core patching should be required.

## Promotion Rule

When a strategy becomes popular or useful, Quenda should not immediately
move it into core.

The preferred promotion path is:

1. experiment outside core
2. stabilize the protocol
3. publish an official implementation
4. keep it replaceable
5. move only the minimal shared mechanism into core if strictly needed

This preserves framework simplicity while still allowing strong defaults
to emerge.

## Design Tests For Future Proposals

Any proposal that adds behavior to Quenda should be checked against the
following questions.

### 1. Is this mechanism or strategy?

If it is strategy, it probably does not belong in core.

### 2. Does it need to be mandatory?

If the system still works without it, it should likely be optional.

### 3. Can it be expressed as a small stage-specific contract?

If yes, prefer a policy seam over embedding the behavior directly into
runtime flow.

### 4. Would downstream users reasonably want to replace it?

If yes, it should not be hard-coded.

### 5. Does it couple unrelated phases together?

If yes, the design is probably too heavy for core.

### 6. Is it a framework invariant or a preferred policy?

Framework invariants belong in core.

Preferred policies belong in defaults or official implementations.

## Relationship To Unix-Style Design

This decision is aligned with a Unix-style philosophy for agent
frameworks.

Quenda core should aim to be:

- small in mandatory behavior
- explicit in interfaces
- composable in extension points
- conservative in baked-in policy

In this model:

- lifecycle stages are the pipes
- protocols are the contracts
- policies are interchangeable components

The system becomes more capable without requiring the runtime engine
itself to become large or over-opinionated.

## Consequences

### Positive

- preserves Quenda as a simple default agent framework
- gives researchers and downstream developers clean replacement seams
- reduces pressure to merge experimental logic into runtime core
- makes official strategies easier to compare against third-party
  strategies
- keeps the architecture aligned with `ADR-017` and `ADR-019`

### Negative

- more concepts must be documented clearly
- some users may initially want features that are intentionally kept out
  of core
- careful refactoring is required so that current implementations do not
  leak strategy into engine code

### Risks

- if core defaults become too smart, this boundary will erode in
  practice
- if too many tiny seams are introduced, the system may feel fragmented
- if official implementations are treated as mandatory, users may not
  perceive the framework as truly replaceable

## Follow-On Guidance

Future hook and policy work should follow this ADR by ensuring that:

- each new seam has a clearly named lifecycle stage
- each seam has a narrow responsibility
- core owns transition mechanics, not strategy semantics
- official implementations remain optional and replaceable
- advanced phases such as verification, reflection, and memory
  management are modeled as opt-in capabilities rather than default
  mandatory runtime behavior
