# Self-Evolution and Extension Platform

## Status

Proposed (2026-08-13)

## Purpose

This document turns Quenda's existing policies, context providers, Skills,
compression, and follow-up phases into one coherent platform for:

- safe, inspectable self-evolution
- cache-stable prompt construction
- replaceable official strategies
- framework-aware agent authoring and self-configuration
- continuous verification loops
- optional multi-agent orchestration
- pluggable retrieval and execution backends

The design rule is:

> Core owns lifecycle, contracts, safety, and provenance. Official packages own
> useful default strategies. Agent packages and users may replace those
> strategies without patching Runtime.

### Unix-style composition constraints

This proposal inherits the framework direction established by ADR-008 and
ADR-022. “Unix-style” is an interface constraint, not a requirement to turn
every operation into a shell command:

1. Each core module owns one coherent mechanism and exposes a small, stable
   contract. Evolution, retrieval, orchestration, and execution remain separate.
2. Strategies compose through typed inputs/outputs; no extension reaches into a
   shared mutable Runtime object as its integration API.
3. CLI commands are non-interactive by default, accept explicit stdin/files,
   write primary results to stdout, diagnostics to stderr, and return meaningful
   exit codes. Machine-readable JSON/JSONL is a first-class output mode.
4. Configuration and manifests are inspectable, diffable, and validatable.
   Hidden process-global state is forbidden for Run, Session, cancellation,
   permissions, memory revisions, and extension activation.
5. Registration, exposure, authorization, and execution are independent stages.
   Installing a component never silently grants or invokes it.
6. Official implementations use the same public contracts as third-party ones;
   users can replace one component without adopting a monolithic product stack.
7. Components support piping and automation, but process boundaries are chosen
   for isolation or deployment—not used to compensate for unclear library APIs.

## Current Baseline and Gaps

Quenda already has more of the required foundation than its user-facing model
currently communicates.

| Capability | Current state | Missing closure |
|---|---|---|
| Context compression | `DefaultCompressionPolicy` triggers on a ratio of model context capacity; Quenda Code configures `0.7` | Make effective budget include reserved output and provider limits; document cache behavior |
| Tool result shaping | Runtime invokes `ToolResultProcessingPolicy` before loop writeback | Publish the seam, provenance, examples, and cache-impact contract |
| Cheap tool cleanup | Runtime micro-compacts old tool results | Replace fixed token defaults with model-relative defaults where possible |
| Memory | Quenda Code loads `IDENTITY.md`, `SOUL.md`, `USER.md`, and `MEMORY.md`; detailed Markdown memory is retrieved on demand; revisioned automatic/review/disabled writes are available | Add end-of-Run observation and proposal triggering, promotion, and forgetting flows |
| Skills | Discovery, activation, resources, and package-local Skills exist | Add versioned improvement proposals, evaluation, rollback, and trust policy |
| Policies | Compression, termination, tool selection, and result processing are bindable | Unify all lifecycle extension points into a public catalog |
| Follow-up phases | `run_followup_phases` is a tested helper, but no production call site uses it; rollback only truncates session messages | Replace the prototype with persistent continuation state and transactional checkpoints |
| Framework knowledge | A versioned capability manifest is exposed through Python, CLI, and Web; Quenda Code bundles a progressively loaded authoring Skill | Add generated JSON Schema, validation/mutation tools, and broader executable examples |
| Multi-agent | Deliberately outside core | Provide an official optional orchestrator package over public Run/Session APIs |

### Correctness prerequisites discovered during implementation review

These are not self-evolution features, but they must be closed before adding
background maintenance, persistent goals, or subagents:

1. **Resolved 2026-08-14:** `AnthropicMessagesApi._convert_messages()` previously overwrote the system
   value for every system message. Runtime emits the main prompt, compression
   summaries, and active resource context as separate system messages, so an
   Anthropic request can lose the framework/agent prompt when a later system
   block exists. Provider adapters need semantic-parity golden tests.
2. **Resolved 2026-08-14:** `HostService.start_run()` previously allowed multiple Runs for one Session. Two Runs
   can refresh and mutate the same prompt, messages, permission handler, and
   persistence state concurrently. Enforce one writer per Session or introduce
   revisioned transactional state before supporting orchestration.
