# ADR-003: Keep the Host Name and Tighten Its Boundary

## Status

Proposed

## Context

Kora currently uses three conceptual layers:

```text
Interface -> Host -> Runtime -> Kernel
```

The name "Host" is useful, but it is also broad. Without a sharper
definition, contributors may treat Host as a catch-all for UI, server
processes, persistence, workspace loading, plugins, permissions, and
runtime orchestration.

That ambiguity becomes more important as Kora adds Skills, persistence,
identity, and workspace trust.

## Decision

Keep the name **Host**, but define it more precisely:

```text
Host is the trusted outer environment that loads, authorizes, persists,
and composes agent definitions before Runtime execution.
```

In Chinese:

```text
Host 是受信任的外层宿主环境，负责在 Runtime 执行前完成加载、授权、持久化和组合。
```

Host is a boundary, not a single process or product surface.

## Host Owns

Host owns:

- loading Agent definitions from files or other trusted sources
- discovering and composing Skills
- workspace trust and permission policy
- identity, users, tenants, and ownership
- persistence adapters for Session and Run state
- shared resources such as files, assets, secrets, and configured tools

## Host Does Not Own

Host does not own:

- Kernel model-tool loop semantics
- Runtime Agent, Session, Run, and event semantics
- UI rendering
- a specific CLI, web server, or desktop app
- provider protocol internals
- tool implementation logic
- plugin marketplace distribution

## Internal Subdomains

Host may eventually contain clearer internal subdomains:

```text
Host
├── Loader: AGENT.md, SKILL.md, and config loading
├── Trust: workspace trust and permission policy
├── Store: Session/Run persistence
├── Identity: user and tenant context
└── Resources: files, assets, secrets, and configured tools
```

These subdomains are not public layers. They are a way to keep Host from
becoming a vague bucket.

## Alternatives Considered

### Platform

Rejected. "Platform" is too broad and suggests a product or SaaS layer
rather than a framework boundary.

### Environment

Rejected. It conflicts with Python environments, workspace environments,
and process environments.

### Shell

Rejected. It has useful Unix flavor but conflicts with CLI shells and
shell command execution.

### Orchestrator

Rejected. It overlaps too much with Runtime orchestration.

### Context

Rejected. It is too abstract and risks becoming less clear than Host.

## Consequences

### Positive

- preserves the existing three-layer architecture
- keeps Host broad enough for persistence, trust, and loading
- prevents Host from absorbing Runtime or Interface responsibilities
- gives Skills and future persistence work a clearer home

### Negative

- Host still needs careful documentation because the name remains broad
- future implementation should avoid exposing Host internals as ordinary user API

## Recommendation

Keep `Host` as the layer name.

Update project documentation to include both positive and negative
definitions so future decisions can be evaluated against the same boundary.
