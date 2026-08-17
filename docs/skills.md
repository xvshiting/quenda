# Skills Framework

Skills are composable capability packages that extend agent behavior with instructions and resources.

## Overview

A **Skill** is a reusable package that provides:

- **Instructions** - How and when to use a capability
- **Resources** - Reference documents, templates, and executable scripts

```text
Skill = instructions + resources
```

Resources are auto-discovered from directory structure:

```text
skill-name/
├── SKILL.md           # Skill definition (required)
├── references/        # Reference documents (read-only)
├── templates/         # Template files (read-only)
├── assets/            # Other assets (read-only)
└── scripts/           # Executable Python scripts
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
| 5 | `~/.agents/skills/` | user | Cross-client user skills |
| 6 (lowest) | `${QUENDA_HOME:-~/.quenda}/skills/` | user | Quenda-specific skills shared across workspaces |

Every skills root is searched recursively. Both of these layouts are valid:

```text
skills/code-review/SKILL.md
skills/engineering/review/code-review/SKILL.md
```

Category directories can be nested to any depth. The `name` in `SKILL.md`
frontmatter, rather than the category path, is the Skill's lookup and activation
identity. Once discovery finds a directory containing `SKILL.md`, that directory
is treated as a package boundary and discovery does not search its resources for
additional Skills. A symlink directly to a Skill package is supported; symlinked
category trees are not recursively followed.

Discovered local Skill packages are registered by the Host as session-scoped
read-only roots. Reading `SKILL.md` or files below that package does not prompt
again even when the package lives outside the project workspace. This never
grants write, delete, shell execution, or network access.

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
│   │   ├── SKILL.md
│   │   ├── references/
│   │   └── scripts/
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

Quenda Code bundles `quenda-framework-authoring` under the nested
`skills/framework/` category. It teaches the Agent how to select a configuration
or extension seam, while `quenda capabilities --json` remains the live source
of framework facts. Keeping those responsibilities separate prevents a static
Skill from drifting as the framework changes. After editing, the Skill calls
the read-only `validate_agent_package` framework Tool; shell workflows use
`quenda agent validate <target> --json` through the same validation module.
Chat-driven configuration uses the separate `apply_agent_config_patch`
framework Tool: preview and validate first, then commit the same revision only
after Host-mediated user approval.
The authoring workflow first calls `explain_agent_config` for a normalized,
credential-free view instead of teaching the model to infer effective state
from raw YAML.

## Skill Evolution Revisions

`quenda.evolution.SkillEvolutionStore` is the framework seam for changing an
installed Skill. A caller supplies the active Skill directory and a dedicated
state directory outside every configured Skill discovery root. `stage()` copies
the package into quarantine, applies package-relative text replacements, and
records static validation results without touching the active revision.
`commit()` requires an explicit approver and rejects stale base revisions;
`rollback()` activates a content-addressed historical snapshot as a new audited
revision. `proposals()` and `history()` make both queues inspectable after a
restart.

Executable changes receive an explicit review flag. Python files are compiled
for syntax only and are never imported or run during static validation. Running
candidate scripts or tests is intentionally deferred to an isolated execution
backend; local Python or shell policy checks are not presented as a sandbox.

Active Host bindings use an explicit Skill activation epoch. Normal prompt
refresh may update the catalog but continues rendering and resolving resources
from the content-addressed snapshots pinned at that epoch. Call
`advance_skill_activation_epoch(binding, names)` (or explicitly request Skill
activation through the running Agent) to opt the binding into current on-disk
revisions. A new/rebound Session pins current revisions automatically.

### User Skills

Shared skills in user's home directory:

```
${QUENDA_HOME:-~/.quenda}/skills/<skill-name>/SKILL.md
```

These are shared across all workspaces for this user.

## Creating a Skill

Skills are defined in `SKILL.md` files within a skill directory:

```
.quenda/skills/
└── engineering/              # Optional category directories
    └── review/
        └── code-review/
            ├── SKILL.md
            ├── references/
            │   └── style-guide.md
            ├── resources/              # Generic read-only supporting files
            │   └── setup-guide.md
            ├── templates/
            │   └── review-report.md
            └── scripts/
                └── analyze.py
```

### SKILL.md Schema

```yaml
---
name: code-review
description: Apply when reviewing code, checking code quality, or providing feedback on code changes.
version: "1.0.0"
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

### Resource Directories

Resources are auto-discovered from these directories:

| Directory | Type | Description | Executable |
|-----------|------|-------------|------------|
| `references/` | reference | Documentation and guides | No |
| `templates/` | template | Template files | No |
| `assets/` | asset | Other asset files | No |
| `scripts/` | script | Python scripts | Yes (*.py only) |

**Executable Scripts:**
- Only `.py` files in `scripts/` directory are executable
- Other resources are read-only
- Scripts receive arguments via command line (`sys.argv`)
- Output is captured and returned to the model

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

Discovered skills are also available as direct slash commands:

```
/code-review inspect the current diff
```

Direct invocation activates the named skill for the session and sends the
remaining text through the normal model/tool loop as that invocation's
arguments. Registered built-in or agent commands take precedence when a
command and skill have the same name.

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
  <file>references/style-guide.md</file>
  <file>templates/review-report.md</file>
  <file executable="true">scripts/analyze.py</file>
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
├── references/
│   ├── style-guide.md
│   └── security-checklist.md
├── templates/
│   └── review-report.md
└── scripts/
    └── analyze.py
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
- Only `scripts/*.py` files are executable
- Script execution has a 30-second timeout
- Future third-party skills will require explicit trust controls

## Architecture

Skills are entirely a **Host layer** concern:

| Layer | Responsibility |
|-------|---------------|
| **Kernel** | Unaware of skills, only handles messages and tool calls |
| **Runtime** | Receives composed AgentConfig, doesn't own skill discovery |
| **Host** | Discovers, validates, loads, and composes skills |

This separation keeps the core runtime simple while allowing rich capability composition.
