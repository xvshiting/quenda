# ADR-004: Workspace Identity and User-Agent Workspace State

## Status

Proposed

## Context

Kora needs one Host model that works for both local TUI usage and future
server usage.

In local TUI mode, a user starts an agent from a concrete folder. In
server mode, a user enters a resource or project view. These should not
be treated as different architectures. They should share the same Host
resolution model.

The key distinction is that a physical folder is not itself the full
workspace state. A folder is only a target resource location. User
specific agent state, skills, sessions, and artifacts should not be
stored in the target folder by default.

## Decision

Kora should separate:

- physical folder or server resource
- Host-owned workspace binding
- logical workspace id
- user-agent-workspace state

The core model is:

```text
Physical Folder or Server Resource
  -> Host-owned Workspace Binding
  -> Logical Workspace ID
  -> User + Agent + Workspace State
```

In local file-backed mode:

```text
<workspace>/.kora/workspace.yaml
  -> workspace_id
  -> ~/.kora/users/<user_id>/agents/<agent_name>/workspaces/<workspace_id>/
```

In server mode:

```text
resource binding
  -> workspace_id
  -> HostStore/users/<user_id>/agents/<agent_name>/workspaces/<workspace_id>/
```

The storage backend changes, but the logical model stays the same.

## Workspace Binding

A workspace folder may contain a Host-owned binding file:

```text
<workspace>/.kora/workspace.yaml
```

Example:

```yaml
schema_version: 1
id: ws_abc123
name: kora
binding:
  created_at: "2026-06-23T00:00:00Z"
  path_hint: "/Users/example/Workspace/kora"
  resource_fingerprint: "optional-fingerprint"
```

This file points a physical folder or resource to a logical workspace id.
It is not the workspace state itself.

Multiple folders may bind to the same logical workspace id, subject to
Host validation. This supports directory moves, multiple checkouts, and
server-side mount paths.

## Protected Host Metadata

The workspace binding file is Host-owned metadata.

In the final Host security model, agents and agent-visible tools must not
write, delete, rename, or replace it.

At minimum, these paths are protected in local file-backed mode:

```text
<workspace>/.kora/workspace.yaml
```

Future Host-owned metadata paths should follow the same rule.

This enforcement is deferred until the Host security phase. The MVP may
create and read workspace bindings before complete tool permission
enforcement exists.

When implemented, the rule must be enforced in Host/tool permission
logic, not only in prompts.

## User-Agent-Workspace State

User-specific agent state for a workspace should live under user scope,
keyed by user id, agent name, and workspace id.

Recommended local layout:

```text
~/.kora/
  users/
    <user_id>/
      config.yaml
      agents/
        <agent_name>/
          config.yaml
          INSTRUCTIONS.md
          skills/
          workspaces/
            <workspace_id>/
              config.yaml
              INSTRUCTIONS.md
              skills/
              sessions/
                <session_id>/
                  state.json
                  runs/
                  scratch/
                  artifacts/
```

Server mode should map the same logical structure to a database, object
store, file service, or another HostStore backend.

## Resolution Flow

When a user starts an agent in a folder or server resource, Host should:

1. resolve the logical user id
2. resolve the agent name
3. read or create the workspace binding
4. validate the binding against known path/resource hints
5. resolve the logical workspace id
6. load user scope configuration
7. load user-agent configuration
8. load user-agent-workspace configuration
9. load or create session state
10. compose the final agent context for Runtime execution

The resolved context, not the raw folder, is what the Runtime receives.

## Binding Validation

Because workspace binding files can be copied or forged, Host must not
blindly trust a workspace id found in a folder.

Recommended behavior:

- known workspace id and known binding: allow
- known workspace id with new path/resource: ask to attach or fork
- path/resource mismatch: ask, deny, or create a new workspace id
- suspicious binding: deny by default

The exact interaction can differ by Interface, but the policy belongs to
Host.

## Relationship to TUI and Server

TUI and Server are Interface layers.

They may start or connect to a Host, but they should not duplicate the
Host resolution model.

Local TUI maps the HostStore to files such as `~/.kora/...`.

Server maps the HostStore to service-side storage.

Both should call the same conceptual operation:

```text
Host.resolve_agent_context(user_id, agent_name, resource)
```

## Consequences

### Positive

- user-specific agent customization does not pollute target workspaces
- local and server modes share one conceptual model
- different users can customize the same agent for the same workspace
  independently
- sessions and artifacts naturally live under user-agent-workspace scope
- folders can be moved or reattached without losing user agent state
- workspace identity is explicit and inspectable

### Negative

- Host must implement binding validation
- local storage layout becomes more structured than a simple `.kora`
  folder in the workspace
- users may need an Interface prompt when attaching a new folder to an
  existing workspace id

## Non-Goals

This ADR does not define:

- the exact persistence API
- the exact server database schema
- the complete permission system
- how project-owned shared `.kora` configuration should be merged
- how workspace-level shared Skills are trusted

Those should be handled by later Host ADRs.

## Recommendation

Adopt this as the guiding model for Phase 7 Host persistence and
workspace identity design.

Phase 7 should not treat the physical folder as the only workspace
state. It should introduce workspace binding and user-agent-workspace
state as first-class Host concepts.
