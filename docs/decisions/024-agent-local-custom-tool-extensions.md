# ADR-024: Agent-Local Custom Tool Extensions

## Status

Accepted (2026-06-30)

## Context

Quenda already supports custom tool authoring in two important ways:

- users can define tools with `@tool`
- users can implement the `Tool` protocol directly

Quenda also now supports Host-owned capability-style built-in tool
resolution through agent configuration, such as:

- `tools.bundles`
- `execution.python.allowed_modules`

However, Quenda still lacks a complete agent-package mechanism for:

1. registering custom tools from agent-owned files
2. resolving those custom tools by name from `config.yaml`
3. composing them together with built-in bundles into one final granted
   tool set

This creates an important gap.

Today, downstream users can do this:

```python
agent = Agent(name="x", tools=[my_tool], model=model)
```

but they cannot yet cleanly do this:

```text
my-agent/
├── AGENT.md
├── config.yaml
└── extensions/
    └── tools/
        └── my_tool.py
```

with:

```yaml
tools:
  bundles:
    - core
  include:
    - my_tool
```

and expect Host to discover, register, and resolve `my_tool`
automatically.

Quenda needs a formal decision for this packaging and resolution model.

## Decision

Quenda should support **agent-local custom tool extensions** as a
Host-owned extension mechanism.

The official convention should be:

```text
<agent-package>/extensions/tools/
```

Host should:

- discover tool modules from that directory
- load exported tools into a Host-owned registry
- resolve `config.yaml.tools.include` against that registry
- combine those tools with built-in bundles
- pass the final resolved tool list into Runtime

Runtime and Kernel should not know whether a tool came from:

- built-in bundles
- agent-local custom extensions
- future skill-provided sources

## Architectural Boundary

This decision follows the existing Host boundary:

- Host loads and composes agent capabilities before Runtime execution
- Runtime receives the final tool list
- Kernel only executes tools

Custom tool registration is therefore a Host concern, not a Runtime
concern.

This is consistent with:

- `ADR-003` Host owns loading, trust, and composition
- `ADR-010` commands are agent-local Host extensions
- the newer capability-request direction where Host resolves final
  granted capabilities

## Directory Convention

Agent-local custom tools should live under:

```text
extensions/tools/
```

This keeps tool extensions parallel to:

- `extensions/commands/`
- `extensions/interactions/`

and makes the agent package structure more uniform.

## Loading Contract

Each `extensions/tools/*.py` module should export one of the following.

### Option A: `tools` list

Recommended:

```python
from quenda import tool


@tool
def search_docs(query: str) -> str:
    """Search internal docs."""
    ...


tools = [search_docs]
```

### Option B: `register` function

For advanced or stateful cases:

```python
def register(registry: ToolRegistryBuilder) -> None:
    registry.register(search_docs)
    registry.register(MyStatefulTool(...))
```

The `tools` list form should be the primary path.

## Config Semantics

`config.yaml` should support:

```yaml
tools:
  bundles:
    - core
    - network
  include:
    - search_docs
    - query_issue_tracker
```

Semantics:

- `bundles` requests named built-in or future bundle-level capabilities
- `include` requests individually named tools

Phase 1 should resolve `include` against:

1. built-in named tools
2. agent-local custom tools

Later phases may extend this to other sources.

## Resolution Model

Host should use one unified resolution path:

1. initialize built-in bundles and built-in named tools
2. discover and register agent-local custom tools
3. expand requested bundles
4. resolve requested `include` names
5. deduplicate by tool name
6. instantiate the final granted tool set

This keeps built-in and custom tools under the same capability
resolution model.

## Name Collision Rule

Agent-local custom tools should **not** silently override built-in tool
names in phase 1.

Recommended rule:

- duplicate tool names are a Host loading error

Reason:

- tool names are model-facing API surface
- silent override would make behavior hard to predict
- tool identity should be stricter than slash-command override

If override is ever needed later, it should require an explicit policy
or configuration setting.

## Error Handling

Phase-1 loading errors should be explicit:

- invalid tool module: fail agent setup
- malformed export contract: fail agent setup
- unknown `tools.include` name: fail agent setup
- duplicate tool name: fail agent setup

Reason:

An agent package that references unavailable tools is internally
inconsistent. Silent fallback would be difficult to debug and would
weaken trust in the packaging model.

## Relationship To Capability Requests

This feature should fit into the broader capability-request model rather
than bypassing it.

That means:

- `bundles` and `include` are requests
- Host still produces the final granted tool set

This leaves room for future Host policy to decide:

- whether agent-local custom tools are allowed at all
- whether certain environments restrict them
- whether only trusted packages may use them

Phase 1 does not require a full trust or approval system, but it should
not assume that custom tools are automatically unrestricted forever.

## Relationship To Skills

This decision should remain compatible with the emerging Skills model.

Longer term, Quenda may need to resolve tools from multiple sources:

1. built-in
2. agent-local
3. skill-provided

That is why the resolution model should already be source-aware at the
Host layer, even if phase 1 only implements built-in and agent-local
sources.

## Non-Goals

This ADR does not require phase 1 to support:

- marketplace-distributed tools
- remote tool installation
- skill-provided executable tools
- per-tool permission prompts
- tenant-specific tool catalogs
- provider-specific tool filtering
- fully general dependency injection into tools

Those can build later on top of this mechanism.

## Implementation Direction

Recommended Host-side additions:

- `load_agent_tools(agent_path: Path) -> LoadedToolCatalog`
- a small Host-owned tool registry / builder
- `_resolve_tools(..., loaded_tool_catalog)` support for custom names

This should be implemented as an extension of existing Host loading and
capability resolution, not as a Runtime feature.

Supporting design draft:

- [agent-local-custom-tool-registration-and-config-resolution.md](/Users/xushiting/Workspace/quenda/docs/architecture/agent-local-custom-tool-registration-and-config-resolution.md)

## Consequences

### Positive

- closes the gap between custom tool authoring and agent-package
  distribution
- gives downstream agent authors a clean declarative packaging model
- keeps Runtime and Kernel boundaries clean
- aligns tool extensions with existing command and interaction
  extensions
- prepares Quenda for later multi-source tool resolution

### Negative

- adds another dynamic loading path in Host
- requires duplicate detection and clearer error reporting
- may later require trust policy refinement for custom tool sources

### Risks

- if built-in and custom tool names are not handled strictly, tool
  identity will become confusing
- if custom tool loading bypasses capability resolution, the overall
  permission model will fragment
- if source tracking is ignored now, future skill/tool unification will
  become harder

## Final Rule

Quenda should treat **agent-local custom tools as Host-discovered,
config-resolved extensions**, not as Runtime features and not as
implicit Python-side side effects.