3. **Resolved 2026-08-14:** Runtime execution now consumes a Run-scoped
   cancellation token. Child-Run cascade semantics remain future orchestrator work.
4. **Partially resolved 2026-08-14:** `refresh_run_context()` and
   `ContextRebuilder` now render through the same pure `PromptAssembler`, and
   Run snapshots expose the resulting segment manifest. Source collection still
   has two extension surfaces, and provider requests still receive a flattened
   string; those remaining paths must converge before cache ordering is changed.
5. **Pending:** Local Python and shell execution are not isolation boundaries. Existing
   module and regex restrictions are policy hints, not an OS sandbox; remote or
   untrusted execution must wait for a real `ExecutionBackend` boundary.

## 1. Prompt Cache Contract

Logical instruction precedence and provider wire order are separate concerns.
Quenda must resolve authority/conflicts explicitly, then construct each model
request in monotonic stability order:

```text
[A] provider/framework contract        very stable
[B] agent identity and invariant rules stable per agent version
[C] tool definitions                   stable per capability binding
[D] agent/user durable profile snapshot stable per session revision
[E] workspace overlays                 stable per workspace revision
[F] activated Skill instructions       stable per activation epoch
[G] summary + recent messages          dynamic conversation tail
[H] current time/run state/input/results newest tail
```

The exact provider wire format may require tools outside the text prompt, but
the same ordering and invalidation model applies. A more-specific instruction
does not win merely because it appears later; scope and trust decide precedence.

Today Quenda does not have this shape. It concatenates framework contract,
temporal context, agent identity/location, package instructions, user/workspace
overlays, and active Skills into one string on every Run. The daily temporal
block and workspace path occur near the front, so changing either invalidates
all later cacheable content. Tool schemas are a separate provider request field,
which is good, but their ordering and digest are not yet contractual.

### Requirements

1. Text refresh must not silently rebuild or reorder A-C.
2. Every source has a stable `source_id`, content digest, revision, residency,
   trust class, and invalidation reason.
3. Capability rebind is the only normal operation that changes C.
4. Memory and Skill evolution creates a new revision at D or F; it never
   rewrites historical messages. By default the active Session retains its
   frozen memory revision until a new Session or explicit reload boundary.
5. Tool-result processing and micro-compaction operate only on G-H.
6. Observability records estimated cached-prefix tokens and the first changed
   segment. Provider-reported cached input remains authoritative when present.
7. Frequently changing facts such as time, current mode, current task, and
   runtime status must stay out of A-F.
8. In-Run Skill activation is an explicit activation epoch: it may invalidate
   F and later, but cannot silently re-read and change A-E.
9. Provider adapters must preserve the same ordered semantic blocks even when
   their APIs represent system instructions differently.

Introduce a `PromptSegment` model rather than passing anonymous concatenated
strings through the entire Host:

```python
PromptSegment(
    source_id: str,
    content: str,
    revision: str,
    residency: "binding" | "activation" | "run" | "turn",
    trust: "framework" | "official" | "agent" | "user" | "retrieved",
    cache_priority: int,
)
```

Providers may flatten segments at the final boundary. This preserves the
current API while making cache invalidation observable and testable.

## 2. Self-Evolution Is a Governed Maintenance Workflow

Self-evolution must not mean that the serving agent edits its own active prompt
or executable extensions during a Run. It is an asynchronous or turn-boundary
maintenance workflow producing reviewable proposals.

```text
observe -> select evidence -> propose -> validate -> write policy -> commit revision
                                                        |-> reject/quarantine
```

### Evolution targets

| Target | Default ownership | Default policy |
|---|---|---|
| `USER.md` | User | Configurable automatic/review/disabled writes with journal and rollback |
| `MEMORY.md` | User-agent private state | Configurable automatic/review/disabled writes with journal and rollback |
| `memory/**/*.md` | User-agent private state | May append dated evidence with provenance |
| `IDENTITY.md` | Agent package | Role, responsibilities, and operating scope; governed independently |
| `SOUL.md` | Agent package | Personality, values, and temperament; governed independently |
| `SKILL.md` and Skill resources | Agent/user package | Proposal + evaluation + approval; never mutate an active revision |
| Executable extensions/tools/policies | Agent package | Normal code-change workflow; no automatic execution |

`IDENTITY.md` and `SOUL.md` are not aliases and neither replaces the other. The
profile provider loads both when present, and new Agent Homes scaffold both.

