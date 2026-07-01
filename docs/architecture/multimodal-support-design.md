# Multimodal Support Design

## Status

Draft (2026-06-26)

## Purpose

This document expands
[ADR-018](/Users/xushiting/Workspace/quenda/docs/decisions/018-multimodal-message-architecture.md).

The ADR answers:

- why multimodal support is needed
- what phase 1 should include
- where layer boundaries should sit

This document answers:

- how the message model should evolve
- how provider families should map the abstraction
- how session storage, compression, and replay are affected
- what should count as the phase-1 delivery target

## Goals

- introduce a unified multimodal input capability for Quenda
- support image input in phase 1
- preserve compatibility with the existing text + tool-calling flow
- avoid leaking provider-specific schemas into core abstractions
- leave room for future `audio`, `file`, and `reasoning` blocks

## Non-Goals

- model-generated images
- phase-1 support for audio or video
- a general attachment parsing platform
- semantic compression of image content
- full, immediate compatibility across every OpenAI-compatible provider

## Current State

Today, Quenda has "vision metadata" but not a real multimodal message
path.

### Current strengths

- `ModelSpec` already has a `vision` capability flag
- OpenAI-compatible and Anthropic-family providers already use explicit
  converter layers
- Session / Runtime / Kernel boundaries are clean enough to support a
  new message abstraction

### Current limitations

- `Message.content` is still designed around strings and tool-call
  sequences
- converters have no unified entry point for image blocks
- storage assumes messages are text or tool-call records
- compression and replay do not account for non-text content

## Design Principles

The design should follow these principles.

### 1. Internal-first abstraction

Normalize the Quenda-internal abstraction before implementing provider
payload mapping.

No single provider schema should become the core message model.

### 2. Compatibility by default

Existing text and tool workflows should not require large migrations.

### 3. Reference over payload

Images should live in session state primarily as references, not as
 embedded large binary objects.

### 4. Family-level mapping

Prefer mapping by API family rather than rebuilding image handling one
 provider at a time.

### 5. Narrow phase 1

Phase 1 should focus only on image input.

## Proposed Architecture

```text
Host input
  -> Runtime normalization
  -> Quenda content blocks
  -> Provider family converter
  -> Provider request payload
```

Responsibilities:

- `Host`: user ingress, file source handling, permissions, experience
- `Runtime`: message normalization, capability checks, session
  coordination
- `Kernel`: consumes a stable message abstraction and drives the
  model-tool loop
- `Provider API`: translates blocks into concrete provider protocol

## Content Block Model

### Phase-1 block set

Recommended initial block set:

- `TextBlock`
- `ImageBlock`
- `ToolCallBlock`
- `ToolResultBlock`

The important decision is not the exact class names. It is the presence
of a typed, serializable, provider-independent message unit.

### Recommended semantics

#### TextBlock

Represents plain text content.

Minimal semantics:

- `type = "text"`
- `text`

#### ImageBlock

Represents an image passed into the model by a user or system actor.

Recommended minimum shape:

- `type = "image"`
- `source_kind`
- `path` or `uri`
- `media_type`
- `detail`
- `metadata`

Semantics:

- `source_kind` distinguishes local files, remote URLs, and uploaded
  temporary references
- `detail` can express low / high / auto style intent
- `metadata` stores non-critical debugging and replay context

#### ToolCallBlock / ToolResultBlock

Existing tool-call abstractions are directionally correct. The goal is
not to replace them, but to let them coexist with text and image blocks
inside one message model.

## Message Compatibility Strategy

To reduce migration cost, Quenda should continue to allow two entry forms:

- simple text messages, such as `content="hello"`
- explicit structured block lists

Recommended internal flow:

1. Runtime receives messages
2. string content is normalized into `TextBlock`
3. tool-call structures are normalized into tool blocks
4. the provider family converter consumes the normalized form

This keeps:

- the external API simple
- the internal model consistent
- migration cost low

## Image Source Strategy

Image-source boundaries should be defined early, or storage and
permissions will become messy.

Recommended phase-1 sources:

- local file paths
- remote URLs

Not recommended as defaults in phase 1:

- base64 as the long-term storage format
- arbitrary binary blobs stored directly in `SessionState`

Reasons:

- base64 increases storage size
- binary payloads make replay, compression, and inspection harder
- large objects in state add serialization and audit cost

## Provider Mapping

### OpenAI-compatible family

