# ADR-008: Tool Schema as Single Source of Truth

## Status

Accepted

## Context

Previously, agent definitions like `AGENT.md` might contain manual descriptions of available tools, their parameters, and usage guidelines. This creates several problems:

1. **Duplication**: Tool information exists in both Tool code and agent prompts
2. **Inconsistency**: Manual descriptions can drift from actual Tool definitions
3. **Maintenance burden**: Changes to tools require updating multiple places
4. **Single source of truth violation**: Which description is authoritative?

## Decision

Tool definitions are the single source of truth for tool information.

### Principles

1. **Tool code defines capabilities**: Each Tool's `name`, `description`, and `parameters` describe what it does and how to use it.

2. **Framework generates tool context**: The system automatically constructs tool-related prompt content from registered tools. This happens at the Kernel layer when calling the model.

3. **AGENT.md focuses on behavior**: Agent prompts describe roles, principles, workflows, and decision-making patterns—not tool inventories.

4. **instructions/*.md describe workflows**: Modular instruction files contain domain-specific guidance (e.g., coding practices, git workflows), not tool catalogs.

### What Goes Where

| Content | Location |
|---------|----------|
| Tool name, description, parameters | Tool class definition |
| Tool availability | Framework (from registered tools) |
| When to use which tool | Model decides from schema |
| General work principles | AGENT.md / instructions/*.md |
| Domain workflows | instructions/*.md |

### What to Avoid

- Listing tools in AGENT.md with descriptions like "Use `read_file` to read files"
- Maintaining a separate `tools.md` instruction file
- Duplicating parameter descriptions that exist in Tool definitions
- Hardcoding tool names in agent prompts

## Consequences

### Positive

- Single source of truth eliminates drift
- Tool changes automatically reflected in model context
- AGENT.md stays focused and concise
- Easier to add/remove tools without updating prompts

### Negative

- Less control over tool descriptions in prompt (but tool.description should be sufficient)
- Requires good tool descriptions in Tool definitions

## Implementation

1. Ensure each Tool has a clear, useful `description` property
2. Remove any tool-specific instructions from agent packages
3. Framework already handles tool schema injection in model calls

## References

- `src/quenda/kernel/tool.py` - Tool interface
- `src/quenda/kernel/loop.py` - Tool registration and execution
- `src/quenda/providers/api/converters.py` - Tool schema conversion for model API
