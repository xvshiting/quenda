# ADR-018: Multimodal Message Architecture

## Status

Proposed (2026-06-26)

## Context

Quenda already marks some models as supporting `vision` at the
`ModelSpec` layer, but the framework's internal message model is still
text-centric:

- `Message.content` primarily represents text or tool call results
- provider converters mainly handle text / tool_call / tool_result
- session storage, compression, replay, and context reconstruction all
  assume text-first messages
- multimodal provider payloads are not normalized through a shared
  abstraction

This creates several practical problems:

- the model catalog advertises visual capability, but runtime message
  flow cannot actually send images
- upper-layer agents have no uniform way to pass images today, or audio
  and files later
- provider adapters are likely to drift into provider-specific special
  cases
- future support for screenshot analysis, UI understanding, or document
  understanding will require another message-model redesign

The project needs a clear answer to four questions:

- should Quenda Core define a first-class multimodal message abstraction
- which layer should own that abstraction
- should phase 1 support only image input or attempt a wider multimodal
  surface
- how should this remain compatible with existing text, tool, storage,
  and compression behavior

## Decision

Quenda should introduce a **structured content-block message model** as
the foundation for multimodal support.

Phase 1 should be intentionally narrow:

- support **image input**
- preserve existing **text + tool calling** behavior
- avoid promising complete support for audio, video, or arbitrary binary
  attachments in phase 1
- avoid leaking provider-specific payloads into the Kernel layer

### 1. Core message model

Message content should not remain a single string-only abstraction.
Instead, it should evolve toward a composable sequence of content
blocks.

Recommended direction:

- keep the current text shortcut for backward compatibility
- introduce normalized content blocks internally
- let Quenda define the blocks rather than copying any one provider
  schema

Recommended first block types:

- `text`
- `image`
- `tool_call`
- `tool_result`

Semantics:

- `text` and `image` represent user / system / assistant content
- `tool_call` and `tool_result` continue to represent the tool loop
- future extensions may add `audio`, `file_ref`, `citation`,
  `reasoning`, and similar blocks

### 2. Layer ownership

Multimodality is cross-layer, but responsibilities should stay clean:

| Layer | Owns | Does not own |
|---|---|---|
| `Host` | file selection, path permissions, upload preprocessing policy, user experience | provider request schema |
| `Runtime` | session message construction, capability checks, state persistence coordination | provider-specific schema |
| `Kernel` | consumes the normalized message abstraction and drives the model-tool loop | local file reads, payload conversion details |
| `Provider API` | maps normalized blocks to provider request formats | session semantics, persistence semantics |

Recommended rule:

- **Host owns ingress**
- **Runtime owns orchestration**
- **Kernel keeps a stable abstraction**
- **Provider adapters own protocol mapping**

### 3. Scope of phase 1

Phase 1 should solve only "images as model input". It should not
attempt to solve:

- model-generated images
- audio input
- video input
- general attachment retrieval and parsing
- a unified OCR / PDF / Office document abstraction

Those can be added later on top of the same block model.

### 4. Compatibility strategy

Backward compatibility is required:

- existing `Message(content="hello")` usage remains valid
- existing tool call / tool result flows remain valid
- text-only providers do not need to understand image blocks; they only
  need to reject them cleanly
- models without vision support should raise a clear
  `UnsupportedFeatureError`

### 5. Provider strategy

Quenda should not bind multimodal support to a single provider format.

Recommended approach:

- normalize blocks inside Quenda
- let the OpenAI-compatible converter map those blocks into the
  appropriate message / content schema
- let the Anthropic converter map them into its content-block schema
- let other providers reuse an API-family converter wherever possible

In other words, multimodal compatibility should be implemented at the
**API family** level rather than one provider at a time.

### 6. Persistence strategy

Session storage must persist structured Quenda messages, not raw provider
payloads.

Recommended constraints:

- persist the Quenda block abstraction, not provider-native payloads
- prefer references for image blocks rather than embedding large binary
  data
- allow base64 only as a transport representation, not as the default
  persistence format

### 7. Compression strategy

Phase 1 should not attempt semantic compression of image content.

Recommended strategy:

- preserve image references and minimal metadata during compression
- allow text summaries to describe the role of the image in the
  conversation
- avoid introducing image-summary-specific block behavior in phase 1

This keeps multimodal support loosely coupled to the compression system.

## Consequences

### Positive

- establishes a shared foundation for image input, multimodal agents,
  and screenshot analysis
- lowers future extension cost for audio, file, and reasoning blocks
- prevents provider-specific payloads from leaking into Kernel and
  session state
- turns model capability metadata into runtime-usable capability

### Negative

- increases the complexity of the core message abstraction
- requires expansion of converters, storage, and tests
- introduces path-reference, serialization, and permissions concerns
- creates follow-on work for compression, replay, and observability

### Risks

- if block design is too narrow, future audio / file support will break
  the abstraction again
- if block design is too broad, phase 1 cost rises substantially
- if raw provider payloads are stored, future provider switching becomes
  harder
- if image persistence strategy is unclear, storage and security costs
  will rise

## Alternatives Considered

### Option A: keep `vision=True` metadata only and do not change the message model

Pros:

- lowest implementation cost
- no immediate code impact

Cons:

- cannot actually send images
- capability metadata diverges from runtime behavior
- future extension cost increases

Conclusion:

- rejected

### Option B: add image special cases only for OpenAI-compatible APIs

Pros:

- fastest way to ship something
- useful for limited experiments

Cons:

- leaks abstraction details
- does not generalize cleanly to Anthropic-style families
- creates technical debt quickly

Conclusion:

- not recommended as the formal architecture
- acceptable only as an experiment branch

### Option C: support image / audio / video / file all at once

Pros:

- appears most complete on paper

Cons:

- scope is too large
- likely to slow delivery significantly
- increases test and persistence complexity sharply

Conclusion:

- rejected
- phase 1 should focus on image input only

## Implementation Guidance

Recommended order of work:

1. define the Quenda content-block abstraction
2. allow `Message` to represent structured content
3. extend the OpenAI-compatible converter
4. extend the Anthropic converter
5. add capability checks and clear errors
6. extend session storage and replay
7. add tests and documentation

## Decision Summary

Quenda should adopt a structured content-block message architecture, with
image input as the phase-1 multimodal scope.

This capability should be defined as a core Quenda abstraction, mapped by
provider API families, and remain backward compatible with the existing
text and tool-calling flow.