### Trigger model

The official scheduler evaluates maintenance at safe boundaries and emits a
reason. Supported triggers are composable:

- explicit user command (`/evolve`, `/remember`, `/forget`)
- end of a completed Run when a durable fact or correction was explicitly stated
- repeated correction or preference observed across at least N distinct Runs
- failed or low-scoring Skill evaluation
- repeated tool failure/no-progress pattern
- session compression boundary
- idle/session-close maintenance
- periodic count/time trigger, if the Host supports scheduling

Eligibility also checks minimum useful history, idle state, rate-limit headroom,
per-target cooldown, daily token/write quota, and whether the same evidence was
already consumed. A trigger is a scheduling decision, never write permission.

Do not reflect after every turn by default. The official policy should use
cheap deterministic eligibility checks first, then invoke a model only when
there is evidence worth processing.

### Required contracts

```python
EvolutionTriggerPolicy.evaluate(EvolutionObservation) -> TriggerDecision
EvolutionPlanner.propose(EvolutionEvidence) -> list[EvolutionProposal]
EvolutionValidator.validate(EvolutionProposal) -> ValidationResult
EvolutionApprovalPolicy.decide(EvolutionProposal, ValidationResult) -> ApprovalDecision
EvolutionStore.stage/commit/reject/rollback(...)
```

Every proposal contains target, base revision, patch, rationale, evidence
references, confidence, risk, evaluator results, and expiry. Commit uses
compare-and-swap on the base revision so concurrent or stale proposals cannot
overwrite newer user state.

### Safety and trust

- Retrieved web/tool content is untrusted evidence and cannot directly become
  instructions or executable Skill content.
- Separate facts, preferences, procedures, and identity changes; each has a
  different retention and approval policy.
- Deduplicate, detect contradiction, and retain provenance.
- Redact secrets and enforce per-scope data boundaries before persistence.
- Keep an append-only audit journal and reversible revisions.
- Newly generated Skill code stays quarantined until tests and permission
  review pass.

## 3. Unified Lifecycle and Extension Surface

Quenda should publish one canonical table generated from registered extension
point descriptors. “Hook” is not the universal abstraction.

| Stage | Extension kind | May mutate data | May choose transition | Core default |
|---|---|---:|---:|---|
| setup/rebind | initializer, resolver | yes | no | capability binding |
| before Run | observer, policy | limited | no | refresh text |
| compression check | policy | no | yes | ratio policy |
| memory retrieve | policy/provider | no | no | none |
| context assembly | provider/middleware | prompt only | no | ordered composer |
| before model | middleware, router | request only | no | direct invocation |
| after model | observer, verifier | no | yes via decision | accept response |
| before tool batch | selection policy | no | yes | allow all |
| around tool call | middleware | result only | no | direct execution |
| after tool result | processing policy | result only | no | pass through |
| loop decision | termination/continuation policy | no | yes | model/tool loop |
| after Run | observer, memory/evolution policy | staged writes | schedule only | persist trace |
| session idle/close | maintenance policy | staged writes | no | none |

Each descriptor declares input/output types, owner layer, ordering, error mode,
timeout, concurrency, prompt-cache impact, state-write permissions, and event
schema. Unknown or incompatible extension API versions fail at binding time.

Use two implementation surfaces over the same lifecycle catalog:

- typed in-process policies/providers for correctness-critical composition,
  authorization, state transitions, and persistence;
- external command/plugin hooks for observation and bounded integration.

External hooks receive immutable snapshots and return typed decisions or
patches. Guard hooks are awaited and fail closed; observers may fail isolated.
Large hook output is stored as an artifact with a bounded preview. Installed
hook code is content-addressed and must be trusted again after its digest
changes. No hook system should be advertised as a complete security boundary
unless every execution harness—including hosted and embedded tools—runs it.

### Ordering

Use explicit ordered pipelines, not filename order:

1. hard framework guards
2. Host/organization policy
3. official strategy
4. agent package strategy
5. user strategy

Observers may fan out. Mutating middleware and transition policies use a
deterministic chain with conflict detection.

## 4. Tool Taxonomy and Availability

Use four provenance classes:

1. **framework**: lifecycle-essential tools with stable contracts
2. **official**: maintained bundles that are replaceable and configurable
3. **marketplace**: installed packages with manifest, permissions, and trust metadata
4. **local**: user/agent-defined tools

