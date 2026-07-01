# Host Text Refresh and Capability Binding Flow

## Status

Implementation-ready draft (2026-06-30)

## Purpose

This document turns the newer skill and reload ADRs into one concrete
Host execution model.

It is intentionally narrow. Its purpose is not to introduce more
concepts. Its purpose is to define:

- what Host should do before each run
- what Host should only do at setup or explicit rebind time
- what data should be durable vs run-scoped

This document builds directly on:

- [ADR-020: Runtime Terminology and Execution Units](/Users/xushiting/Workspace/kora/docs/decisions/020-runtime-terminology-and-execution-units.md)
- [ADR-025: Skill Lifetime and Prompt Residency](/Users/xushiting/Workspace/kora/docs/decisions/025-skill-lifetime-and-prompt-residency.md)
- [ADR-026: Textual Context Reload and Capability Rebind](/Users/xushiting/Workspace/kora/docs/decisions/026-textual-context-reload-and-capability-rebind.md)

## Scope

This draft only covers Host-side preparation for a run.

It does not redesign:

- Runtime lifecycle
- Kernel loop semantics
- automatic skill routing algorithms
- permission policy UX

## One-Sentence Model

Host should have two separate preparation paths:

1. a **text refresh path** that runs before every new run
2. a **capability binding path** that runs only at setup or explicit
   rebind time

## Execution Boundary

In current Kora terms:

- one new user input normally creates one new `Run`
- that run normally corresponds to one user-facing `Turn`

So "reload at turn boundary" operationally means:

- **run the text refresh path before starting the next run**

## Host State Model

Host should separate stable state from run-scoped resolved state.

### Stable session or setup state

These values should survive across runs until explicitly rebuilt:

- resolved model/provider binding
- granted tool set
- sandbox configuration
- policy wiring
- `active_skill_names`
- session identity and workspace binding

### Run-scoped resolved state

These values should be rebuilt before each run:

- `AGENT.md` text snapshot
- included instruction file snapshots
- workspace overlay instruction snapshots
- discovered skill catalog snapshot
- resolved `SkillPackage` objects for active or selected skills
- applied skill instruction snapshot
- any loaded skill resource content used in that run

## Path A: Text Refresh Path

This path should execute before every new run.

### Inputs

- agent package path
- workspace path and user scope paths
- current `active_skill_names`
- current session state

### Steps

1. Re-read `AGENT.md`
2. Re-read agent-declared instruction files
3. Re-read workspace and user instruction overlays
4. Re-scan skill discovery locations
5. Re-resolve current active skills by name
6. Compose the effective instruction snapshot for the new run
7. Load skill resource contents only if the current run actually needs
   them

### Outputs

- a fresh prompt/context snapshot for the new run
- a fresh skill catalog view for routing and presentation
- fresh applied-skill snapshots for the run

### Key rules

- this path must be safe to run every turn
- this path must not silently change granted tools or model wiring
- this path must not mutate capabilities mid-run

## Path B: Capability Binding Path

This path should execute only when the session or agent binding is being
created, or when an explicit rebind is requested.

### Inputs

- capability-affecting `config.yaml`
- extension module discovery
- host policy and permission environment

### Steps

1. Load capability-affecting config
2. Resolve model/provider binding
3. Resolve tool bundles and named tools
4. Resolve sandbox grants
5. Resolve runtime policy bindings
6. Produce the stable capability snapshot for subsequent runs

### Outputs

- bound model/provider
- granted tools
- sandbox configuration
- policy instances or factories

### Trigger conditions

This path should run on:

- initial agent setup
- explicit reload or rebind command
- agent/session restart
- future host-driven refresh APIs

It should not run automatically just because a user edited a text file.

## Recommended Data Shape

The Host layer should move toward a state model like this:

```text
StableHostBinding
  model_binding
  granted_tools
  sandbox_config
  policy_bindings
  active_skill_names
  workspace_binding
  identity

RunContextSnapshot
  agent_md_text
  instruction_texts
  discovered_skills
  resolved_active_skills
  applied_skill_instructions
  loaded_skill_resources
```

The key design point is:

- durable state tracks intent and granted capabilities
- run snapshots track prompt material

## Current Codebase Alignment

The current codebase is close to this split, but not fully aligned yet.

### Already aligned

- capability resolution is mostly Host-owned
- skill activation already exists as an explicit state concept
- context rebuild already exists as a Host-owned operation

### Needs convergence

1. `SkillActivator` should primarily own active skill names, not treat
   loaded skill objects as long-lived truth
2. `ContextRebuilder` should rebuild from freshly resolved active skills
   on each run
3. skill discovery cache should not act as unconditional session truth
4. text refresh and capability binding should become visibly distinct
   code paths

## Immediate Implementation Tasks

This document intentionally narrows the next work to four finite tasks.

### Task 1. Split Host setup into two explicit paths

Introduce a clear separation between:

- one-time or explicit capability binding
- per-run text refresh

This can be done without redesigning Runtime or Kernel.

### Task 2. Change skill activation durable state to names

Prefer:

```text
active_skill_names: list[str]
```

over durable storage of loaded `SkillPackage` snapshots.

### Task 3. Re-resolve active skills during context rebuild

At each new run:

1. read active skill names
2. rediscover or refresh skill metadata
3. resolve the latest `SkillPackage` objects
4. compose prompt input from those fresh objects

### Task 4. Add one explicit rebind entrypoint

Provide one Host-level mechanism for capability refresh, such as:

- restart session
- explicit reload command
- explicit rebind API

Phase 1 only needs one clear mechanism, not a complete UI.

## Out Of Scope For This Track

To keep this work bounded, the following should not be expanded in the
same implementation track:

- automatic model-driven skill routing
- skill marketplace or remote installation
- dynamic in-run capability mutation
- full policy hot-swap system
- new runtime phases

## Recommended Stop Point

This design track should be considered complete when Kora can do all of
the following:

1. edit `AGENT.md` and see the change on the next user message
2. add or edit a skill and see it on the next user message
3. keep tool/model/sandbox bindings stable until an explicit rebind
4. explain those semantics consistently in code and docs

At that point, the next step should be implementation and tests, not
further concept expansion.
