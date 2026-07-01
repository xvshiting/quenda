# ADR-026: Textual Context Reload and Capability Rebind

## Status

Proposed (2026-06-30)

## Context

Quenda now has enough architecture around Sessions, Runs, Skills, and
instruction layering that reload behavior needs to be made explicit.

Several recent questions all point to the same underlying ambiguity:

- should `AGENT.md` reload every turn?
- should a newly added skill be discoverable on the next user message?
- should edited `SKILL.md` content apply immediately?
- should `config.yaml` tool grants also change automatically on the next
  turn?

If Quenda answers all of these with the same rule, the model becomes
confusing.

Some inputs are primarily:

- textual context
- prompt composition sources
- routing metadata

Others are primarily:

- capability grants
- execution bindings
- security boundaries
- runtime wiring

Those two categories should not share the same reload semantics.

This ADR builds on:

- `ADR-002` Skills as Host-level capability packages
- `ADR-007` instruction layering and scope overlays
- `ADR-020` runtime terminology and execution units
- `ADR-025` skill lifetime and prompt residency

## Decision

Quenda should adopt a **two-class reload model**:

1. **Textual context reload at turn boundary**
2. **Capability rebind by explicit refresh**

The practical meaning is:

- text-like context inputs should be re-read before each new run
- capability-affecting configuration should not silently mutate at each
  turn

## Terminology Alignment

This ADR uses the `ADR-020` terms with the following practical mapping.

### Session

A multi-turn conversation container.

### Turn

A user-facing conversational unit.

In current Quenda usage, a new user message normally starts a new turn.

### Run

The runtime execution instance created for one new user message.

In today's design:

- one new user input usually creates one run
- one run usually corresponds to one turn

So when this ADR says "reload at turn boundary", the operational
meaning is:

- **before the next run begins for the next user input**

### Iteration

One internal model-tool loop advance inside a run.

This ADR does **not** recommend reloading prompt sources between
iterations inside a run.

## Two Reload Classes

### Class A. Textual context reload

These inputs should be re-read at each turn boundary because they are
part of prompt construction, routing, or user-editable guidance.

They are expected to feel editable.

### Class B. Capability rebind

These inputs affect what the agent is allowed or able to do, or how core
runtime components are wired.

They should not silently change at each turn because that would weaken:

- predictability
- reproducibility
- security understanding
- debugging clarity

## Rules

### Rule 1. Re-read textual context at each new run

Before each run starts, Host should re-resolve and re-read applicable
textual context sources.

This includes:

- agent instruction text
- workspace instruction text
- skill catalog metadata used for routing or display
- skill instruction bodies when applied
- resource metadata used for routing decisions

### Rule 2. Do not silently rebind capabilities at each turn

Capability-affecting inputs should remain stable for the current
session/runtime wiring unless an explicit refresh action occurs.

Examples:

- rebuilding the agent/session
- explicit reload or rebind command
- restarting the process
- creating a new run environment from updated configuration

### Rule 3. A turn boundary is outside the run, not inside it

Once a run starts:

- its instruction snapshot is fixed
- its active capability bindings are fixed

Quenda should not live-mutate prompt sources or capability grants halfway
through a run.

### Rule 4. New textual content should become visible on the next user
message

If a user edits text-based context files, the common expectation should
hold:

1. edit the file
2. send the next message
3. updated behavior appears in the next run

This applies to discovery changes too, such as adding a new skill
directory.

## Reload Matrix

