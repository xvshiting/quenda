# Skill Turn-Boundary Reload Semantics

## Status

Draft (2026-06-30)

## Purpose

This document defines how Kora should handle skill file changes after a
skill has already been activated.

The core question is:

- if a user edits `SKILL.md` or related resources, when should those
  changes take effect?

This document recommends a clear answer:

- **not live hot reload during a running turn**
- **yes turn-boundary re-resolution before the next user message is
  executed**

## Current Behavior

Today, Kora does **not** behave like a hot-reload system.

The current flow is approximately:

1. `SkillDiscovery` loads a `SkillPackage`
2. `SkillDiscovery` caches that package by name
3. `SkillActivator` stores active `SkillPackage` objects
4. instruction composition reads active skill instructions from those
   in-memory objects

This means:

- editing `SKILL.md` after activation does not automatically update the
  already-active `SkillPackage`
- rebuilding context in the same session still uses the cached skill
  object

In effect, current skills behave like a session-scoped snapshot.

## Why Full Hot Reload Is Not Ideal

At first glance, "edit skill, next token changes immediately" sounds
convenient. But true hot reload creates architectural problems.

### 1. Prompt state becomes unstable mid-session

If a skill mutates invisibly while a session is running, it becomes hard
to explain:

- why the model behaved differently
- which exact instructions were active at a given moment
- whether a behavior change came from user action or file mutation

### 2. Future capability semantics become risky

Skills may later influence:

- resource access
- tool requirements
- trust metadata
- policy hints

Those should not silently mutate during an already-running turn.

### 3. Debugging and reproducibility degrade

If a skill file changes in place and the session transparently updates
it at arbitrary times, reproducing a prior run becomes much harder.

## Recommended Semantics

Kora should adopt the following rule:

> Skills are not live hot-reloaded during a running turn, but active
> skill contents should be re-resolved at turn boundaries.

In practical terms:

- once a run starts, its active skill snapshot stays fixed
- before the next run begins, Host may re-resolve active skill names
  against the filesystem
- updated skill content then becomes visible in the next turn

This gives users a natural workflow:

- edit a skill
- send the next message
- observe the updated behavior

without introducing unstable in-turn mutations.

## Turn Boundary Definition

For this document, a turn boundary means:

- the point after one run completes, and before the next user message is
  executed

In REPL terms:

- user edits a skill
- user submits the next message
- Host rebuilds context from current active skill names

In one-shot mode:

- this matters less, because each one-shot invocation naturally starts a
  fresh setup path anyway

## What Should Refresh At Turn Boundaries

The following changes should become visible on the next turn.

### 1. `SKILL.md` instruction body

If the textual instructions inside `SKILL.md` change, the next turn
should use the new instructions.

### 2. Skill frontmatter metadata used only for presentation or
instruction composition

Examples:

- description
- activation command hints
- declared references for display

If these affect the composed instruction or user-visible skill listing,
they should refresh at the next boundary.

### 3. Skill resource file contents

If a referenced markdown file or safe asset content changes, it should
be re-read on next use after the boundary.

## What Should Not Silently Refresh

The following should **not** change implicitly without a more explicit
reload or re-resolution step.

### 1. Active / inactive state

Editing a file must not auto-activate or auto-deactivate a skill.

Activation state is session intent, not file content.

### 2. Source priority resolution

If multiple skill sources exist:

- user-workspace
- agent package
- user-level

then source selection should remain stable unless Host intentionally
re-resolves the skill name.

This should happen at turn boundaries, not arbitrarily mid-turn.

### 3. Future capability-affecting metadata

If skills later declare:

- tool requirements
- trust metadata
- policy hints

then changing those values should not instantly mutate already-running
session capability grants.

Those changes should require a more explicit Host re-resolution step,
and possibly a new session or grant refresh policy.

## Recommended Implementation Model

The key implementation shift is:

- `SkillActivator` should not be the long-term owner of immutable loaded
  `SkillPackage` snapshots
- it should primarily own **active skill names**

Then, at turn boundaries:

1. Host asks for the list of active skill names
2. Host re-resolves each name through `SkillDiscovery`
3. Host rebuilds instruction sources from freshly resolved skill
   packages
4. Host updates the system prompt for the next run

This preserves user intent while refreshing content.

## Suggested Data Model Direction

Recommended long-term separation:

### Stable session state

- `active_skill_names: list[str]`

### Turn-scoped resolved state

- `resolved_active_skills: list[SkillPackage]`

This avoids treating loaded skill objects as durable session state.

## Discovery Cache Guidance

`SkillDiscovery` may still cache, but the cache should no longer behave
as an unconditional session-long truth source.

Recommended rule:

- discovery cache is an optimization
- turn-boundary resolution must be able to invalidate or bypass stale
  cached entries

Possible implementations:

- clear cache on each context rebuild
- compare file mtimes and refresh changed skills
- cache only discovery metadata but re-read `SKILL.md` content on turn
  rebuild

Phase 1 does not need the most sophisticated version. It only needs to
avoid stale skill content across turns.

## Relationship To Existing Instruction Semantics

This recommendation is consistent with the existing instruction-layer
direction:

- workspace `INSTRUCTIONS.md` changes are intended to affect future
  turns
- skills should feel similarly editable

But skills differ in one important way:

- skills have activation state
- workspace instruction files do not

That is why Kora should refresh **skill content** at turn boundaries,
while keeping **activation state** explicit and stable.

## REPL Behavior Recommendation

For REPL mode, the ideal user experience should be:

1. activate a skill
2. edit `SKILL.md`
3. send the next message
4. new skill content is used automatically

No manual `/skills reload` command should be required for the common
case, though an explicit reload command may still be useful for
debugging.

## One-Shot Behavior Recommendation

For one-shot execution, each invocation naturally re-runs Host setup, so
skill file edits should already be visible on the next invocation as
long as discovery does not persist stale process-global cache.

## Non-Goals

This document does not propose:

- filesystem watcher based hot reload
- mid-turn instruction mutation
- automatic activation based on file edits
- automatic capability grant refresh from skill metadata edits

Those would add more complexity than value at this stage.

## Final Recommendation

Kora should treat skills as:

- **activation-stable across a session**
- **content-refreshable at turn boundaries**

This gives users the practical benefit they want, without turning
skills into a fully live mutable runtime substrate.
