# Quenda Technology Radar and Architecture Decision Framework

> Purpose: guide long-term architecture choices, evaluate external solutions,
> and keep project decisions consistent with Quenda's layered design.

## 1. Why this exists

Quenda is still early enough that the biggest risk is not missing features.
The bigger risk is accumulating inconsistent abstractions, tooling, and
documentation while the product surface is still forming.

This document defines how we evaluate technical options before adoption.
It is intentionally opinionated.

## 2. Decision principles

Any proposal should be judged against these principles:

- Keep public API surface small and unsurprising.
- Prefer ordinary files and explicit protocols over opaque frameworks.
- Keep Kernel deterministic, synchronous, and easy to test.
- Keep Runtime async, but free of persistence, tenancy, and auth concerns.
- Keep Host responsible for persistence, identity, permissions, and shared resources.
- Favor composable primitives over large magical abstractions.
- Add complexity only when a real use case already exists.
- Preserve the official Code Agent's parity with external agents.

If a proposal violates one of these principles, it needs a strong reason.

## 3. Architecture boundaries

We should classify every new idea by the layer that owns it.

### Kernel

Owns:

- model-tool loop semantics
- tool execution order and stop conditions
- response normalization
- deterministic behavior for tests

Does not own:

- persistence
- authentication
- workspace discovery
- UI concerns
- provider-specific auth resolution

### Runtime

Owns:

- Agent and Session semantics
- async orchestration
- event emission
- run lifecycle

Does not own:

- database-specific persistence
- tenant policy
- auth infrastructure
- rendering

### Host

Owns:

- agent loading and composition before Runtime execution
- persistence adapters
- identity and tenancy
- permissions
- workspace trust
- workspace identity and binding validation
- user-agent-workspace state resolution
- shared resources
- Skill discovery and loading

Does not own:

- kernel execution semantics
- Runtime Agent/Session/Run semantics
- UI, CLI, server, or desktop app behavior
- provider protocol internals
- tool implementation details
- plugin marketplace distribution

## 4. Evaluation lenses

Every proposal should be reviewed through these lenses.

### 4.1 User value

Questions:

- What concrete problem does this solve?
- Who benefits first?
- Is this a core workflow or an edge case?

Decision rule:

- If the benefit is not clear and near-term, defer it.

### 4.2 Architectural fit

Questions:

- Which layer owns this?
- Does it move responsibility inward or outward?
- Does it blur boundaries that are currently clean?

Decision rule:

- If it requires cross-layer leakage to work, redesign it or reject it.

### 4.3 Complexity cost

Questions:

- What new concepts are introduced?
- What maintenance burden does this add?
- What will contributors need to understand before using it?

Decision rule:

- If it increases concepts faster than it increases leverage, keep it out.

### 4.4 Testability

Questions:

- Can we test it with deterministic fakes?
- Can we verify behavior without network access?
- Does it make regression testing harder or easier?

Decision rule:

- If it weakens deterministic testing, it needs a compensating benefit.

### 4.5 Compatibility

Questions:

- Does it break current public APIs?
- Can it be introduced in a backward-compatible way?
- Is a migration path needed?

Decision rule:

- Public API breaks require an explicit migration story.

### 4.6 Operational risk

Questions:

- Does it introduce new runtime dependencies?
- Does it complicate setup, packaging, or deployment?
- Does it increase security exposure?

Decision rule:

- If operational burden is high, the proposal must be a core capability.

## 5. Adoption radar

Use this four-zone radar for external technologies and internal proposals.

### Adopt now

Criteria:

- clearly solves a current problem
- low integration risk
- matches project principles
- easy to test and explain

Examples of the kind of thing that belongs here:

- well-scoped storage adapters for Host
- lightweight observability primitives
- minimal compatibility layers that preserve existing behavior

### Trial

Criteria:

- promising but not yet proven in Quenda's workflow
- small enough to pilot without locking in architecture
- can be isolated behind an interface

Examples:

- alternative persistence backends
- workspace binding validation rules
- user-agent-workspace storage layouts
- Host-owned metadata protection and tool permission policy
- optional transport mechanisms for events
- new provider protocols with limited scope
- local Skills capability packages based on `SKILL.md`

### Assess

Criteria:

- potentially useful, but unclear payoff
- significant design tradeoffs
- needs exploration before commitment

Examples:

- multi-agent coordination models
- memory systems
- streaming protocols beyond the simplest current path
- third-party Skill distribution and trust models

### Hold

Criteria:

- not necessary yet
- too much complexity
- would distract from current stabilization goals

Examples:

- broad framework abstraction layers
- generalized plugin ecosystems too early
- exotic deployment targets before the CLI is stable
- automatic remote Skill installation before Host trust controls exist

## 6. Recommendation matrix

When comparing alternatives, score each option from 1 to 5.

| Criterion | Weight | What good looks like |
|----------|--------|----------------------|
| User value | High | solves a real current workflow |
| Layer fit | High | stays within the owning layer |
| Testability | High | easy to verify deterministically |
| Compatibility | High | preserves current public behavior |
| Simplicity | High | minimal new concepts |
| Operational cost | Medium | low setup and maintenance burden |
| Extensibility | Medium | leaves room for known next steps |

Suggested decision rule:

- Prefer the option with the highest weighted score.
- If two options are close, choose the simpler one.
- If an option is more powerful but materially harder to test, defer it unless the power is required now.

## 7. Architecture decision checklist

Before approving a proposal, ask:

1. What problem are we solving?
2. Which layer owns it?
3. What is the smallest complete solution?
4. What does this change break?
5. How will we test it?
6. What is the migration path?
7. What is the rollback story?
8. What documentation must change with it?

If any of these are unclear, the proposal is not ready.

## 8. Red flags

Treat these as warning signs:

- introducing a new abstraction before a concrete use case exists
- moving framework responsibilities into user code
- adding “just in case” extensibility at the public API boundary
- mixing provider concerns into runtime semantics
- making the Kernel aware of outer-layer policy
- shipping docs that describe a future state as if it were current
- adopting tools because they are popular rather than because they fit

## 9. Recommended review output format

When I evaluate a technical proposal, I will usually respond in this structure:

- Summary
- Fit with Quenda's architecture
- Tradeoffs
- Risks
- Recommendation
- Next validation step

That format keeps us focused on decisions rather than implementation noise.

## 10. How to use this in practice

For any new architecture or tool proposal:

1. Classify it as Kernel, Runtime, Host, or external support.
2. Score it against the matrix.
3. Identify short-term and long-term costs.
4. Decide whether it belongs in Adopt now, Trial, Assess, or Hold.
5. Record durable choices in `docs/decisions/` when the decision matters long-term.

## 11. Current project stance

For Quenda today, the likely priority order is:

1. Stabilize the environment and documentation.
2. Lock the provider contract.
3. Finish the minimal Host persistence story.
4. Improve ergonomics only after the foundation is stable.

That sequencing keeps the project aligned with its own constitution.

## 12. Skills stance

Skills should be treated as a Trial item, not an adopted core abstraction.

The recommended direction is:

- adopt the `SKILL.md` directory convention where practical
- keep discovery, trust, loading, and resource access in Host
- keep Kernel unaware of Skills
- keep Runtime focused on Agent/Session/Run semantics
- start with local, trusted workspace Skills
- defer marketplace, remote installation, and automatic script execution

See [docs/decisions/002-skills-capability-packages.md](decisions/002-skills-capability-packages.md).