| Source | Class | Default timing | Why |
|---|---|---|---|
| `AGENT.md` text | Textual context reload | Re-read before each new run | Agent guidance should feel editable |
| `instructions/*.md` declared by agent package | Textual context reload | Re-read before each new run | Prompt composition source |
| Workspace `INSTRUCTIONS.md` and overlays | Textual context reload | Re-read before each new run | User/workspace guidance should update quickly |
| Skill catalog metadata | Textual context reload | Re-scan before each new run | New or changed skills should be discoverable next turn |
| Applied `SKILL.md` instruction bodies | Textual context reload | Re-read when the skill is applied for the new run | Matches turn-boundary skill refresh |
| Skill resource metadata | Textual context reload | Re-read before or during selection for the new run | Supports progressive disclosure |
| Loaded skill resource content | Run-scoped prompt snapshot | Load on demand during the run, then expire | Large prompt payload, should stay ephemeral |
| `config.yaml` model/provider binding | Capability rebind | Explicit refresh only | Changes execution wiring |
| `config.yaml` tool bundle requests | Capability rebind | Explicit refresh only | Changes granted tool set |
| `config.yaml` custom tool includes | Capability rebind | Explicit refresh only | Changes model-visible executable surface |
| `execution.python.allowed_modules` | Capability rebind | Explicit refresh only | Security-sensitive execution boundary |
| Policy factories / extension module wiring | Capability rebind | Explicit refresh only | Affects runtime behavior, not just text |

## `AGENT.md` Semantics

`AGENT.md` should be treated as a textual context source, not as a
capability declaration file.

That means:

- edits to `AGENT.md` should take effect on the next user message
- `AGENT.md` should be re-read before each run
- `AGENT.md` should not itself silently grant tools, sandbox rights, or
  runtime policy bindings

This keeps it aligned with the instruction-layer model rather than the
capability-grant model.

## Skill Discovery Semantics

This ADR clarifies a common expectation:

- if a new skill appears on disk, the next turn should be able to see it

Therefore Host should re-scan skill discovery sources at turn
boundaries rather than treating the discovery catalog as session-frozen.

However:

- discovering a skill does not auto-activate it
- discovering a skill does not auto-load its full resources

That remains governed by skill activation and progressive disclosure.

## Why `config.yaml` Should Not Fully Hot Reload

It may be tempting to say "just re-read `config.yaml` every turn too".
That is too blunt.

Some `config.yaml` fields may contain textual or cosmetic values, but
many fields influence:

- model identity
- tool grants
- custom extension loading
- sandbox behavior
- runtime policy wiring

If those mutate silently between turns, users and downstream developers
lose a stable answer to:

- which tools were actually granted?
- which model was actually running?
- which policies were active for this session?

So the framework should prefer:

- easy next-turn editability for text
- explicit rebind for capabilities

## Future Extension

Later, Quenda may split `config.yaml` itself into finer categories, such
as:

- textual agent presentation config
- capability request config
- runtime binding config

If that happens, some non-sensitive textual fields may become eligible
for turn-boundary reload.

This ADR does not prevent that.

It only says capability-affecting fields must not be silently hot
reloaded by default.

## Recommended Implementation Direction

Host should move toward two distinct pre-run behaviors.

### 1. Text refresh path

At each turn boundary:

1. re-read `AGENT.md`
2. re-read included instruction files
3. re-scan skill catalogs
4. re-resolve active or selected skills
5. rebuild the effective prompt/context snapshot for the new run

### 2. Capability binding path

At agent/session setup time:

1. load capability-affecting configuration
2. resolve tool bundles and named tools
3. bind model/provider/runtime policies
4. keep those bindings stable for the session unless explicitly rebuilt

## Consequences

### Positive

- preserves the intuitive "edit text, next turn changes" experience
- prevents silent drift in tools and execution permissions
- aligns skill behavior with prompt-budget and reproducibility goals
- gives downstream agent authors a stable mental model

### Negative

- Host setup becomes more explicitly split into two phases
- some users may expect `config.yaml` edits to work like text edits
- implementation will need clearer caching and invalidation boundaries

## Recommendation

Use this ADR as the default reload contract for Host design.

The practical summary is:

- **prompt-layer sources reload at turn boundaries**
- **capability-layer sources require explicit rebind**

That should be the baseline assumption for future work on Skills,
instruction composition, tool grants, and agent package ergonomics.
