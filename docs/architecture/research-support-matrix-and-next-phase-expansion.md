# Research Support Matrix and Next-Phase Lifecycle Expansion

## Status

Draft (2026-06-29)

## Purpose

This document evaluates how well Quenda's current runtime terminology and
state-machine design support recent agent research directions, and
identifies the next set of lifecycle phases and transitions that would
most improve that support.

It answers three questions:

- which research methods are already well supported by the current
  lifecycle design
- which methods are only partially supported
- which additional phases and transitions would most improve research
  coverage

This document builds on:

- [ADR-019: Prioritize Strategy Hooks Over Rich UI](/Users/xushiting/Workspace/quenda/docs/decisions/019-strategy-hooks-over-rich-ui.md)
- [ADR-020: Runtime Terminology and Execution Units](/Users/xushiting/Workspace/quenda/docs/decisions/020-runtime-terminology-and-execution-units.md)
- [ADR-021: Runtime Lifecycle and State Machine](/Users/xushiting/Workspace/quenda/docs/decisions/021-runtime-lifecycle-and-state-machine.md)

## Evaluation Criteria

For each research direction, this document evaluates whether the current
design supports:

- clear mapping to runtime states
- meaningful hook insertion points
- traceability for comparison and evaluation
- strategy substitution without major framework forks

Support levels used below:

- `Strong`: current terminology and lifecycle already align well
- `Partial`: current design can host the method, but important seams are
  missing or awkward
- `Weak`: the method is possible only through significant workaround or
  framework restructuring

## Current Support Matrix

| Research Direction | Support Level | Why |
|---|---|---|
| ReAct-style reasoning/action loops | Strong | `Model Step`, `Tool Batch`, `Tool Phase`, and `LoopDecision` align naturally |
| Tool-use policy / agent-computer interfaces | Partial | tool phases are named, but Runtime does not yet fully own tool gating and result shaping |
| Budget-aware / stopping strategies | Strong | `Run`, `Step`, `LoopDecision`, and Runtime termination are a good fit |
| Trace / evaluation / replay | Strong | `Run`, `Step`, events, and `TraceSink` align well |
| Reflection / verification | Partial | lifecycle leaves room, but no explicit verification phase exists yet |
| Long-term memory / memory-managed agents | Partial | lifecycle can host memory seams, but memory phases are not yet explicit |
| Search / branching / workflow optimization | Weak to Partial | current lifecycle is mainly linear and lacks branch-level units |
| Multi-agent orchestration | Partial at lower layer | core lifecycle is useful as a single-agent substrate, but orchestration needs upper-layer modeling |

## Research Direction Analysis

### 1. ReAct-style reasoning and acting

Representative work:

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

### Current fit

Support level:

- `Strong`

Reason:

- one `Model Step` maps cleanly to one reasoning/action proposal
- one `Tool Batch` maps cleanly to one set of requested actions
- `Tool Phase` captures execution of those actions
- `LoopDecision` naturally represents "what happens next"

This is one of the strongest confirmations that the current terminology
is on the right track.

### Remaining gaps

The main gap is not conceptual. It is implementation ownership:

- Runtime still does not fully own tool gating and post-tool shaping

This affects experimentation quality, but not the conceptual lifecycle.

## 2. Tool-use policy and environment-interface research

Representative work:

