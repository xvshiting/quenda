# Agent Lifecycle Hooks and Policy Extension

## Status

Draft (2026-06-26)

## Purpose

This document combines Kora's current architecture with recent agent
research trends to propose a hook and policy surface that is more useful
for the agent research community.

It answers four questions:

- which stages are most valuable to expose as hooks
- which of those should live in core
- which capabilities should become default policies or official
  extensions
- how downstream agent authors can plug in smoothly without forking the
  runtime

## Executive Summary

Research trends suggest that the most valuable hooks are not UI hooks,
but strategy hooks around the agent lifecycle. The highest-value stages
to prioritize are:

1. `Context Assembly`
2. `Memory Retrieve`
3. `Memory Write / Delete / Compress`
4. `Planner / Workflow`
5. `Model Selection and Invocation`
6. `Tool Selection and Execution`
7. `Verifier / Reflection`
8. `Termination / Budget Control`
9. `Trace Export / Evaluation`

These nine categories cover most active agent-research themes while
still mapping cleanly onto Kora's current `Host -> Runtime -> Kernel`
layering.

## Research Signals

Several research directions strongly inform this design.

### ReAct and interleaved reasoning-action loops

`ReAct` emphasizes that reasoning and action should be interleaved, not
treated as two disconnected phases. This implies that frameworks should
expose stable seams between model response, tool execution, and the next
reasoning turn rather than only exposing the final answer.

Source:

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

### Reflection and external critique

`Reflexion` and `CRITIC` show that agent improvement often depends on:

- episode feedback
- tool-based critique
- external verifiers

This suggests that reflection and verification should be explicit seams,
not only prompt patterns embedded inside one agent.

Sources:

- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)

At the same time, self-critique is not always reliable. Research has
shown that asking the model to validate its own plans can degrade
performance on some planning tasks.

Source:

