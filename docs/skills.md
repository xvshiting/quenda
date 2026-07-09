# Skills Framework

Skills are composable capability packages that extend agent behavior with instructions and resources.

## Overview

A **Skill** is a reusable package that provides:

- **Instructions** - How and when to use a capability
- **Resource catalog** - Reference documents, templates, and assets

```text
Skill = instructions + resource catalog
```

Skills differ from Tools:
- A **Tool** is an executable function the model can call
- A **Skill** is instructional content that guides the model's behavior

## Framework Contract

All Quenda agents automatically receive the **Framework Contract** in their system prompt. This includes:

- Workspace structure conventions (physical vs logical)
- Skills system overview and path locations
- How to create new skills
- Skill usage commands

The Framework Contract ensures every agent knows where to find and how to create skills.

## Physical vs Logical Workspace

Quenda distinguishes between **physical workspace** (project folder) and **logical workspace** (user-specific state):

### Physical Workspace (Shared)
```
<project-folder>/           # Shared project files
├── .quenda/
│   └── workspace.yaml      # Workspace binding (id, metadata)
└── ...                     # Project code
```

### Logical Workspace (Per-User)
```
~/.quenda/users/<user>/
├── agents/
│   └── <agent>/
│       └── workspaces/<ws_id>/  # Session state
└── workspaces/
    └── <ws_id>/
        └── skills/              # User-workspace skills
```

This design enables:
- **User isolation**: Each user has their own skills per workspace
- **Multi-tenant support**: Same project, different users, different skills
- **Clean separation**: Project code vs user state

## Skill Locations

Skills are discovered in this priority order:

| Priority | Location | Source | Description |
|----------|----------|--------|-------------|
| 1 (highest) | `~/.quenda/users/<user>/workspaces/<ws_id>/skills/` | user_workspace | User-specific, highest priority |
| 2 | `<workspace>/.quenda/skills/` | workspace | Project-shared skills |
| 3 | `<workspace>/.agents/skills/` | workspace | Cross-client project skills |
| 4 | `<agent-package>/skills/` | agent_package | Bundled with agent |
| 5 (lowest) | `~/.quenda/skills/` | user | Shared across workspaces |

### User-Workspace Skills

Skills specific to a user in a particular workspace:

```
~/.quenda/users/<user>/workspaces/<ws_id>/skills/<skill-name>/SKILL.md
```

These skills:
- Are isolated per user and per workspace
- Have the highest priority (can override bundled skills)
- Support multi-user environments

### Project Skills

Skills checked into or installed under a project workspace:

```
<workspace>/.quenda/skills/<skill-name>/SKILL.md
```

These skills:
- Are shared by anyone using the workspace
- Are useful for project-specific conventions, architecture notes, or workflows
- Can override agent-bundled and user-global skills
- Can be overridden by user-workspace skills for personal customization

Quenda also discovers ecosystem-compatible project skills under:

```
<workspace>/.agents/skills/<skill-name>/SKILL.md
```

### Agent Package Bundled Skills

Skills bundled with the agent package. When distributing via PyPI, include in package data:

```
<agent-package>/
├── AGENT.md
├── config.yaml
├── skills/                    # Bundled skills
│   ├── code-review/
│   │   └── SKILL.md
│   └── repo-navigation/
│       └── SKILL.md
└── ...
```

In `config.yaml`, reference bundled skills:

```yaml
skills:
  - code-review        # Auto-activate bundled skill
  - repo-navigation
```

**Benefits:**
- Installed together with the agent
- Version consistency: skill version matches agent version
- Removed when agent is uninstalled
- No pollution of user/workspace environment

### User Skills

Shared skills in user's home directory:

```
~/.quenda/skills/<skill-name>/SKILL.md
```

These are shared across all workspaces for this user.

## Creating a Skill

Skills are defined in `SKILL.md` files within a skill directory:

```
.quenda/skills/
└── code-review/
    ├── SKILL.md
    ├── guides/
    │   └── style-guide.md
    └── templates/
        └── review-report.md
```

### SKILL.md Schema

