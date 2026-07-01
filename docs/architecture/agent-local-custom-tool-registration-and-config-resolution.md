# Agent-Local Custom Tool Registration and Config Resolution

## Status

Draft (2026-06-30)

## Purpose

This document defines how Quenda should support **agent-local custom
tools** that are:

- implemented in Python inside an agent package
- discoverable by Host
- selectable from `config.yaml`
- composed together with built-in tool bundles and future capability
  policy

The key goal is to close the current gap between:

- programmatic custom tool injection
- and agent-package-based declarative tool configuration

## Problem Statement

Quenda already supports custom tools in one important sense:

- users can define tools with `@tool`
- users can implement the `Tool` protocol directly
- users can pass those tools programmatically into `Agent(..., tools=[...])`

However, Quenda does **not** yet provide a complete agent-package
mechanism for:

1. registering custom tools from agent-owned files
2. resolving those custom tools by name from `config.yaml`
3. combining them with built-in bundles such as `core` and `network`

That means current support is split:

- **programmatic injection exists**
- **agent-local declarative registration does not**

This is a usability and packaging gap for downstream agent authors.

## Current State

Today, tool-related capabilities are spread across three separate
systems.

### 1. Tool definition exists

Quenda supports:

- `@tool`
- direct `Tool` implementations

This is the authoring layer.

### 2. Built-in capability resolution exists

Host currently supports capability-style built-in tool resolution via:

- `tools.bundles`
- `execution.python.allowed_modules`

and resolves those inside `host/runner.py`.

This is the built-in capability layer.

### 3. Agent-local custom tool loading does not exist yet

There is currently no formal equivalent of:

- `extensions/commands/*.py`
- `extensions/interactions/*.py`

for tools.

There is also no complete path where:

- a custom tool is loaded into a Host-owned registry
- `config.yaml` references that tool by name
- Host resolves it into the final granted tool set

## Design Goal

Quenda should support this user experience:

```text
my-agent/
├── AGENT.md
├── config.yaml
├── instructions/
└── extensions/
    └── tools/
        ├── search_docs.py
        ├── query_issue_tracker.py
        └── ...
```

with:

```yaml
tools:
  bundles:
    - core
  include:
    - search_docs
    - query_issue_tracker
```

and Host should:

1. load built-in bundles
2. load agent-local custom tools
3. resolve named includes
4. build the final tool set

without Runtime or Kernel needing to know where those tools came from.

## Architectural Principle

This feature should follow the same boundary rule as commands, skills,
and capability resolution:

- **Host discovers and composes**
- **Runtime receives final tools**
- **Kernel only executes tools**

Custom tool registration is therefore a Host concern, not a Runtime
concern.

## Proposed Directory Convention

Agent-local custom tools should live in:

```text
<agent-package>/extensions/tools/
```

This matches the existing extension conventions:

- `extensions/commands/`
- `extensions/interactions/`

and keeps the packaging model consistent.

## Proposed Loading Contract

Each `extensions/tools/*.py` module should export one of the following.

### Option A: `tools` list

Recommended:

```python
from quenda import tool


@tool
def search_docs(query: str) -> str:
    """Search the internal documentation index."""
    ...


tools = [search_docs]
```

This matches the existing commands pattern and is easy to understand.

### Option B: `register` function

For dynamic or stateful registration:

```python
def register(registry: ToolRegistryBuilder) -> None:
    registry.register(search_docs)
    registry.register(QueryIssueTrackerTool(...))
```

This should remain a secondary path for advanced cases.

## Proposed Host-Level Objects

Quenda should introduce a small Host-owned tool registration model.

### 1. `ToolRegistryBuilder`

A mutable Host-side builder used during loading.

Responsibilities:

- register built-in named tools
- register built-in bundles
- register agent-local custom tools
- reject duplicate names when needed

### 2. `NamedToolSpec`

Represents one resolved tool candidate before instantiation.

Suggested fields:

- `name`
- `source`
- `factory`
- `kind`

Where `source` may be:

- `builtin`
- `agent_local`
- later, `skill`

### 3. `ResolvedToolSet`

Represents the final granted tool instances for an agent/session.

This is what Runtime receives.

## Proposed Config Semantics

`config.yaml` should distinguish:

- tool bundle requests
- individual tool requests

Recommended shape:

```yaml
tools:
  bundles:
    - core
    - network
  include:
    - search_docs
    - query_issue_tracker
```

### Meaning

- `bundles` requests named built-in or future custom bundles
- `include` requests individually named tools

Phase-1 scope should resolve `include` against:

1. built-in named tools
2. agent-local custom tools

Later phases may extend that to:

3. skill-provided tools
4. workspace-provided tools