- [Can Large Language Models Really Improve by Self-critiquing Their Own Plans?](https://arxiv.org/abs/2310.08118)

This argues for verification hooks that can integrate external
verifiers, not only self-critique.

### Search and workflow optimization

`Tree of Thoughts`, `Tree Search for Language Model Agents`, and `AFlow`
all show that:

- search
- branching
- candidate evaluation
- workflow optimization

are increasingly runtime concerns, not just prompting tricks.

If the framework does not expose planner / branch / workflow seams,
downstream researchers will need to bypass or fork the runtime.

Sources:

- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [Tree Search for Language Model Agents](https://arxiv.org/abs/2407.01476)
- [AFlow: Automating Agentic Workflow Generation](https://arxiv.org/abs/2410.10762)

### Memory as a first-class subsystem

`MemGPT`, recent memory-management work, and 2025-2026 memory-poisoning
research jointly show that memory is no longer a side cache. Retrieval,
writing, deletion, compression, and trust boundaries all matter.

This means memory hooks must go beyond a single "compression strategy"
concept.

Sources:

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- [How Memory Management Impacts LLM Agents: An Empirical Study of Experience-Following Behavior](https://arxiv.org/abs/2505.16067)
- [From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents](https://arxiv.org/abs/2606.04329)
- [MemMorph: Tool Hijacking in LLM Agents via Memory Poisoning](https://arxiv.org/abs/2605.26154)

### Agent-computer interfaces and environment adapters

`SWE-agent` and `WebArena` show that environment and tool interfaces
materially affect agent quality. Tool use is not just "call a function";
it is part of the runtime design.

This argues for tool hooks that support:

- pre-tool policy
- post-tool result shaping
- environment adaptation

Sources:

- [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793)
- [WebArena: A Realistic Web Environment for Building Autonomous Agents](https://arxiv.org/abs/2307.13854)

### Evaluation, observability, and training disaggregation

Recent evaluation surveys and systems such as `Agent Lightning`
emphasize:

- fine-grained trajectories
- cost, robustness, and safety metrics
- separation between execution and training

This makes trace export and observability hooks part of the research
infrastructure, not optional extras.

Sources:

- [Survey on Evaluation of LLM-based Agents](https://arxiv.org/abs/2503.16416)
- [Agent Lightning: Train ANY AI Agents with Reinforcement Learning](https://arxiv.org/abs/2508.03680)

### Multi-agent orchestration belongs above core

`AutoGen` and related work show that multi-agent orchestration is
important, but that does not mean orchestration should move into core.

The better dependency direction is:

- core exposes single-agent lifecycle and trace seams
- upper-layer orchestration packages consume those seams

Source:

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)

## Design Goals

Based on those signals, Kora's hook design should satisfy the following
goals.

### 1. Research-friendly

Downstream researchers should be able to replace local strategies
without forking the full runtime.

### 2. Layer-aligned

Hooks should align with the existing `Host -> Runtime -> Kernel`
boundaries rather than dissolve them.

### 3. Typed and explicit

Prefer typed policy, middleware, and observer contracts over ad-hoc
callback lists.

### 4. Default-simple

Default implementations should remain small and understandable.
Complex strategies should plug in from outside.

### 5. Traceable

All major stages should be observable for replay, evaluation, and
training.

## Recommended Hook Taxonomy

Not every extension point should be called a "hook". A more useful
taxonomy is:

### 1. Observers

Observe only; do not change behavior.

Good for:

- metrics
- logging
- trace export
- evaluation

### 2. Policies

Return a decision at a specific lifecycle stage.

Good for:

- memory retrieval
- model selection
- tool selection
- termination
- compression

### 3. Middleware

Wrap execution and operate before and after a stage.

Good for:

- model invocation
- tool execution
- persistence

This separation helps avoid a generic callback soup.

## Recommended Core Hook Stages

The following stages are the most valuable candidates for core seams.

### 1. Run Ingress Hook

Location:

- Host / Runtime boundary

Purpose:

- preprocess the incoming task
- inject constraints
- apply lightweight routing or benchmarking setup

Research value:

- instruction rewriting
- task routing
- evaluation harness integration

Recommended form:

- middleware or policy

### 2. Context Assembly Hook

Location:

- Runtime

Purpose:

- construct the effective model input context
- combine system prompt, summaries, recent messages, and state overlays

Research value:

- context engineering
- prompt strategy comparison
- retrieval-slot allocation

Recommended form:

- policy

This is one of the highest-priority seams for core.

### 3. Memory Retrieve Hook

Location:

- Runtime

Purpose:

- choose which long-term memory to retrieve
- rank, truncate, and filter retrieved memory

Research value:

- episodic memory
- semantic retrieval
- experience replay
- trust-aware retrieval

Recommended form:

- policy

### 4. Memory Write / Delete Hook

Location:

- Runtime / Host persistence boundary

Purpose:

- choose what experience to write into memory
- delete or demote memory
- annotate trust, source, expiry, or relevance

Research value:

- memory growth control
- error-propagation mitigation
- poisoning defense

Recommended form:

- policy

This seam is more valuable to the research community than a raw
`save_session()` surface.

### 5. Compression / Summarization Hook

Location:

- Runtime

Purpose:

- decide whether to compress
- choose how to summarize
- preserve key structure during compaction

Research value:

- long-context management
- summary fidelity
- memory compaction

Recommended form:

- policy

Kora already has an initial version of this seam. It is a strong signal
for the broader direction.

### 6. Planner / Workflow Hook

Location:

- Runtime loop control

Purpose:

- support plan-first, branching, search, or critic-guided workflows

Research value:

- ReAct variants
- search over actions
- workflow synthesis

Recommended form:

- policy

Important constraint:

- Kernel should not turn into a large planner
- this seam fits better in Runtime

### 7. Model Selection Hook

Location:

- Runtime / Provider boundary

Purpose:

- choose a model based on task type, cost, history, or failure mode

Research value:

- routing
- adaptive inference
- cost-aware execution

Recommended form:

- policy

### 8. Pre-Model Invocation Hook

Location:

- immediately before Provider API invocation

Purpose:

- adjust request parameters
- inject guardrails, timeouts, or instrumentation

Research value:

- inference-time control
- safety instrumentation
- evaluation instrumentation

Recommended form:

- middleware

### 9. Post-Model Response Hook

Location:

- Kernel / Runtime boundary

Purpose:

- validate or repair responses
- attach sanitizers or structural checks
- trigger downstream verifier logic

Research value:

- output verification
- structured-response repair
- reasoning sanitization

Recommended form:

- middleware or policy

### 10. Tool Selection Hook

Location:

- before tool execution

Purpose:

- reorder, reject, or replace tool use
- apply risk-, context-, or history-aware tool policy

Research value:

- tool-use policy
- safe tool routing
- learned tool preference

Recommended form:

- policy

### 11. Tool Execution Hook

Location:

- around the tool runtime

Purpose:

- wrap execution
- add caching, retries, sandbox logic, or redaction

Research value:

- environment adaptation
- cost control
- safety gating

Recommended form:

- middleware

### 12. Tool Result Processing Hook

Location:

- after tool execution, before the result is returned to the model

Purpose:

- truncate, summarize, label, or structure tool observations

Research value:

- tool feedback shaping
- result compression
- observation abstraction

Recommended form:

- policy

### 13. Verification / Reflection Hook

Location:

- after a model step or after a multi-step partial result

Purpose:

- attach an external verifier or critic
- decide whether to retry, revise, or continue

Research value:

- Reflexion
- CRITIC
- external verification

Recommended form:

- policy

Explicit support for external verifiers is recommended; self-critique
alone should not define the seam.

### 14. Termination / Budget Hook

Location:

- Runtime loop control

Purpose:

- decide whether to continue, stop, compress, backtrack, or switch model

Research value:

- cost-aware agents
- adaptive stopping
- safe stopping

Recommended form:

- policy

### 15. Trace Export Hook

Location:

- cross-cutting across the whole execution lifecycle

Purpose:

- export structured trajectories
- support replay, benchmark evaluation, offline analysis, and training

Research value:

- evaluation
- RL and offline training
- workflow optimization

Recommended form:

- observer

This is one of the most important seams for research, and one of the
easiest to underestimate.

## Priority Tiers

To avoid overcomplicating core too early, these hooks should be phased.

### Tier 1: Highest-priority core seams

- Context Assembly
- Memory Retrieve
- Memory Write / Delete
- Compression / Summarization
- Model Selection
- Tool Selection
- Tool Result Processing
- Termination / Budget
- Trace Export

These are broadly useful across most current agent research directions.

### Tier 2: High leverage, but can follow

- Planner / Workflow
- Pre-Model Invocation
- Post-Model Response
- Verification / Reflection
- Tool Execution middleware

These are important, but depend more on stable lower-level contracts.

### Tier 3: Better placed above core

- multi-agent orchestration
- UI navigation
- command palettes
- rich human-approval workflows beyond the simplest defaults

These should consume core hooks rather than force core abstractions.

## Mapping to Kora Layers

### Host

Best suited for:

- ingress
- persistence
- trace sinks
- user-approval policy

### Runtime

Best suited for:

- context assembly
- memory policy
- planner logic
- verification
- termination
- compression

### Kernel

Kernel should remain small and stable, exposing primarily:

- pre-model and post-model seams
- tool execution seams
- loop events

Kernel should not become the home of most high-level strategy logic.

## Recommended Interface Style

The project should avoid modeling every stage as:

- `before_x()`
- `after_x()`

callback lists.

Recommended style:

- observer interfaces for telemetry
- policy interfaces for decisions
- middleware interfaces for execution wrapping

These are semantically clearer and scale better than generic callback
collections.

## What This Means for Kora

If Kora follows this direction, it is more valuable to build:

- a generalized form of `CompressionPolicy`
- `MemoryPolicy`
- `ModelSelectionPolicy`
- `ToolPolicy`
- `TerminationPolicy`
- `TraceSink`
- `VerifierPolicy`

than to prioritize:

- slash-command submenus
- richer selector state
- REPL menu navigation

Those UI capabilities may still exist as official front-end features,
but they should not define core evolution.

## Suggested Near-Term Plan

### Phase 1

- standardize terminology: hook / policy / observer / middleware
- generalize the existing compression seam
- introduce a structured trace-export model

### Phase 2

- add memory read / write policy
- add model-selection and termination policy
- add tool-result shaping seam

### Phase 3

- add verifier / reflection seam
- add planner / workflow seam
- validate them through official agents and promote useful defaults

## Final Recommendation

For an agent framework aimed at research and downstream system builders,
the highest-value investments are:

- clear lifecycle stages
- stable strategy-extension seams
- structured traces
- simple defaults

Kora has already moved in the right direction through its compression
strategy seam.

The next step is to make that philosophy systematic across memory,
planning, tool use, verification, termination, and trace export.