```yaml
---
name: code-review
description: Apply when reviewing code, checking code quality, or providing feedback on code changes.
version: "1.0.0"
resources:
  references:
    - path: "guides/style-guide.md"
      description: "Style guidelines"
  assets:
    - path: "templates/review-report.md"
      type: template
---

# Code Review

When reviewing code, provide thorough, constructive feedback...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier (lowercase, alphanumeric, dashes, underscores) |
| `description` | Yes | Human-readable description - primary triggering mechanism |
| `version` | No | Semantic version (default: "0.1.0") |
| `resources` | No | References and assets |

### Resources

The `resources` section supports:

```yaml
resources:
  references:               # Documents for the model to reference
    - path: "guides/style-guide.md"
      description: "Style guidelines"
  assets:                   # Templates and other assets
    - path: "templates/report.md"
      type: template
```

Asset types: `template`, `script`, `data`, `other`

## Discovery Locations

Skills are discovered in this priority order:

1. **User-workspace skills** - `~/.quenda/users/<user>/workspaces/<ws_id>/skills/<name>/`
2. **Project skills** - `.quenda/skills/<name>/`
3. **Ecosystem project skills** - `.agents/skills/<name>/`
4. **Agent package skills** - `<agent-package>/skills/<name>/`
5. **User skills** - `~/.quenda/skills/<name>/`

## Using Skills

### In Agent Configuration

Activate skills by default in `config.yaml`:

```yaml
# config.yaml
skills:
  - code-review
  - testing
```

### In REPL

Use the `/skill` command to manage skills:

```
/skill list                    # List available and active skills
/skill activate code-review    # Activate a skill
/skill deactivate code-review  # Deactivate a skill
/skill resources               # List resources from active skills
```

### Programmatic API

```python
from quenda.host.skill import SkillDiscovery, SkillActivator, ResourceResolver

# Discover available skills
# user_workspace_skills_path: logical workspace path for user isolation
# agent_package_path: path to agent package with bundled skills
discovery = SkillDiscovery(
    user_workspace_skills_path=user_workspace_skills_path,
    agent_package_path=agent_package_path,
)
skills = discovery.discover_skills()

# Activate skills
activator = SkillActivator(discovery)
activator.activate_skill("code-review")

# Get active skills for instruction composition
active_skills = activator.active_skills

# Access resources
resolver = ResourceResolver(active_skills)
guide = resolver.load_resource("code-review", "style-guide.md")
```

## Progressive Disclosure

Skills implement progressive disclosure for efficiency:

1. **Discovery** - Only frontmatter metadata is loaded
2. **Activation** - The `SKILL.md` body is read lazily when the skill is used
3. **Usage** - Resources are loaded on demand

This ensures large skill directories don't impact startup time.

## Instruction Composition

Skills are integrated into the instruction composition layer (ADR-007):

```
Framework → Agent AGENT.md → Agent Instructions → User instructions → Workspace instructions → Skills
```

### Skill Injection

**Active Skill Instructions (only for activated skills)**

Activated skills get their full instructions injected:

```markdown
<skill_content name="code-review">

# Code Review

When reviewing code, provide thorough, constructive feedback...

Skill directory: /path/to/skill
Relative paths in this skill are relative to the skill directory.

<skill_resources>
  <file>guides/style-guide.md</file>
  <file>templates/review-report.md</file>
</skill_resources>
</skill_content>
```

### How It Works

1. **Discovery**: All skills in skill directories are discovered
2. **Activation**: User or config activates specific skills
3. **Instruction injection**: Full instructions of active skills → agent knows how to apply them
4. **Resource loading**: References, templates, and other assets are read only when needed

Discovered skill catalogs stay host-side by default. They can still be surfaced explicitly for debugging or routing flows, but they are not injected into every run prompt.

## Example Skills

### Code Review Skill

```
.quenda/skills/code-review/
├── SKILL.md
├── guides/
│   ├── style-guide.md
│   └── security-checklist.md
└── templates/
    └── review-report.md
```

### Testing Skill

```
.quenda/skills/testing/
├── SKILL.md
└── references/
    ├── test-patterns.md
    └── coverage-guide.md
```

## Security Considerations

- Skills are trusted workspace configuration
- Skills can influence model behavior and tool selection
- Scripts in skills are not automatically executed
- Future third-party skills will require explicit trust controls

## Architecture

Skills are entirely a **Host layer** concern:

| Layer | Responsibility |
|-------|---------------|
| **Kernel** | Unaware of skills, only handles messages and tool calls |
| **Runtime** | Receives composed AgentConfig, doesn't own skill discovery |
| **Host** | Discovers, validates, loads, and composes skills |

This separation keeps the core runtime simple while allowing rich capability composition.
