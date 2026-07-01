# ADR-025: Skill Lifetime and Prompt Residency

## Status

Proposed (2026-06-30)

## Context

Kora already established several important skill decisions:

- `ADR-002` places Skills at the Host layer
- `ADR-007` defines the broader instruction layering model
- [skill-turn-boundary-reload-semantics.md](/Users/xushiting/Workspace/kora/docs/architecture/skill-turn-boundary-reload-semantics.md)
  recommends turn-boundary refresh rather than live hot reload

However, one important part is still underspecified:

- when skill instructions enter the prompt
- when skill resources enter the prompt
- when those contents should leave the prompt again

Right now, the language around "loading a skill" is too ambiguous.
Different things are being conflated:

- discovering that a skill exists
- marking a skill as active
- composing its instruction body into the current run
- loading one of its reference or asset files

That ambiguity becomes more costly as Kora moves toward:

- prompt-budget awareness
- model-driven skill selection
- progressive disclosure of skill resources
- stronger reproducibility and tracing

Kora needs a formal lifetime model so downstream users can plug in
different skill-routing strategies without changing what the framework
means by "active", "loaded", or "unloaded".

## Decision

Kora should distinguish **four separate skill states** and give each
one its own lifetime semantics:

1. **Discovered skill metadata**
2. **Active skill state**
3. **Applied skill instructions**
4. **Loaded skill resources**

These are not the same thing and must not share one implicit lifetime.

The default rule is:

- **metadata may persist outside prompt assembly**
- **activation expresses intent, not prompt residency**
- **instructions are applied as run-scoped prompt snapshots**
- **resources are ephemeral and should be unloaded as soon as their
  immediate use is over**

## Terminology

### Discovered skill metadata

The lightweight catalog entry for a skill, such as:

- `name`
- `description`
- source location
- declared references or assets for display
- optional activation hints

This is not prompt content by itself.

### Active skill state

The session-level or configuration-level fact that a skill is currently
enabled for consideration.

This should usually be represented as:

```text
active_skill_names: list[str]
```

not as long-lived in-memory prompt snapshots.

### Applied skill instructions

The full `SKILL.md` instruction body after Host resolves an active or
selected skill and composes its instructions into the current run's
prompt.

This is prompt content.

### Loaded skill resources

The actual contents of a referenced document, template, example, or
other declared skill resource after Host loads that content into the
current run context.

This is also prompt content, but should have a shorter lifetime than
skill instructions.

### Prompt residency

The period during which some skill-derived content is present in the
effective model context for a run.

## Lifetime Rules

### 1. Metadata lifetime

Discovered skill metadata may be cached outside the run loop and reused
across turns.

It should:

- remain cheap to inspect
- remain available for listing and routing
- stay outside the main prompt unless explicitly surfaced as a catalog

Metadata existence does not mean the skill is being used.

### 2. Activation lifetime

Active skill state represents intent and should outlive a single run.

Default rule:

- explicitly activated skills are **session-scoped**
- config-declared default skills are active for the lifetime of the
  agent session unless changed

Activation should survive turn boundaries, but activation alone should
not be treated as a guarantee that raw instruction text stays pinned in
memory between runs.

### 3. Instruction lifetime

Applied skill instructions should be treated as **run-scoped prompt
snapshots**.

This means:

- before a run starts, Host resolves the current active or selected
  skills
- Host composes their full instruction bodies into the run prompt
- once the run starts, that instruction snapshot stays fixed for the
  duration of the run
- when the run ends, the snapshot expires

If the skill remains active, Host may apply it again on the next run by
re-resolving it at the next turn boundary.

So the instruction body is:

- longer-lived than a resource load
- shorter-lived than activation state

### 4. Resource lifetime

Loaded skill resources should be **ephemeral by default**.

The framework should prefer this progression:

1. discover the skill from metadata
2. decide to use or apply the skill
3. load the full instruction body
4. only then load specific resources that the current run actually
   needs

Once loaded, resource contents should generally remain only for the
current immediate task step or run phase, then be removed from future
prompt composition unless deliberately summarized or persisted
elsewhere.

Resource contents should not become sticky merely because they were read
once.

## Official Default Residency Model

Kora should use the following default model.

