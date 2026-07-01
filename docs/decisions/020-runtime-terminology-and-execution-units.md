# ADR-020: Runtime Terminology and Execution Units

## Status

Proposed (2026-06-26)

## Context

Kora is moving toward a more explicit lifecycle model for hooks,
policies, and runtime control.

That work is difficult to do well if the project uses core execution
terms inconsistently. In recent design discussions, several terms have
been used with overlapping or unstable meanings:

- session
- run
- turn
- step
- tool call
- tool batch
- tool phase
- completion
- termination
- interruption

This ambiguity creates several problems:

- hook boundaries become unclear
- policy contracts become overloaded
- state transitions are hard to specify precisely
- different documents can appear to agree while actually describing
  different levels of execution

Kora needs a stable terminology layer before it can define a durable
lifecycle state machine or policy system.

## Decision

Kora should standardize the following execution terms and use them
consistently in architecture, API design, and implementation work.

## Core Execution Units

### Session

A `Session` is the durable conversation state for an agent over time.

It owns:

- message history
- summary blocks
- archive references
- usage accumulation
- persistent metadata

A session may contain many runs.

### Run

A `Run` is one execution of the agent runtime against one new user
message inside a session.

It is the primary unit for:

- execution lifecycle
- event emission
- hook invocation
- interruption
- completion
- failure

In the current design, one user message normally creates one run.

### Turn

A `Turn` is a user-facing conversational unit, not the primary runtime
control unit.

In the current Kora design, one run usually corresponds to one agent
turn, but these concepts should remain distinct:

- `Run` is a runtime object
- `Turn` is a conversational concept

This distinction leaves room for future designs where a single run may
contain richer internal phases without changing the user-facing notion
of a turn.

### Step

A `Step` is one observable unit emitted during run execution.

For the current Kernel/Runtime structure, the primary step kinds are:

- model step
- tool step

Step is the right term for event- and trace-level observation.

It is not the same thing as a turn, and it is smaller than a run.

## Model and Tool Units

### Model Step

A `Model Step` is one model invocation plus its response.

Its output may contain:

- final content
- tool calls
- a stop reason

This is the smallest unit that advances reasoning in the
model-tool loop.

### Tool Call

A `Tool Call` is one requested invocation of one tool with one argument
payload.

It is the smallest execution unit in the tool layer.

### Tool Batch

A `Tool Batch` is the ordered list of tool calls returned by one model
step.

The model may request zero, one, or many tool calls in a single batch.

This is an important unit because many policies should reason about:

- the entire requested batch
- not only a single tool call in isolation

### Tool Execution Step

A `Tool Execution Step` is one completed execution of one tool call,
producing one tool result.

This is the step-level observation unit for tools.

### Tool Phase

A `Tool Phase` is the execution interval covering the entire tool batch
returned by one model step.

It begins when the runtime accepts a tool batch for execution.

It ends when:

- all approved tool calls in the batch are finished
- or the batch is aborted, interrupted, or otherwise stopped

This term is useful because some hooks should operate on:

- individual tool calls
- the entire batch
- or the phase boundary itself

## Control and Transition Terms

### Loop Decision

A `Loop Decision` is a runtime-owned decision about what should happen
after a phase boundary.

Typical outcomes include:

- invoke the model again
- execute a tool batch
- complete the run
- terminate the run by policy
- interrupt the run
- fail the run
- enter a future verification or reflection phase

This is the most important control term for future policy design.

### Hard Guard

A `Hard Guard` is a non-optional execution safety limit enforced by the
runtime engine itself.

Example:

- `Kernel.max_iterations`

Hard guards exist to prevent runaway execution even when no custom
policy is configured.

### Policy

A `Policy` is a configurable strategy that influences lifecycle
behavior.

Unlike a hard guard, a policy is intended to be:

- replaceable
- configurable
- agent-specific

Examples:

- compression policy
- termination policy
- tool selection policy

## Outcome Terms

### Completion

A `Completion` means the run reaches a natural successful end according
to the runtime loop.

Examples:

- model returns terminal content
- tool loop finishes and the next model step ends normally

Completion is a success outcome.

### Termination

A `Termination` means the run stops because a runtime policy decides it
should stop.

Examples:

- max step budget reached
- token budget exceeded
- repeated no-progress behavior detected

Termination is not necessarily a failure. It is a policy-driven stop.

### Interruption

An `Interruption` means execution stops because of an external stop
signal.

Examples:

- user presses Ctrl+C
- a host environment cancels the run

Interruption is externally triggered, not policy-triggered.

### Failure

A `Failure` means execution stops because of an unhandled error or a
runtime-level unrecoverable condition.

Examples:

- model invocation error
- unexpected tool execution failure that cannot be recovered
- runtime bug

Failure is distinct from both completion and policy termination.

## Recommended Usage Rules

To keep future design consistent, Kora should follow these rules.

### 1. Use `Run` as the primary hook and trace unit

Hooks, traces, and lifecycle policies should anchor themselves to the
run, not to the loosely defined term "turn".

### 2. Use `Step` for observable execution increments

Step is the right term for runtime event emission and trace records.

### 3. Use `Tool Batch` and `Tool Phase` explicitly

This is important because many future policies will need access to:

- the full requested tool batch
- the full set of tool results from that batch

### 4. Separate outcome terms cleanly

Do not use "termination" as a generic synonym for every kind of stop.

Kora should distinguish:

- completion
- termination
- interruption
- failure

### 5. Separate hard guards from policies

Kernel-level safety guards should not be described as policies.

Runtime-level configurable decisions should not be described as engine
guards.

## Relationship to Future Lifecycle Work

This ADR is a prerequisite for the runtime lifecycle state machine.

In particular:

- `Run` defines the lifecycle container
- `Model Step`, `Tool Batch`, and `Tool Phase` define key state-machine
  units
- `Loop Decision` defines the runtime-owned transition concept
- outcome terms define terminal states clearly

## Consequences

### Positive

- makes hook contracts easier to define precisely
- improves consistency across ADRs and architecture documents
- reduces ambiguity in policy naming
- makes the future state machine easier to understand

### Negative

- some current documents may need wording cleanup
- some current uses of "termination" and "turn" will need to be narrowed

## Recommendation

Kora should adopt this terminology as the baseline vocabulary for all
future hook, lifecycle, and runtime-control work.
