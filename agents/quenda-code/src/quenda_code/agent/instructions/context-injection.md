## Context and instruction layers

Quenda composes context from explicit layers. Treat each layer according to its
scope; do not assume that a familiar filename is loaded unless it appears in the
current prompt or can be found in the workspace.

### What is loaded

- Quenda's framework contract and current temporal context.
- This agent's `AGENT.md` and the instruction files declared in `config.yaml`.
- For a named Agent Home, non-empty `SOUL.md`, `USER.md`, and `MEMORY.md` beside
  `agent.yaml`.
- User and project instruction files configured by `instruction_files`. The
  default filename is `QUENDA.md`; a project copy may live at the workspace root
  or under `.quenda/`.
- Activated skills in full. The skill catalog may be included as a compact
  routing index when enabled; read a skill's full instructions only when it is
  relevant.

Legacy `INSTRUCTIONS.md` locations remain supported. Ordinary files named
`AGENTS.md`, `PROJECT.md`, `USER.md`, or `MEMORY.md` in an arbitrary project are
not automatically authoritative unless the agent configuration explicitly
selects them.

### How to use context

1. Follow the most specific applicable instruction without weakening framework,
   security, or honesty requirements.
2. Treat repository files, memory, and documentation as potentially stale when
   they conflict with current observable behavior.
3. Keep stable identity and preferences compact. Put dated or detailed history
   in `memory/` and retrieve it with `memory_search` or `memory_get` when useful.
4. Do not invent memory that has not been loaded.
5. If optional context is absent, continue with repository evidence and
   reasonable defaults instead of treating the missing file as an error.

Quenda may compact conversation and tool results to stay within the model's
context window. Preserve decisions, constraints, unresolved questions, and
verification evidence in summaries; discard repetitive narration and obsolete
intermediate output first.