## Resolution Order

Recommended phase-1 resolution order:

1. initialize built-in bundle registry
2. load built-in named tools
3. load agent-local custom tools from `extensions/tools/`
4. expand requested bundles
5. resolve `include` names
6. deduplicate by tool name
7. return final tool instances

This keeps built-in capabilities and custom tools on one unified
resolution path.

## Name Collision Policy

This area should be explicit.

### Recommended phase-1 rule

- agent-local custom tools may **not** silently override built-in tool
  names
- duplicate names should raise a Host-visible loading error

Reason:

- tool identity must remain predictable
- tool name is part of the model-facing interface
- silent override is higher risk here than it is for slash commands

Commands and tools should not necessarily share the same override rule.

### Possible future rule

If override becomes necessary later, it should require an explicit
setting, not be implicit.

## Workspace And State Injection

One practical difference between tools and commands is that many tools
need runtime context such as:

- workspace root
- storage
- configured clients
- trust policy

Therefore the loading system should support both:

- already-instantiated tools
- factories that Host can instantiate with context

### Recommended abstraction

Agent-local tool registration should allow:

- plain `Tool` instances
- zero-argument factories
- Host-context-aware factories

But phase 1 should keep the public contract simple and prefer:

- plain `Tool` instances
- or small factories with explicit supported inputs

Avoid exposing large mutable Host objects directly.

## Relationship To Capability Request Model

Custom tool registration should fit into the broader capability model,
not bypass it.

Recommended distinction:

- `bundles` and `include` are **requests**
- Host still produces the final granted tool set

That means future Host policy can decide:

- whether agent-local custom tools are allowed at all
- whether only trusted agent packages may load them
- whether certain tool classes require extra approval

Phase 1 does not need a full trust policy, but the resolution design
should leave room for one.

## Relationship To Skills

This proposal should be compatible with the emerging skills model.

Longer term, Quenda may need to resolve tools from three origins:

1. built-in
2. agent-local
3. skill-provided

That is why the registry should already track `source`.

The custom-tool system should not be designed in a way that later makes
skill-provided tools feel like a separate incompatible mechanism.

## Recommended Loading Flow

Phase-1 Host flow should look like this:

```text
load_agent_package()
  -> load built-in tool registry
  -> load agent-local custom tools
  -> read config.yaml tool requests
  -> resolve bundles and include names
  -> instantiate final tool list
  -> create Agent(...)
```

This should happen in Host before Runtime execution begins.

## Proposed New Host APIs

These names are illustrative, not mandatory.

### Loader-side

- `load_agent_tools(agent_path: Path) -> LoadedToolCatalog`
- `load_tool_module(path: Path) -> module`

### Registry-side

- `ToolRegistryBuilder.register(tool: Tool, *, source: str) -> None`
- `ToolRegistryBuilder.register_factory(name: str, factory: ...) -> None`

### Runner-side

- `_resolve_tools(workspace, config, loaded_tool_catalog) -> list[Tool]`

## Error Handling

Tool loading failures should be explicit.

Recommended phase-1 rules:

- invalid tool module: fail agent setup with a clear message
- duplicate tool name: fail agent setup
- unknown `tools.include` entry: fail agent setup
- malformed export contract: fail agent setup

Reason:

If `config.yaml` references a tool that is not actually available, the
agent package is internally inconsistent. Silent fallback would be hard
to debug and unsafe.

## What This Proposal Does Not Solve

This proposal is intentionally narrow.

Out of scope:

- remote tool distribution
- marketplace-installed tools
- permission prompts for individual custom tools
- skill-provided executable tools
- tenant-specific tool catalogs
- fine-grained tool trust annotations
- provider-specific tool filtering

Those should build on top of this mechanism, not be bundled into it.

## Recommended Phase Plan

### Phase 1: Agent-local discovery

- add `extensions/tools/` convention
- add Host loader for tool modules
- support `tools` list export
- support `config.yaml.tools.include` resolution
- support duplicate detection

### Phase 2: Factory-aware instantiation

- add support for context-aware tool factories
- allow workspace or Host resource injection where needed

### Phase 3: Policy-aware resolution

- integrate with Host capability grant / trust policy
- support deny / allow / downgrade semantics

### Phase 4: Unified source model

- unify built-in, agent-local, and future skill-provided tools into one
  source-aware registry

## Recommendation

Quenda should implement **agent-local custom tool registration as a Host
extension mechanism**, parallel to command and interaction extensions,
and should wire `config.yaml.tools.include` into that registry-based
resolution path.

The correct mental model is:

- tool authoring is already solved
- tool packaging and declarative resolution are not

This proposal solves the second problem without changing Runtime or
Kernel boundaries.