- [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793)
- [WebArena: A Realistic Web Environment for Building Autonomous Agents](https://arxiv.org/abs/2307.13854)

### Current fit

Support level:

- `Partial`

Reason:

- the terminology now distinguishes `Tool Call`, `Tool Batch`, and
  `Tool Phase`
- that is good enough for tool-policy reasoning
- but current Runtime / Kernel ownership is still too narrow for full
  policy control

### Remaining gaps

Needed next steps:

- Runtime-owned tool-call approval seam
- Runtime-owned tool-result shaping seam
- better phase-level control over tool batches

These are already recognized in the current hook drafts.

## 3. Budget-aware and stopping-control research

Representative directions:

- adaptive stopping
- cost-aware routing
- failure-based stopping

### Current fit

Support level:

- `Strong`

Reason:

- `Run` is the right top-level lifecycle unit
- `LoopDecision` is the right transition boundary
- `Completion`, `Termination`, `Interruption`, and `Failure` are now
  clearly separated

This is already a solid foundation for:

- max-step policies
- time budgets
- token budgets
- error-based stopping

### Remaining gaps

The main remaining gap is richer behavioral state:

- current termination design should include tool-batch and progress
  signals, not only budget counters

That is an interface refinement problem, not a lifecycle-model failure.

## 4. Trace, evaluation, and replay-based comparison

Representative work:

- [Survey on Evaluation of LLM-based Agents](https://arxiv.org/abs/2503.16416)
- [Agent Lightning: Train ANY AI Agents with Reinforcement Learning](https://arxiv.org/abs/2508.03680)

### Current fit

Support level:

- `Strong`

Reason:

- `Run` is a natural execution episode
- `Step` is a natural trajectory increment
- Runtime events already provide structured observation points
- `TraceSink` is a clean observer seam

This is sufficient to support:

- offline comparison of strategies
- replay tools
- experiment logging
- trajectory export for training systems

### Remaining gaps

The main gap is schema richness, not lifecycle shape.

Quenda still needs:

- richer event payload conventions
- explicit trace schema stabilization

But the underlying lifecycle model is already a strong fit.

## 5. Reflection and verification methods

Representative work:

- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)

### Current fit

Support level:

- `Partial`

Reason:

- the current model has a strong `LoopDecision` concept
- that creates a natural place to ask "what should happen next"
- but there is no explicit `VerificationPhase` or `ReflectionPhase`

So these methods can be approximated through policy logic, but not yet
modeled as first-class lifecycle states.

### Remaining gaps

Recommended additions:

- `VerificationRunning`
- `ReflectionRunning`

Recommended transitions:

- `ModelResponded -> VerificationRunning`
- `ToolBatchCompleted -> VerificationRunning`
- `VerificationRunning -> LoopDecision`
- `VerificationRunning -> Completed`
- `VerificationRunning -> Failed`

This would allow verification to become a true runtime phase instead of
an implied side behavior.

## 6. Memory-centric agent methods

Representative work:

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- recent memory management and poisoning research

### Current fit

Support level:

- `Partial`

Reason:

- `Session`, `Run`, `ContextPrepared`, and `CompressionCheck` provide a
  good starting structure
- the existing compression seam already shows memory-like lifecycle
  behavior
- but memory is not yet represented as an explicit phase family

### Remaining gaps

Recommended additions:

- `MemoryReadRunning`
- `MemoryWriteRunning`
- `MemoryCompactionRunning`

Recommended transition boundaries:

- `CompressionCheck -> MemoryCompactionRunning`
- `Started -> MemoryReadRunning -> ContextPrepared`
- `ToolBatchCompleted -> MemoryWriteRunning -> LoopDecision`
- `Completed -> MemoryWriteRunning`

These additions would better support:

- episodic memory
- semantic retrieval
- memory trust filtering
- poisoning defenses
- selective writeback

## 7. Search, branching, and workflow optimization

Representative work:

- [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601)
- [Tree Search for Language Model Agents](https://arxiv.org/abs/2407.01476)
- [AFlow: Automating Agentic Workflow Generation](https://arxiv.org/abs/2410.10762)

### Current fit

Support level:

- `Weak to Partial`

Reason:

- current lifecycle is mostly linear
- `LoopDecision` is useful, but it only implies one next transition at a
  time
- there is no first-class notion of branch, candidate, rollback, or
  branch evaluation

This means search methods can be built above Quenda, but not yet in a
smooth native way.

### Remaining gaps

Recommended additions:

- `BranchCreated`
- `BranchEvaluating`
- `BranchSelected`
- `BranchPruned`

Recommended conceptual units:

- `Branch`
- `CandidateState`
- `SearchDecision`

Recommended transition shapes:

- `LoopDecision -> BranchEvaluating`
- `BranchEvaluating -> ModelInvoking`
- `BranchEvaluating -> ToolPhaseRunning`
- `BranchEvaluating -> BranchSelected`
- `BranchSelected -> LoopDecision`
- `BranchEvaluating -> BranchPruned`

This does not mean search should be pushed into core immediately, but it
does mean the lifecycle should eventually leave room for it if Quenda
wants to support search-heavy agent research smoothly.

## 8. Multi-agent orchestration

Representative work:

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)

### Current fit

Support level:

- `Partial`, but at the substrate layer

Reason:

- the current lifecycle is good as a single-agent execution substrate
- `Run`, `TraceSink`, `LoopDecision`, and future policies are exactly
  the kinds of surfaces upper-layer orchestration systems need
- but orchestration itself should still remain above core

This matches Quenda's architectural direction.

### Remaining gaps

No immediate core-lifecycle state expansion is required solely for
multi-agent support.

What is required is:

- reliable single-agent lifecycle semantics
- clean trace export
- clean interruption / completion / failure boundaries

That is already the right direction.

## What the Current Design Supports Well

The current terminology and lifecycle already support these research
needs well:

- linear model-tool loops
- step-level observation
- budget-based stopping
- trace export
- comparison of policy implementations
- single-agent substrate use by larger systems

This is a strong baseline.

## What the Current Design Does Not Yet Support Smoothly

The current design does not yet fully support:

- explicit verification phases
- explicit memory read / write phases
- branch and candidate-level search execution
- Runtime-owned tool gating and result shaping
- rich transition control beyond linear continue-or-stop decisions

These are the most important next gaps.

## Recommended Next-Phase Expansion

If Quenda wants to better support the current research frontier, the next
phase of lifecycle expansion should prioritize three categories.

### Priority 1: Verification and Reflection

Recommended new states:

- `VerificationRunning`
- `ReflectionRunning`

Reason:

- these are broadly useful
- they fit naturally into the current lifecycle
- they unlock Reflexion / CRITIC-style methods more cleanly

### Priority 2: Memory Lifecycle Phases

Recommended new states:

- `MemoryReadRunning`
- `MemoryWriteRunning`
- `MemoryCompactionRunning`

Reason:

- memory is central to long-running agents
- compression already points in this direction
- this helps unify context assembly, memory, and compression

### Priority 3: Branch and Search Units

Recommended new concepts:

- `Branch`
- `CandidateState`
- `SearchDecision`

Recommended optional states:

- `BranchEvaluating`
- `BranchSelected`
- `BranchPruned`

Reason:

- current lifecycle is still too linear for search-heavy agent research

This should likely remain later than verification and memory in actual
implementation order, but it should now be recognized as a lifecycle
design target.

## Recommended Evolution Order

Suggested next-phase order:

1. keep current linear lifecycle as the stable base
2. add verification / reflection phase support
3. add memory read / write phase support
4. move tool-call approval and tool-result writeback ownership into
   Runtime
5. introduce optional branch/search lifecycle extensions

This sequence keeps the architecture evolvable without destabilizing the
current execution model too early.

## Final Recommendation

Quenda's current terminology and runtime lifecycle already support a large
and important subset of current agent research, especially:

- ReAct-style loops
- tool-use experiments
- stopping-control strategies
- trace-based evaluation

That means the current design is already a strong foundation.

However, if Quenda wants to support the broader frontier of agent
research more smoothly, the next lifecycle expansion should explicitly
add:

- verification / reflection phases
- memory read / write phases
- optional branch/search concepts

The right next move is not to abandon the current lifecycle, but to
extend it in these directions while keeping Runtime as the owner of
state transitions and strategy invocation.
