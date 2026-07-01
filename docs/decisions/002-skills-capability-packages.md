# ADR-002: Skills as Host-Level Capability Packages

## Status

Accepted

## Context

Modern agent systems increasingly use "skills" to package reusable agent
capabilities. Claude Code and the Agent Skills specification both use a
directory-based model centered on a `SKILL.md` file, with optional
supporting resources such as scripts, references, and assets.

This model is useful for Kora because many reusable capabilities are not
just tools. They often include:

- instructions for when and how to use the capability
- a small set of related tools
- reference files and examples
- optional scripts or assets
- policy constraints around tool use

Kora needs a way to reuse these capability packages without expanding the
Kernel or making ordinary Agent definitions harder to understand.

## Decision

Kora should add a Skills mechanism, but only as a Host-level loading and
composition concept.

The initial definition is:

```text
Skill = instructions + resource catalog + optional tools + optional policy metadata
```

A Skill is not a Tool. A Tool is executable capability. A Skill explains
how and when a set of capabilities should be used.

## Layer Ownership

### Kernel

The Kernel must not know about Skills.

It continues to know only about messages, model responses, tool calls,
and tool results.

### Runtime

The Runtime should not own Skill discovery, trust, installation, or
resource loading.

It may receive an `AgentConfig` that has already been composed from one
or more Skills by the Host layer.

### Host

The Host owns:

- discovering Skills
- parsing `SKILL.md`
- validating metadata
- enforcing workspace trust and permissions
- composing Skill instructions and tools into an `AgentConfig`
- exposing Skill resources to the agent in a controlled way

## Proposed MVP

The first Kora Skills trial should be deliberately small:

- support local directory Skills such as `.kora/skills/<name>/SKILL.md`
- optionally recognize `.agents/skills/<name>/SKILL.md` for ecosystem compatibility
- parse frontmatter fields such as `name`, `description`, and optional Kora metadata
- list available Skills as a lightweight catalog
- load full Skill instructions only when selected or activated
- expose references and assets as a resource catalog
- keep scripts inert by default

The MVP should prefer progressive disclosure:

1. load only Skill metadata during discovery
2. load `SKILL.md` instructions when a Skill is activated
3. load supporting files only when needed

## Deferred Capabilities

The following should not be part of the first implementation:

- marketplace distribution
- automatic third-party Skill installation
- automatic execution of Skill scripts
- Skill-defined unrestricted tool permissions
- embedding-based Skill routing
- Skill dependency resolution
- remote Skill loading
- making Skills visible to Kernel APIs

## Security Notes

Skills are executable-adjacent instructions. A malicious or compromised
`SKILL.md` can influence model behavior, tool selection, and workflow
decisions.

Project-level Skills should therefore be treated as trusted workspace
configuration. Any future support for third-party Skills needs explicit
trust, provenance, and permission controls.

## Alternatives Considered

### Treat Skills as Tools

Rejected. This blurs the distinction between executable functions and
instructional capability packages.

### Put Skills in Runtime

Rejected for the initial design. Runtime should remain focused on Agent,
Session, Run, and event semantics. Discovery, trust, loading, and policy
belong in Host.

### Build a Plugin System First

Rejected. A plugin system would introduce installation, versioning,
permissions, and distribution concerns before Kora has proven the smaller
capability-package model.

## Consequences

### Positive

- keeps Kernel and Runtime simple
- aligns with Claude Code and Agent Skills ecosystem direction
- supports reusable capabilities without requiring private Code Agent hooks
- gives Kora a path toward richer Agent composition

### Negative

- Host layer needs clearer loading and trust boundaries
- docs must explain the difference between Tool and Skill
- future script support will require careful security design

## Recommendation

Move Skills into the roadmap as a Phase 8 Trial item.

The next step is a design note for the exact `SKILL.md` schema and Host
loading flow, not immediate implementation.
