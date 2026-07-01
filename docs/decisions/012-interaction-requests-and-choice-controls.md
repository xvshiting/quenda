# ADR-012: Interaction Requests and Extensible Choice Controls

## Status

Accepted

## Context

Quenda needs a structured way to pause execution and ask the user to make a choice.

This is not a tool call. Tools are for acting on the world. Choices are for asking a human to decide when the agent should not guess blindly.

Common examples:

- choosing between multiple valid next steps
- confirming a risky action
- selecting a provider/model/session from current state
- picking one item from a menu of candidates

LLMs can help generate the candidate options and explanatory text, but the framework must not rely on ad hoc markdown markers or brittle string matching to detect these moments.

## Decision

Quenda should provide a structured interaction request protocol:

- `InteractionRequest` for host-side choice/confirm/input/menu requests
- `InteractionResponse` for user selections
- `InteractionRegistry` for built-in and agent-local interaction kinds

### Core shape

```python
InteractionRequest(
    kind="choice",
    title="Next step",
    message="What would you like me to do?",
    options=[
        InteractionOption(id="read", label="Read more files"),
        InteractionOption(id="edit", label="Start editing"),
    ],
)
```

The request is a structured object, not a prompt convention.

### Built-in interaction kinds

Quenda should ship with a small set of common kinds:

- `choice`
- `confirm`
- `input`
- `menu`

These are the most common human-in-the-loop patterns needed by agents.

### Where the decision happens

The control flow should be:

1. LLM or Host produces an `InteractionRequest`
2. Host validates the request against the registered interaction kind
3. Interface renders the request
4. User responds
5. Host applies the response and continues

The LLM may propose the request, but Host decides whether it is valid and whether to display it.

### Extensibility model

Interaction kinds should be extensible in the same spirit as commands.

Agent packages may define additional interaction handlers under:

```text
extensions/interactions/*.py
```

Loading contract:

- `interactions` list of interaction handlers, or
- `register(registry)` function

This lets agent authors add custom interaction kinds without changing Quenda framework code.

## Why This Fits Quenda

This follows the same separation pattern as commands:

- Kernel remains unaware
- Runtime remains focused on execution semantics
- Host owns the structured control plane
- Interface owns rendering and input

It also keeps the system explicit:

- the request is a data structure
- the response is a data structure
- the extension point is a registry
- the UI is a presentation concern

## Non-Goals

This ADR does not define:

- a full UI framework
- a modal dialog system
- remote interaction services
- arbitrary markdown-based detection of choice requests
- automatic LLM decision making without Host validation

## Consequences

### Positive

- choice points are explicit and serializable
- Host can validate and gate interaction requests
- UI can render the same request in CLI, TUI, or web
- agent-local extensions can add custom interaction kinds

### Negative

- more framework surface area
- extra loader and registry code
- UI consumers must handle structured requests, not just plain text

## Recommendation

Quenda should adopt structured interaction requests as the framework primitive for choice/confirm/input/menu flows, and expose them through an extensible registry that can be loaded from agent packages.
