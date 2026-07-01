# Slash Command System Enhancement Proposal

## Status

Draft (2026-06-26)

## Purpose

This document aligns terminology and direction for improving Kora's
slash command system, so later discussions do not mix up `menu`,
`interaction`, `completion`, and `command` concerns.

It answers four questions:

- which system we are actually discussing
- how its terms and boundaries should be defined
- which layer should evolve first
- how to choose between the two proposed solution directions

## Problem Statement

Kora already has a functioning slash command system:

- `Command` protocol
- `CommandRegistry`
- `ReplRuntime.execute_command()`
- `CommandCompleter`

But it still behaves mostly like a string-based command executor. It is
weak in several areas:

- argument completion is limited
- most commands do not implement `get_completions()`
- the system cannot express multi-stage parameter selection
- dynamic candidates such as providers, models, and sessions are not
  represented cleanly
- command semantics and input presentation are too tightly coupled

As a result, commands like `/model`, `/session`, and `/mode` are still
largely driven by:

- manual argument entry
- textual help output
- simple string completion

rather than richer command-native behaviors such as:

- command discovery
- subcommand navigation
- parameter candidate display
- dynamic candidate loading

## Terminology Consensus

To avoid future confusion, the project should use the following terms
consistently.

### 1. Slash Command System

The system composed of commands such as `/model`, `/session`, `/mode`,
and `/context`.

It owns:

- command discovery
- command parsing
- argument completion
- argument candidates
- command execution

It is not the same thing as selector UI, nor the interaction system.

### 2. Interaction System

The generic interaction protocol built around `InteractionRequest`,
`InteractionRegistry`, and `choice / confirm / input / menu`.

It owns:

- one-off human interaction requests
- confirmation
- single-choice selection
- input requests
- flat menu selection

It should not become the core abstraction of the slash command system.

### 3. Command Completer

The `prompt_toolkit` input completer used during REPL input.

It is a UI entry point for the slash command system, not the command
system itself.

It owns:

- displaying candidates during typing
- improving input ergonomics

It should not own command semantics or business rules.

### 4. Selector

The UI control that displays a list of options and supports arrow-key
selection.

It is a rendering capability, not a command abstraction.

It may be reused by both interaction flows and command flows, but it
should not define their semantics.

### 5. Command Navigation

The command-system capability for:

- subcommand discovery
- parameter-candidate display
- multi-stage argument selection
- dynamic candidate loading

This is the capability this proposal aims to improve.

## Scope Clarification

This proposal is about:

- slash command system evolution
- command-aware completion
- command-native candidate resolution

This proposal is not about:

- LLM-triggered `InteractionRequest`
- independent selector evolution
- a separate command-palette product surface
- full TUI / web navigation systems

## Current State

The current system can be summarized as follows.

### Existing strengths

- command protocol is already explicit
- registration and execution responsibilities are centralized
- `ReplRuntime` already owns host-level command orchestration
- `get_completions()` already exists as an extension point

### Existing limitations

- `get_completions()` returns only strings, which is too weak
- commands cannot expose structured candidates
- `CommandCompleter` can only consume string results
- dynamic commands like `/model` and `/session` have no full candidate
  strategy
- there is no abstraction for command-level multi-stage resolution

## Decision Framing

Two candidate directions have been proposed.

### Option A: Enhance the Command Protocol

Give commands richer responsibilities so they can define:

- what candidates exist at the current stage
- whether the current arguments are complete
- whether the next step is completion, selection, or execution

### Option B: Enhance CommandCompleter

Push the logic primarily into the completer:

- stage 1 completes command names
- stage 2 displays parameter or submenu options

## Recommendation

Recommended direction:

- **Option A should lead the architecture**
- **Option B should exist as a UI-layer enhancement**

In practice:

- the command system should provide structured candidate and resolution
  behavior
- `CommandCompleter` should consume that behavior and present it

The inverse dependency is not recommended.

## Why Option A Should Lead

### 1. Command semantics belong to the command system

Valid parameters, available subcommands, and dynamic candidates are all
command semantics. They should be defined by the command, not inferred
by an input widget.

### 2. Completer is UI, not business logic

If provider / model / session loading logic lives in the completer:

- logic becomes fragmented
- reuse decreases
- new front-ends must reimplement the same logic

### 3. Structured candidates are more durable than string completions

Future surfaces such as:

- tab completion
- dropdown suggestions
- selector popovers
- command palettes

can all consume the same command-native candidate model.