Availability and prompt exposure are separate decisions. A tool can be
installed and callable without placing its full schema in every request.

- A very small framework set is always bound where the capability exists.
- Frequently used official tools may be eagerly exposed.
- Large marketplace/local catalogs use a stable catalog summary plus
  `search_tools`/activation.
- Tool schema order is deterministic and schemas are content-addressed.

The framework should optimize measured cache hit rate and model tool-selection
quality, rather than assuming either “all tools” or “few tools” is universally
best.

## 5. Framework-Aware Agents and Self-Configuration

Agents should not learn Quenda configuration from a hand-maintained prose
prompt alone. The source of truth should be a versioned capability registry
owned by code.

Generate these artifacts in CI from the same registry:

- `quenda capabilities --json`
- configuration JSON Schema
- lifecycle/extension-point catalog
- tool and policy catalog
- reference documentation tables
- an official `quenda-authoring` Skill
- executable example agents used by documentation tests

Add read-only framework tools:

- `inspect_quenda_capabilities`
- `validate_agent_package` (initial static validator complete)
- `explain_agent_config`

Add a guarded mutation tool:

- `apply_agent_config_patch`, which validates schema, shows a diff, respects
  workspace/agent-home permissions, and requires approval for capability or
  external-system changes

Examples must be integration-tested against the current package. CI should
fail when generated docs or examples drift from the registry.

## 6. Continuous Work, Verification, and Graphs

The existing bounded `run_followup_phases` helper is only a prototype: current
product code does not call it, and its checkpoint/rollback covers messages but
not summaries, archives, tool side effects, usage, memory writes, or artifacts.
Replace it with a persistent official continuation strategy:

```python
ContinuationPolicy.evaluate(PhaseResult, GoalContract, Budget) ->
    finish | continue_with_feedback | branch | request_user | fail
```

An official `verify-until-done` strategy should support deterministic checks,
external verifiers, model critique, budgets, no-progress detection, and a hard
phase cap. “Satisfied” must be tied to an explicit goal contract and evidence,
not only the same model saying the answer looks good.

Persist `GoalState`, verdict, consumed evidence, wait/barrier state, and budget.
Real user input preempts queued synthetic continuation. Judge failure behavior
is configurable; Runs with external side effects default to pause, not continue.
Continuation is appended to the dynamic conversation tail and never edits the
system prefix.

Graph/loop engines belong above the single-agent Runtime. Core should expose
checkpoint, fork, cancel, resume, event, and artifact primitives. An official
optional orchestration package can then provide planner-worker, parallel fanout,
reviewer, DAG, and sub-agent patterns without making every Quenda Run a graph.

## 7. Retrieval and Sandbox Backends

### Retrieval

Define a narrow `Retriever` port returning provenance-rich candidates. Ship:

- current index-free Markdown scan
- official BM25 adapter

Keep vector, hybrid, and remote search as replaceable adapters. Retrieval,
ranking, prompt injection, and memory persistence remain separate phases.

### Execution

Replace the local-only assumption with an `ExecutionBackend` capability:

```python
prepare -> execute -> stream -> collect_artifacts -> cancel -> close
```

Ship local process first, then official Docker and SSH adapters. Configuration
declares backend, workspace mapping, environment/secrets references, network,
resource limits, timeout, and artifact policy. Agent packages request a backend;
Host policy grants it. SSH host keys and credentials remain Host-owned.

## 8. Packaging

Recommended distribution boundary:

```text
quenda-core               lifecycle contracts and safe defaults
quenda-official           replaceable policies/backends/tools
quenda-code               official coding agent and identity
quenda-orchestrator       optional multi-agent/graph execution
marketplace/local         third-party and user packages
```

They may initially share a repository, but must depend only on public
contracts. This allows Quenda Code to enable official self-evolution by default
while users may disable it or bind their own implementation.

## 9. Quenda Implementation Audit

The current code review yields this priority matrix. “Reuse” means deepen an
existing seam, not introduce a parallel abstraction.