Mapping intent:

- `TextBlock` -> text content item
- `ImageBlock` -> image_url or equivalent image content item
- tool calling continues through the existing function / tool message
  flow

Important caveats:

- not every OpenAI-compatible provider fully supports image content
- some support only URLs and not base64
- some claim compatibility but diverge in schema details

This suggests a need for finer-grained `compat` metadata beyond a single
`vision=True` flag.

### Anthropic family

Mapping intent:

- `TextBlock` -> text block
- `ImageBlock` -> image source block
- `ToolCallBlock` / `ToolResultBlock` continue through the existing
  content-block conventions

Important caveats:

- the system prompt remains a separate channel
- block order must be preserved exactly
- tool-use and multimodal block interleaving needs explicit legality
  rules

## Capability Validation

Runtime capability checks are required, or metadata and actual behavior
will continue to diverge.

Minimum validation rules:

- if a message contains `ImageBlock` and the selected model has
  `vision=False`, fail early with a clear error
- if a converter family does not yet support image mapping, fail with a
  clear unsupported-feature error
- if a provider supports only URL images and input is a local path,
  Host or Runtime should surface that conversion requirement explicitly

The goal is early, explicit failure rather than silent fallback.

## Persistence and Replay

Session persistence should store Quenda blocks, not provider request
bodies.

### Recommended persistence rules

- persist normalized blocks
- persist image references plus necessary metadata
- do not persist image bytes by default
- replay should reconstruct the same block structure

### Replay failure handling

If a local image path is gone, or a remote URL is no longer reachable,
that should not silently disappear.

Recommended behavior:

- surface an explicit "reference unavailable" state during replay or
  reconstruction
- preserve original metadata for debugging
- allow Host-level repair workflows later if needed

## Compression Impact

Phase 1 should not treat images as semantic compression targets.

Recommended strategy:

- preserve image references and metadata as-is
- let summaries describe the role of the image, e.g. "the user uploaded
  an error screenshot"
- keep recent image blocks in the hot-message region

Reasons:

- image summarization is a separate problem
- bundling it into phase 1 would expand scope substantially
- the existing text-compression system should remain only loosely
  coupled

## Observability and Debugging

Multimodal support increases debugging cost relative to pure text.

The design should therefore preserve:

- visibility into block types in logs and traces
- clear separation between path failures, capability failures, and
  provider-mapping failures
- session inspection that can show image references and metadata

Phase 1 does not need a full UI for this, but it should preserve the
necessary information.

## Rollout Plan

### Phase 1: Architecture foundation

- define content-block abstractions
- support message normalization
- extend session persistence shape

### Phase 2: Provider enablement

- enable the OpenAI-compatible family
- enable the Anthropic family
- add baseline capability checks and error messages

### Phase 3: Production hardening

- add regression coverage
- update API and tutorial documentation
- document provider compatibility differences

## Acceptance Criteria

Phase 1 should be considered complete when:

- text-only dialogue and tool-calling behavior show no regressions
- at least one OpenAI-compatible vision model can accept a local or URL
  image
- at least one Anthropic-family vision model can accept image input
- session save / load preserves image blocks correctly
- non-vision models fail clearly when given image input
- compression does not break message reconstruction

## Risks and Mitigations

### Risk 1: Over-designed abstraction

Risk:

- phase 1 becomes slower because the block model is generalized too far

Mitigation:

- keep the initial block set small
- do not implement audio or video up front

### Risk 2: Provider compatibility fragmentation

Risk:

- OpenAI-compatible providers vary more than their marketing suggests

Mitigation:

- distinguish API-family capability from provider-specific compatibility
- allow explicit downgrade paths where provider support is partial

### Risk 3: Storage cost and unstable references

Risk:

- local paths can expire and remote URLs can disappear

Mitigation:

- persist references and metadata by default
- treat reference loss as visible state, not as something to swallow

## Open Questions

- should image blocks allow relative paths, or only normalized references
- should a shared `file_ref` abstraction exist for images and future
  attachments
- how fine-grained should provider `compat` metadata become
- should future `thinking` / `reasoning` information also be modeled as
  content blocks

## Recommendation

Use this document as the implementation blueprint behind ADR-018.

Review discussion should focus on:

- whether the block model is stable enough
- whether phase-1 scope is tight enough
- whether API-family mapping is the right level of abstraction
- whether the persistence strategy is acceptable
