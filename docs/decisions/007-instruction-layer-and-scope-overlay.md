# ADR-007: Instruction Layer and Scope Overlay

## Status

Proposed

## Context

Quenda needs a clear model for composing agent instructions from multiple sources.

Survey of mainstream agent instruction systems:

- **Claude Code**: `CLAUDE.md` with user/project/local/managed policy scopes, `@path` imports, separation of rules vs skills
- **GitHub Copilot**: `.github/copilot-instructions.md` for repository-level, path-specific instructions in `.github/instructions/`
- **AGENTS.md**: Cross-tool convention for agent README, supports multiple in monorepos

Common patterns:
- Repository-level instructions auto-loaded
- Path/agent-level instructions can override
- Long-term rules separated from task-based skills

Quenda should adopt the core pattern but maintain its own layering.

## Decision

### File Responsibilities

```text
AGENT.md          = Agent identity and base system prompt (not just metadata)
config.yaml       = Machine-readable configuration
INSTRUCTIONS.md   = Scope overlay instructions
instructions/*.md = Modular, includable rules
resources/*.md    = Reference material, not injected by default
skills/*          = On-demand capability packages
```

### AGENT.md Structure

`AGENT.md` remains the agent's core definition:

```markdown
---
name: quenda-code
version: 0.1.0
description: Quenda's official coding agent
---

You are Quenda Code, an expert coding assistant...

[Base system prompt continues here]
```

It is **not** just metadata. It defines who the agent is and its base behavior.

### config.yaml Purpose

Machine-readable configuration that controls:

```yaml
model:
  provider: deepseek
  name: deepseek-v4-flash

tools:
  include:
    - core
    - filesystem
    - execution

instructions:
  include:
    - instructions/coding.md
    - instructions/git.md

session:
  max_turns: 100
```

### Scope Hierarchy

Instructions compose from multiple scopes:

```text
1. Quenda framework contract
2. Agent package AGENT.md
3. Agent package config.yaml included instructions
4. User global INSTRUCTIONS.md
5. User-agent INSTRUCTIONS.md
6. Workspace INSTRUCTIONS.md
7. Workspace-agent INSTRUCTIONS.md
8. Activated skills
```

Later scopes are more specific. The model should prioritize more specific instructions.

### Storage Locations

**Agent package** (shipped with agent):

```text
agents/quenda-code/
  AGENT.md
  config.yaml
  instructions/
    coding.md
    git.md
    testing.md
```

**Workspace-owned** (in target workspace):

```text
<workspace>/.quenda/
  workspace.yaml              # Workspace binding (Host-owned)
  INSTRUCTIONS.md             # Workspace-level instructions
  agents/
    quenda-code/
      INSTRUCTIONS.md         # Workspace + agent instructions
      config.yaml             # Workspace-agent config overlay
```

**User-private** (in user scope):

```text
~/.quenda/users/<user_id>/
  INSTRUCTIONS.md             # User global instructions
  agents/
    quenda-code/
      INSTRUCTIONS.md         # User-agent instructions
      workspaces/
        <workspace_id>/
          INSTRUCTIONS.md     # User-agent-workspace instructions
          config.yaml         # User-private workspace-agent config
```

### Composition Semantics

Instruction composition is **append-only**:

```text
- All instruction files are concatenated in order
- No automatic "same-name override" at prompt level
- Later scopes are more specific, but structurally all files are appended
- Conflict resolution is semantic, not structural
```

If override is needed, use config-level mechanisms:

```yaml
instructions:
  disable:
    - package:instructions/git.md  # Future feature, not MVP
```

MVP does not support instruction disable. All included instructions are appended.

### Template Variables

Template rendering with `{{variable}}` syntax applies to **instruction text files only**:

Supported files:
- `AGENT.md`
- `INSTRUCTIONS.md` (all scopes)
- `instructions/*.md`

NOT supported:
- `config.yaml`
- `workspace.yaml`

Allowed variables (Host whitelist):

```text
{{agent.name}}
{{agent.version}}
{{workspace.id}}
{{workspace.path}}
{{user.id}}
{{model.provider}}
{{model.name}}
{{date}}
{{session.id}}
```

No arbitrary expressions, loops, or conditionals. Simple string substitution only.

### Loading Timing

**Startup (once per agent initialization)**:

```text
- Agent package AGENT.md
- Agent package config.yaml
- Agent package included instructions (from config.yaml)
```

**Per-Run (before each user message)**:

```text
- User global INSTRUCTIONS.md
- User-agent INSTRUCTIONS.md
- Workspace INSTRUCTIONS.md
- Workspace-agent INSTRUCTIONS.md
- User-agent-workspace INSTRUCTIONS.md
```

This allows users to modify workspace instructions and see changes take effect immediately in the next turn.

**Skills**: Loaded when activated, can be cached for duration of session.

## Consequences

### Positive

- Clear separation: agent identity vs context instructions
- Users can customize behavior without modifying agent package
- Changes to workspace instructions take effect immediately
- Simple append-only composition is easy to understand and debug
- Template variables provide useful context without complexity

### Negative

- Multiple files to understand for new users
- Need to implement scope resolution and file watching
- Per-run loading adds I/O overhead (mitigated by caching small files)

## Implementation Notes

### MVP Scope

MVP implements:

1. Agent package `AGENT.md` + `config.yaml` loading at startup
2. Basic instruction composition (append in order)
3. Template variable substitution for whitelisted variables
4. Workspace `INSTRUCTIONS.md` per-run loading
5. User-agent `INSTRUCTIONS.md` (user preferences for specific agent)

**Deferred:**

1. ~~User-global scope instructions~~ - **Decided to skip**: Global user preferences are better suited for UI/settings rather than filesystem files. Agent-specific user preferences are kept.
2. User-agent-workspace scope
3. Skill activation
4. Instruction disable mechanism

### Host Loader Refactor

This ADR guides the next Host loader refactor:

```python
class InstructionComposer:
    def compose(
        self,
        agent_package: AgentPackage,
        workspace: WorkspaceBinding,
        user: User,
        session: Session,
    ) -> str:
        """Compose full instruction text."""
        parts = []

        # 1. Framework contract (implicit)
        parts.append(FRAMEWORK_CONTRACT)

        # 2. Agent package AGENT.md
        parts.append(agent_package.agent_md)

        # 3. Agent package included instructions
        for path in agent_package.config.instructions.include:
            parts.append(agent_package.read_instruction(path))

        # 4-7. Scope overlays (per-run)
        for scope in self.resolve_scopes(workspace, user):
            if scope.instructions:
                parts.append(scope.instructions)

        # 8. Activated skills
        for skill in session.activated_skills:
            parts.append(skill.instructions)

        return self.render_template("\n\n".join(parts), context)
```

## References

- [Claude Code Memory](https://docs.anthropic.com/en/docs/claude-code/memory)
- [GitHub Copilot Repository Instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
- [AGENTS.md](https://agents.md/)