| Priority | Area | Evidence in current code | Decision |
|---|---|---|---|
| P0 | Provider context parity | Anthropic keeps only the last system message; Runtime emits several | Fix adapter and add one cross-provider fixture suite |
| P0 | Session concurrency | `HostService.start_run()` accepts multiple active Runs for one mutable Session | Add Session lease/one-writer rule and optimistic revision |
| P0 | Cancellation | Runtime uses one process-global interrupt signal and clears it at Run start | Introduce Run-scoped cancellation token and cascade API |
| P0 | Execution safety | Python/shell run local subprocesses; module/regex filters are not isolation | Name it `local-trusted`; add real backend capability checks |
| P1 | Prompt cache | Daily temporal context and workspace identity appear near the front of one rebuilt string | Adopt `PromptSegment`, frozen snapshots, activation epochs, invalidation telemetry |
| P1 | Context paths | `refresh_run_context` and `ContextRebuilder` compose through different paths | Replace both with one canonical assembler |
| P1 | Compression budget | Ratio trigger exists, but reserved output does not affect policy; later math subtracts a hard-coded 4000 | Centralize ratio, reserve, summary and recent-tail math in `ContextBudget` |
| P1 | Tool-result handling | Processing policy runs before persistence/model replay; raw output remains in events/traces | Split model/persist/display/trace views and apply secret policy to raw traces |
| P1 | Tool exposure | Deferred schemas and `search_tools` activation already exist | Preserve; formalize registry/exposure/authorization/provenance separately |
| P1 | Extension determinism | Agent-local Python is loaded by file iteration and cached by path-derived module name | Sort explicitly; content-address revisions; add API version, trust and failure policy |
| P2 | Continuation | `run_followup_phases` is test-only and rollback is message-only | Replace with persisted goal/phase state and transactional artifacts |
| P2 | Memory evolution | Markdown memory and tools exist, but no proposal/revision/audit workflow | Build official conservative maintenance package over artifact revisions |
| P2 | Skill evolution | Discovery/activation exists; active activation rebuilds the full prompt | Version Skills, validate in isolation, activate at an explicit epoch |
| P3 | Retrieval | Markdown search exists but no stable retriever port | Add `Retriever`, then official BM25 adapter |
| P3 | Orchestration | No persistent child-Run graph or scoped cancellation | Add only after Run/Session correctness; ship optional orchestrator |

Additional observable defects should be fixed with the owning seam rather than
papered over: `result_truncated` currently reflects a fixed processed-length
test rather than whether a processor changed the result; extension setup has
inconsistent fail-open/fail-closed behavior; and raw tool output may contain
credentials even when the model-visible result is sanitized.

## 10. Delivery Plan

### Phase -1 — Provider and Session correctness

- Fix multi-system-message semantics for Anthropic and add provider-parity
  golden tests for summaries, resource context, tool calls, and multimodal data.
- Serialize same-Session writes and make persistence revision-aware.
- Replace the process-global interrupt flag with Run-scoped cancellation.
- Collapse all prompt rebuild paths into one canonical assembler.
- Label local execution accurately and prevent it from being selected where an
  isolation guarantee is required.

Implementation progress (2026-08-16):

- completed: Anthropic preserves ordered system blocks and no longer injects
  empty tool-result placeholders before persisted real results;
- completed: Host and Runtime reject concurrent writers for one Session;
- completed: Runtime exposes a Run-scoped `CancellationToken`, and Host targets
  only the selected Run token before cancelling its task;
- completed: a canonical, side-effect-free `PromptAssembler` now serves Run
  refresh and model/mode context rebuilds while preserving the compatibility
  string API;
- completed: `PromptSegment` metadata, assembly/stable-prefix digests, and
  first-change invalidation reasons are public and covered by behavior tests;
- completed: `PromptAssembler` orders binding, session, activation, and Run
  residency classes by stability while preserving relative order inside each
  class, so temporal Run context stays behind the stable prefix;
- completed: local process execution is declared as `local-trusted`; an Agent
  requiring isolation or selecting an unavailable backend fails during static
  validation and Host binding;
- completed: turn refreshes and compatibility rebuilds now share canonical
  source collection, scope ordering, path de-duplication, and prompt assembly;
- completed: Anthropic and OpenAI-compatible transports share semantic golden
  fixtures, and provider-reported cache read/write usage is normalized into the
  Runtime event and Session telemetry contract.

### Phase 0 — Contract and observability

- Introduce `PromptSegment` and prefix-invalidation telemetry. (Content-free
  observations and `prompt_cache_observed` Host events now report stable/reused
  segment counts, digests, and token estimates; provider-reported cache reads
  and writes now flow through `ModelResponded` and `SessionUsage`.)
