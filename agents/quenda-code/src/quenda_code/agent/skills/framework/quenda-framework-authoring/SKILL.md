---
name: quenda-framework-authoring
description: Configure, extend, or diagnose a Quenda Agent or Agent Home. Use when adding providers or models, selecting default or vision models, creating nested Skills, registering tools or policies, choosing an extension seam, or explaining how Quenda itself should be configured.
---

# Author Quenda Framework Configurations

Treat the running framework as the source of truth and this Skill as the
workflow. Do not reconstruct Quenda's current contracts from memory.

## Start with live capabilities

Run the smallest useful query before editing:

```sh
quenda capabilities --json --section configuration
```

Use `quenda capabilities --json` when provider catalogs or extension contracts
are also needed. The output is credential-free and suitable for piping into
other tools.

## Choose the narrowest seam

1. Edit `config.yaml` for provider catalogs, model roles, tool bundles, Skill
   activation, MCP, compression, and named policy bindings.
2. Add a Skill for procedural knowledge or a repeatable workflow. A Skill does
   not implement a new runtime transport, sandbox, lifecycle, or policy seam.
3. Add an Agent-local extension under `extensions/` for Python behavior owned
   by one Agent package.
4. Change framework core only when a reusable contract or lifecycle seam is
   missing. Keep official implementations replaceable through that contract.

Read [agent-config.md](skill://quenda-framework-authoring/references/agent-config.md)
for configuration shapes. Read
[extension-seams.md](skill://quenda-framework-authoring/references/extension-seams.md)
before adding Python. Read
[vendor-boundaries.md](skill://quenda-framework-authoring/references/vendor-boundaries.md)
when Codex, Claude Code, or another agent product is mentioned.

## Editing workflow

1. Locate the actual Agent Home or package; do not assume the current workspace
   is the Agent Home. `quenda agent list` prints installed homes.
2. Inspect the live manifest and call `explain_agent_config` for the smallest
   relevant section of the current effective configuration. Do not read raw
   credentials merely to explain configuration.
3. Preserve existing providers, models, and unrelated user edits.
4. Prefer environment-variable references for credentials. Inline credentials
   are supported but must never be echoed, committed, or copied into reports.
5. For an in-conversation `config.yaml` change, call
   `apply_agent_config_patch` without `commit` first. Review its redacted diff
   and validation report, then call it again with `commit: true` and the
   returned `base_revision`. The Host requests user approval before the atomic
   commit and records a rollback revision.
6. Call `validate_agent_package` after changes outside that guarded tool. From a shell,
   run `quenda agent validate <target> --json`. Fix every error before runtime
   testing; review warnings explicitly.
7. Run focused tests and then the affected integration tests. Do not claim a
   provider works from static validation alone; use an explicit opt-in live
   request when credentials are available.

For an existing Skill improvement, call `inspect_skill_evolution` first. Use
`apply_skill_evolution` with `action: propose` and complete replacements keyed
by package-relative path. Review the static validation findings, changed paths,
base revision, executable-review flag, and evidence. Commit that proposal only
with its returned `proposal_id` and `base_revision`; the Host requests a fresh
`skill_evolution.write` approval. A commit changes the installed package but
does not silently replace a revision already pinned into an active Session.
Explicitly request that Skill again to advance its activation epoch, or start a
new/rebound Session. Use rollback with both the target historical revision and
the current expected revision.

## Cache and evolution rules

Keep stable framework and Agent identity instructions stable. Put changing
conversation state and tool results in the dynamic tail. User preferences and
memories belong in the Agent Home's user or memory layers; changes to identity,
Skills, or executable extensions require a reviewable revision and must not
rewrite an active Run's earlier context.

Do not copy the capability manifest into this Skill. Query it at use time so
framework upgrades cannot leave the Skill presenting stale facts.
