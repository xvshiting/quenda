# Quenda Development Constitution

Quenda is a lightweight Agent framework with an official Code Agent built on top of the same public APIs available to external developers.

## Core principles

* Keep Quenda simple to use, even when its internal architecture is layered.
* The framework must absorb common complexity instead of transferring it to Agent authors.
* Prefer convention over configuration.
* Prefer composition over inheritance.
* Prefer ordinary files and explicit protocols over opaque abstractions.
* Separate mechanism from policy.
* Add abstractions only when required by a concrete current use case.
* Keep public APIs small, stable, and unsurprising.

## Architectural boundaries

Quenda separates execution into three conceptual layers:

* **Kernel** executes one model–tool loop.
* **Runtime** manages Agent, Workspace, Session, Prompt, and Run semantics.
* **Host** is the trusted outer environment that loads, authorizes,
  persists, and composes Agent definitions before Runtime execution. It
  manages persistence, identity, tenancy, permissions, workspace trust,
  and shared resources.

Dependencies must point inward:

```text
Interface → Host → Runtime → Kernel
```

Lower layers must not depend on higher layers.

Kernel must not know about:

* Agent files
* Workspace discovery
* Sessions
* Users or tenants
* Databases
* TUI, Web, or Server interfaces
* Model configuration or API-key resolution

Runtime must not know about:

* Authentication
* Tenant ownership
* Billing
* Database-specific persistence
* UI rendering

Host must not own:

* Kernel model-tool loop semantics
* Runtime Agent, Session, Run, or event semantics
* UI rendering
* A specific CLI, web server, or desktop app
* Provider protocol internals
* Tool implementation logic
* Plugin marketplace distribution

## Public API

Normal users should only need concepts such as:

* `Agent`
* `Session`
* `tool`
* `run`

Internal concepts such as Kernel, Runtime, resolvers, adapters, registries, repositories, and providers must not be required for ordinary Agent definition.

A minimal Agent should be definable with an `AGENT.md` file.

## Agent equality

The official Quenda Code Agent must use the same public loading and execution mechanisms as external Agents.

Do not introduce privileged private APIs or special execution branches for the official Code Agent.

A requirement belongs in:

* Kernel, only if it is universal execution mechanism;
* Runtime, only if it is reusable Agent runtime semantics;
* the Code Agent, if it is code-specific behavior or policy.

## Execution rules

* Agent behavior must be grounded in actual model and tool results.
* Security boundaries must be enforced in code, not only through prompts.
* Workspace access must remain isolated to the configured root.
* Runs must be observable through structured events.
* Sessions must remain independent and must survive the completion of individual Runs.
* Kernel must be independently testable with deterministic fake models and tools.
* External model responses and tool errors must be normalized before entering core logic.

## Development rules

Before making a substantial change:

1. Read `docs/CURRENT.md`.
2. Read `TODO.md`.
3. Inspect the relevant implementation and tests.
4. Identify which architectural layer owns the change.

During implementation:

* Prefer the smallest complete change.
* Add tests with behavior changes.
* Do not implement speculative infrastructure.
* Do not silently cross established layer boundaries.
* Do not move framework responsibilities into user code merely to keep framework code small.

After substantial work:

* Update `TODO.md`.
* Update `docs/CURRENT.md`.
* Record durable architectural decisions under `docs/decisions/` when necessary.

## Decision test

Before introducing a new abstraction, ask:

1. Is it required by a current real use case?
2. Does it materially improve isolation, testing, replacement, or reuse?
3. Does it reduce total complexity rather than move complexity elsewhere?

If the answers are not clearly yes, defer it.

## Documentation boundaries

* `CLAUDE.md`: stable principles and non-negotiable boundaries.
* `TODO.md`: actionable unfinished work.
* `docs/CURRENT.md`: current design state, open questions, and next action.
* `docs/decisions/`: accepted architectural decisions.

Do not put temporary progress, detailed implementation plans, or frequently changing directory structures in this file.
