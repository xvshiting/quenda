# ADR-015: Context Compression and Local Layered Storage

## Status

Accepted

## Context

Kora sessions can grow long enough that the full raw message history no
longer fits comfortably inside the active context window.

If the framework simply keeps appending messages forever, several
problems appear:

- prompt cost grows without bound
- older decisions become harder to surface
- long-running sessions become fragile when the model window is exceeded
- storage can grow unnecessarily if every raw message is kept in memory

The project needs a compression policy that is simple enough to reason
about, but durable enough for agent workflows that depend on continuity.

The key questions are:

- what should be compressed?
- where should compressed data live?
- should raw messages be deleted after compression?
- does compression create a new session?

## Decision

Kora should use **summary-based compression** with **local layered
storage**.

### 0. Layer ownership

Compression is a cross-layer concern, but each layer owns a different
part of the workflow:

| Layer | Owns | Does not own |
|---|---|---|
| `Host` | Compression policy, thresholds, storage layout, archive rules, user-facing `/compress` style commands | Per-turn message reconstruction, raw token counting |
| `Runtime` | Compression execution during the session/run lifecycle, token estimation, token usage aggregation, state updates, and rebuild orchestration | Persistence layout, permissions, user commands |
| `Kernel` | Nothing compression-specific | Session state, storage, summarization, context trimming |

The recommended rule is:

- **Host decides**
- **Runtime executes**
- **Kernel is unaware**

This keeps compression aligned with the existing architecture:

- Host owns configuration and persistence concerns
- Runtime owns execution semantics
- Kernel stays deterministic and minimal

### 1. Compression strategy

The default compression strategy should be:

- keep the most recent raw messages uncompressed
- summarize older conversation into a compact representation
- preserve important state in the summary, not just a generic narrative

This is preferable to plain truncation because it preserves the thread
of the conversation rather than dropping older context entirely.

This is also preferable to a full priority-based memory system at this
stage because it is simpler to implement, test, and explain.

### 2. Storage strategy

Compression artifacts should be stored **locally by default**.

The storage model should be layered:

- **hot layer**: recent raw messages used directly for model input
- **summary layer**: compressed representation of older messages
- **archive layer**: optional raw transcript retained for recovery,
  inspection, or re-summarization

The default storage target is the local Host-owned persistence area.
Remote sync is not part of this ADR.

### 3. Raw message retention

Compression does **not** mean the raw messages must be deleted
immediately.

The recommended default is:

- retain the most recent `N` raw messages
- compress messages older than that threshold
- keep the compressed result locally
- keep raw history in an archive layer if recovery is required

This gives us a safe middle ground:

- enough raw history to preserve short-term coherence
- enough summary to keep long-running sessions usable
- enough archive data to recover from summary mistakes

### 4. Session semantics

Compression does **not** create a new session.

The session remains the same logical conversation identity. Compression
only changes how the session history is stored and reassembled for the
next turn.

This distinction matters because:

- session identity should remain stable
- tool usage and decisions should remain attributable to one session
- users should not lose continuity simply because the session was compacted

If a user intentionally wants a fresh conversation, that should be
represented as a new session or an explicit fork, not as compression.

### 5. Context reconstruction

When the next turn is prepared, Host should reconstruct the effective
context from:

- the current system prompt
- recent raw messages
- compressed summaries
- any approved instruction overlays or state updates

The model should not receive the full archive by default.
Archive loading should be explicit and rare.

### 6. Execution flow between layers

The preferred flow is:

1. Interface or Host detects that compression is needed, or the user
   explicitly requests it.
2. Host provides the compression policy, summarization configuration,
   and storage adapters.
3. Runtime builds the active message set and computes structured usage
   stats for the current turn.
4. Runtime passes those stats into the Host-provided compression policy.
5. Host policy returns a structured decision such as "compress now" or
   "continue without compaction".
6. Runtime invokes a Compressor-capable component to generate the
   summary if compression was requested.
7. Runtime updates the session state with the new summary, archive
   references, and usage counters.
8. Host persists the updated state locally.
9. Runtime rebuilds the message list for the next turn.
10. Kernel receives only the already-prepared messages.

The important point is that summarization is not a Kernel concern, and
storage is not a Runtime concern.

### 7. Runtime to Host policy interface

Runtime should not send a bare token number to Host.

Instead, Runtime should construct a structured stats object and pass it
to a Host-provided policy interface.

Recommended shape:

```text
CompressionStats
  - estimated_input_tokens
  - message_count
  - context_window
  - reserved_output_tokens
  - summary_token_count
  - hot_message_count
  - session_id
  - agent_name
  - mode
```

Recommended interaction:

```text
Runtime
  -> compression_policy.should_compress(stats)
  -> CompressionDecision
```

Recommended decision shape:

```text
CompressionDecision
  - compress: bool
  - keep_last_n_messages
  - target_budget_tokens
  - archive_raw_messages: bool
  - summarizer_id
  - reason
```

This keeps the dependency direction clean:

- Runtime computes runtime facts
- Host policy evaluates those facts
- Runtime executes the resulting decision

## Recommended Data Model

A session can be represented as a composition of blocks:

```text
Session
  - session metadata
  - hot messages
  - summary blocks
  - archive references
```

Suggested semantics:

- `hot messages`: exact recent turns sent directly to the model
- `summary blocks`: compressed history of older turns
- `archive references`: pointers to raw transcript storage, not always
  loaded into memory

This model keeps compression explicit and inspectable.

