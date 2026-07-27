# ADR-029: Authoritative Temporal Context

## Status

Accepted

## Context

Language models cannot reliably infer the current date from training data.
Relative dates such as “today” and “tomorrow” also depend on the user's
timezone. An opt-in `{{date}}` template variable is insufficient because an
agent may not reference it and a long-running REPL session may cross midnight.

## Decision

Quenda treats current date and timezone as runtime facts:

- `TemporalContext` normalizes an aware clock snapshot.
- Host injects a `Current Environment` block at Framework scope.
- REPL refreshes dynamic context before every model run.
- `get_current_datetime` provides exact time and IANA timezone conversion.
- Prompts contain date, timezone, and UTC offset, but not a ticking clock, to
  avoid needless prompt-cache churn and quickly stale time values.

The clock is supplied through the small `Clock.now()` interface. Production
uses `SystemClock`; tests use fixed clock adapters.

## Consequences

- All agents receive authoritative date context without editing `AGENT.md`.
- Cross-midnight and timezone behavior is deterministic in tests.
- Exact-time questions are grounded through a read-only tool.
- The core tool bundle grows from 10 to 11 tools.