- Generate the capability/extension catalog from code. (`quenda.lifecycle/v1`
  is now the ordered code-owned registry for active and reserved seams and is
  included in `quenda.capabilities/v1`, CLI, and Web surfaces.)
- Document current policy bindings and tool provenance.
- Add cache-stability golden tests across ordinary Runs. (Covered for canonical
  assembly plus Anthropic and OpenAI-compatible request semantics.)

### Phase 1 — Safe memory evolution

- Add evolution observation, proposal, validator, approval, and journal types.
  (Foundation implemented as `quenda.evolution`: configurable automatic,
  reviewed, or disabled writes; secret checks; optimistic concurrency; atomic
  writes; content-addressed snapshots; append-only journal; and
  rollback-as-new-revision.)
- Ship explicit `/remember`, `/forget`, `/evolve status|review|rollback` flows.
- Enable conservative end-of-Run memory proposals and pass them through the
  configured write policy. The official policy defaults to automatic writes;
  review and disabled modes remain available. (Implemented through the isolated
  `AfterRunHandler` seam with periodic and explicit-signal triggers; failures do
  not change the completed Run outcome.)
- Model `IDENTITY.md` and `SOUL.md` as separate always-on documents. (Implemented:
  both are loaded when present; new Agent Homes scaffold both.)

### Phase 2 — Skill evolution and framework self-configuration

- Version Skills and evaluate proposals in isolation. (The
  `SkillEvolutionStore` foundation now stages full package candidates outside
  every Skill discovery root, records evaluator output, statically parses
  frontmatter and compiles Python without importing or executing it, rejects
  path traversal/symlinks/probable secrets, and requires explicit approval plus
  base-revision CAS before an atomic directory activation. Every activation is
  journaled, historical snapshots are content-addressed, and rollback creates a
  new audit entry. This is static quarantine, not an OS execution sandbox;
  executing proposed tests waits for the Phase 4 `ExecutionBackend`. Host
  bindings now render instructions and resolve resources from immutable Skill
  snapshots; ordinary refresh cannot change them, while explicit activation or
  `advance_skill_activation_epoch()` pins current revisions as a new epoch.)
- Ship `quenda-framework-authoring` Skill and config inspection/validation
  tools. (Bundled authoring Skill and static `validate_agent_package` Tool/CLI
  complete. The always-bound `apply_agent_config_patch` Tool now provides
  RFC 7396 preview/commit, full candidate validation, redacted diffs,
  optimistic concurrency, explicit semantic approval, atomic writes,
  content-addressed rollback revisions, and an append-only journal. A dedicated
  credential-free `explain_agent_config` Tool now combines normalized effective
  configuration, static validation, and matching live capabilities.)
- Generate schemas, docs, and tested examples from the capability registry.

### Phase 3 — Verification and persistent goals

- Promote follow-up phases to `ContinuationPolicy`.
- Add goal contracts, budgets, checkpoints, no-progress detection, and resume.
- Ship the official `verify-until-done` strategy.

### Phase 4 — Retrieval and execution adapters

- Add `Retriever` and BM25 official adapter.
- Add `ExecutionBackend`; ship Docker and then SSH with Host authorization.

### Phase 5 — Optional orchestration

- Build `quenda-orchestrator` on public primitives.
- Ship planner/parallel-worker/reviewer examples and cancellation tests.

## 11. Acceptance Criteria

- An ordinary new Run with unchanged binding and memory preserves the same
  stable prefix digest.
- A memory update invalidates only the memory segment and later segments.
- No active Skill or identity file is overwritten during a Run.
- Every evolution commit is attributable, reviewable, and reversible.
- Official strategies can be disabled or replaced entirely through config.
- The capability manifest, docs, schemas, and examples cannot drift in CI.
- A custom verifier, memory policy, retriever, or execution backend can be
  added without modifying Runtime source.
- Continuous work always has budget, cancellation, and no-progress guards.
- All provider adapters preserve framework, agent, summary, and resource
  instruction semantics in the same fixture suite.
- A Session has at most one active writer; stale Runs cannot commit messages,
  prompts, memory, goals, or evolution revisions.
- Cancelling one Run cannot clear or cancel an unrelated Run.