## Compression Trigger

Compression should be triggered by policy, not ad hoc caller behavior.

Possible triggers:

- message count exceeds a threshold
- estimated token count exceeds a threshold
- session age exceeds a threshold
- explicit user command requests compaction

The simplest initial policy is:

- compress when the active prompt budget is exceeded
- preserve the newest messages verbatim

## Token Accounting

Kora should distinguish between two different token concepts:

- **estimated tokens** used to decide whether compression is needed
- **actual tokens** reported by the provider and accumulated for session
  usage tracking

These should not be treated as the same thing.

### Estimated tokens

Estimated token counts are used before model invocation.

They are a Runtime concern because Runtime owns the final message list
that will be sent to the model.

Estimated tokens should feed compression policy decisions, but they are
not authoritative billing data.

### Actual tokens

Actual token counts should be tracked at the session level in real time
when the provider returns usage information.

This is worth doing because it gives the system:

- cumulative session cost visibility
- better observability for long-running sessions
- a durable signal for future UI and reporting features
- a more accurate basis for analytics than prompt-size estimates

The recommended model is:

- Runtime reads provider-reported usage from each completed model call
- Runtime aggregates cumulative counts into session state
- Host persists those cumulative counters as part of session metadata or
  a dedicated usage structure

Suggested counters:

- total_input_tokens
- total_output_tokens
- total_tokens
- total_cached_input_tokens, if the provider exposes it
- total_reasoning_tokens, if the provider exposes it
- compression_count
- last_compressed_at

These counters are session telemetry, not compression policy by
themselves.

Host policy may choose to consult them, but Runtime should still own the
mechanics of collecting and aggregating them.

## Protocol Sketch

The first implementation should keep the protocol small and close to the
current `SessionState` / `Run` model.

### Session usage structure

Recommended session-level structure:

```text
SessionUsage
  - total_input_tokens: int
  - total_output_tokens: int
  - total_tokens: int
  - total_cached_input_tokens: int | None
  - total_reasoning_tokens: int | None
  - compression_count: int
  - last_compressed_at: datetime | None
```

This can initially live inside session metadata or a dedicated
`usage` field once Runtime state evolves.

### Compression stats structure

Recommended per-turn policy input:

```text
CompressionStats
  - estimated_input_tokens: int
  - message_count: int
  - context_window: int | None
  - reserved_output_tokens: int | None
  - summary_token_count: int
  - hot_message_count: int
  - session_id: str
  - agent_name: str
  - mode: str
  - cumulative_usage: SessionUsage
```

This object is produced by Runtime after it has assembled the effective
message list for the upcoming call.

### Compression decision structure

Recommended Host policy output:

```text
CompressionDecision
  - compress: bool
  - keep_last_n_messages: int
  - target_budget_tokens: int | None
  - archive_raw_messages: bool
  - summarizer_id: str | None
  - reason: str
```

This keeps the policy response explicit and testable.

### Compressor structure

Recommended Runtime-facing summarization contract:

```text
Compressor.compress(
  session: SessionState,
  decision: CompressionDecision,
) -> CompressionResult
```

Suggested result shape:

```text
CompressionResult
  - summary_messages: list[Message]
  - archived_message_count: int
  - archive_refs: list[str]
  - summary_token_count: int
```

Runtime applies the result to the in-memory session state, then Host
persists the updated state.

### Runtime integration point

The intended sequence is:

1. `Session.send()` creates a `Run`
2. `Run` builds the candidate message list
3. `Run` estimates token usage for that candidate list
4. `Run` calls `compression_policy.should_compress(stats)`
5. `Run` invokes `compressor.compress(...)` if needed
6. `Run` updates session state and usage counters
7. `Run` continues with normal Kernel execution

This preserves one clean rule:

- compression is a Runtime lifecycle step
- policy remains Host-owned
- usage accounting stays attached to the session

## Summary Content

The summary should preserve the information most likely to matter later:

- user goals
- accepted constraints
- important decisions
- tool outputs that influenced the plan
- known errors and failed attempts
- open TODO items
- current mode or workflow state if relevant

The summary should avoid verbose reenactment. It is not a chat log
replacement; it is a durable working memory artifact.

## Non-Goals

This ADR does not define:

- the exact summarization prompt
- the exact summarization model
- remote synchronization
- retrieval-augmented memory
- semantic search over archived sessions
- a full priority-ranking memory engine
- automatic branching or checkpointing semantics

Those can be introduced later if the product needs them.

## Consequences

### Positive

- long sessions remain usable without losing the main thread
- context growth becomes controlled
- raw history can still be recovered when needed
- session identity stays stable
- the implementation can start simple and evolve later

### Negative

- summary quality becomes important
- storage logic is more complex than plain truncation
- users need to understand that summary is derived state, not truth
- archive management introduces another persistence layer

## Implementation Guidance

When implementing this ADR, prefer:

- a summary strategy as the default compression policy
- local storage as the default persistence target
- a layered model with hot, summary, and archive tiers
- explicit policy thresholds rather than hidden heuristics
- the ability to re-summarize from raw history if a summary drifts

Avoid:

- treating compression as session replacement
- deleting raw history immediately after summary generation
- forcing remote storage into the first implementation
- relying on the model to infer archival state implicitly

## Recommendation

Kora should adopt summary-based compression with local layered storage.

This gives the project a practical default that preserves continuity,
keeps costs bounded, and fits the existing Host-owned persistence model.