| Skill element | Default residency | Owned by | Notes |
|---|---|---|---|
| Metadata catalog | Cached outside prompt | Host | For discovery and routing |
| Active skill names | Session-scoped | Host/session state | Intent only |
| Full skill instruction body | Run-scoped | Host prompt assembly | Re-applied each run if still active |
| Resource file contents | Ephemeral | Host/resource loader | Load late, unload early |

## Explicit Activation vs Model-Selected Use

Kora should support two conceptually different cases.

### Case 1. Explicitly activated skill

Examples:

- user runs `/skill activate code-review`
- agent config declares `skills: [code-review]`

In this case:

- the skill becomes active at the session level
- its instructions are eligible to be applied on each run
- its resource contents are still loaded progressively and remain
  ephemeral

### Case 2. Model-selected skill

This is a future-facing case where the model or a Host routing layer
chooses a skill for the current task without permanently pinning it for
the full session.

In this case, the default should be:

- instructions are applied for the current run only
- resources are loaded only if needed
- nothing is automatically promoted to session-persistent activation

If later Kora adds model-driven skill selection, this ADR's semantics
should remain stable:

- selection decides **whether to apply**
- this ADR decides **how long applied content stays resident**

## Unload Semantics

Kora should define unload behavior explicitly.

### Instruction unload

Applied instruction text should leave prompt residency when:

- the current run ends, if the skill was only selected for that run
- the skill is deactivated, starting from the next turn boundary
- the session ends

For explicitly active skills, "unload" does not mean deleting the
activation record. It means the prior run snapshot expires, and a fresh
snapshot will only be composed again if the skill is still active.

### Resource unload

Loaded resource content should leave prompt residency when:

- the immediate step or phase that required it is complete
- the run ends
- a smaller derived summary has been intentionally retained instead

The preferred rule is:

- keep references, citations, or summaries if useful
- do not keep raw resource text in later prompts by default

## Relationship To Turn-Boundary Reload

This ADR is compatible with the turn-boundary reload recommendation.

Combined rule:

- activation state persists across turns
- applied instruction and resource snapshots do not
- active skills are re-resolved at turn boundaries before the next run

This gives users a predictable mental model:

1. activate a skill once
2. edit the skill if needed
3. send the next message
4. the next run uses the updated skill content

without requiring live hot reload inside an already-running turn.

## Why This Model

### 1. It controls prompt growth

If skill instructions and especially skill resources remain pinned after
every use, prompt size will drift upward and become harder to reason
about.

### 2. It supports progressive disclosure cleanly

Many skills have large references or templates. Those should not become
ambient prompt baggage.

### 3. It keeps explicit intent separate from transient context

Activation is a durable user or configuration choice. Prompt residency
is a temporary execution detail.

### 4. It prepares for autonomous skill routing

Future model-driven or policy-driven skill selection becomes much
cleaner if the framework already distinguishes:

- selected this run
- active this session
- loaded as a resource this step

### 5. It improves traceability

A run can record exactly:

- which skills were active
- which skills were applied
- which resources were loaded

without pretending they all shared one lifetime.

## Recommended Host Data Model

Kora should move toward a state model like this:

### Stable state

```text
active_skill_names: list[str]
```

### Run-scoped resolved state

```text
applied_skills: list[SkillPackage]
loaded_skill_resources: list[LoadedSkillResource]
```

The framework should avoid treating loaded `SkillPackage` objects or raw
resource contents as long-lived session truth.

## Non-Goals

This ADR does not define:

- the exact algorithm for automatic skill selection
- whether skill selection is model-driven, rule-driven, or policy-driven
- remote skill installation or marketplace behavior
- memory summarization policy for skill-derived information
- tool permission grants coming from skills

Those decisions may come later without changing the lifetime model in
this ADR.

## Consequences

### Positive

- gives skills a clear and composable runtime mental model
- prevents resource content from silently bloating future prompts
- keeps Kora compatible with both explicit and automatic skill use
- supports future observability around skill application

### Negative

- Host implementation becomes more explicit and stateful
- current skill activation internals may need refactoring
- some users may initially expect activated skills to imply always-pinned
  prompt content

## Recommendation

Treat this ADR as the semantic baseline for future skill work.

The next implementation-facing follow-up should be a small Host design
update that:

1. stores active skill names as durable state
2. rebuilds applied skill snapshots per run
3. treats loaded resource content as ephemeral
4. records active/applied/resource-loaded skill events distinctly in
   trace or debug output