### 4. Individual commands can evolve independently

`/model`, `/session`, and `/mode` each need different behavior. Letting
each command define its own candidate semantics makes this easier to
evolve and test.

## Why `InteractionRequest` Should Not Be the Main Contract

Although `InteractionRequest` looks superficially similar to candidate
selection, the semantics are different.

`InteractionRequest` is better for:

- one-off confirmation
- one-off selection
- one-off input collection

The slash command system needs to express:

- command argument stage
- available command candidates
- command executability
- argument normalization

Recommendation:

- selector UI may be reused
- `InteractionRequest` should not become the command-protocol return
  type

## Proposed Architecture

Recommended architecture:

```text
Slash Command System
  -> Command protocol
  -> Command registry
  -> Command candidate resolution
  -> Command execution

Command Completer
  -> consumes command candidates

Selector
  -> optional UI for rich candidate display
```

### Responsibility split

`Command`

- defines name, description, and usage
- defines candidate and argument-resolution behavior
- executes the command

`ReplRuntime`

- coordinates command resolution and execution
- exposes a uniform entry point to UI surfaces

`CommandCompleter`

- shows candidates
- inserts or replaces input text

`Selector`

- renders candidates when a richer interface is needed

## Proposed API Direction

The system should evolve beyond:

```python
get_completions(args: str) -> list[str]
```

and move toward a structured candidate + resolution model.

### CommandCandidate

Recommended fields:

- `id`
- `label`
- `value`
- `description`
- `kind`

Suggested `kind` values include:

- `command`
- `subcommand`
- `provider`
- `model`
- `session`
- `mode`
- `argument`

### CommandResolution

Recommended fields:

- `status`
- `normalized_args`
- `message`

Suggested statuses:

- `ready`
- `needs_input`
- `invalid`

### Command capability direction

Future command interfaces could move toward:

- `get_candidates(args, context)`
- `resolve(args, context)`
- `execute(args, context)`

This is more durable than `get_sub_menu()` because it expresses command
resolution rather than one specific UI pattern.

## Evaluation of the Two Proposed Solutions

### Solution 1: Enhance Command Protocol

Conclusion:

- correct direction
- but it should not be named `get_sub_menu()`
- and it should not return `InteractionRequest`

It should evolve toward command-native candidate and resolution
interfaces.

### Solution 2: Enhance CommandCompleter

Conclusion:

- useful as a UI enhancement layer
- not suitable as the primary architecture

Its job should be:

- stage-1 command-name completion
- stage-2 display of structured candidates produced by commands

It should not:

- define provider / model / session business logic itself
- become the source of command semantics

## MVP Recommendation

Recommended minimal path:

### Phase 1

- align terminology
- extend command-protocol design
- preserve compatibility with the existing `get_completions()`

### Phase 2

- validate the model on `ModeCommand`
- extend it to `ModelCommand`
- extend it to `SessionCommand`

### Phase 3

- let `CommandCompleter` consume structured candidates
- optionally add richer selector-based rendering

## Backward Compatibility

Existing commands must continue to work.

Recommended strategy:

- commands that implement only `execute()` remain valid
- commands that implement only `get_completions()` remain consumable
- new capability should be introduced as an optional extension before it
  becomes required

## Risks

### Risk 1: Over-designed abstraction

If the slash command model becomes too generic too early, MVP delivery
will slow down.

Mitigation:

- keep the first candidate model small
- limit initial coverage to `mode`, `model`, and `session`

### Risk 2: UI and semantics become coupled again

If the completer continues to own business rules, maintainability will
degrade.

Mitigation:

- keep semantics inside the command protocol
- let UI consume structured results only

### Risk 3: Interface evolution increases migration cost

Mitigation:

- add a compatibility layer
- let old and new interfaces coexist for one transition period

## Final Recommendation

This work should be framed as:

- **Slash Command System Enhancement**

The project should align on five points:

1. the optimization target is the `Slash Command System`, not the
   `Interaction System`
2. `CommandCompleter` is a UI layer, not a command-semantics layer
3. command-protocol evolution should lead the architecture
4. `InteractionRequest` should not be the command submenu contract
5. the long-term direction should be structured candidates and
   multi-stage command resolution

## Suggested Next Step

The next design pass should define:

- the minimum field set for `CommandCandidate`
- the minimum field set for `CommandResolution`
- MVP behavior for `ModeCommand`, `ModelCommand`, and `SessionCommand`
- how `CommandCompleter` should consume both old and new command
  interfaces
