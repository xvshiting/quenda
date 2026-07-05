# ADR-027: Multimodal Input Foundation

## Status

Proposed (2026-07-04)

## Context

Quenda 当前已经具备一部分多模态支持的基础：

- Kernel 层已经有 `TextContent` / `ImageContent`，并允许 `Message.content` 承载文本块与图片块
- OpenAI-compatible 与 Anthropic-family 都已经有各自的消息转换器
- Session storage 已经能序列化 / 反序列化图片块
- CLI 和 Runtime 已经可以把本地图片接入到主消息流
- `ModelSpec` 已经有 `vision` 能力标记

这些基础说明方向是对的，但仍然存在几个架构问题：

- `vision=True` 目前更像元数据，缺少统一的运行时能力校验
- `Message.content` 仍然是“按类型分流”的联合类型，后续扩展 `audio`、`file`、`reasoning` 会继续变脆
- session 存储和 CLI 目前偏向把 base64 当作主路径，长期不利于回放、审计和存储控制
- Anthropic / OpenAI 两条适配链路虽然都能接图片，但还没有完全统一的语义约束

Quenda 需要明确：多模态到底是一个 provider 特性，还是一个核心消息能力。

## Decision

Quenda should adopt a **core-level, structured content-block model** for multimodal input.

Phase 1 should support:

- text
- image input
- compatibility with existing tool calling

Phase 1 should not attempt:

- audio
- video
- model-generated images
- arbitrary binary attachment ingestion
- image semantic compression

### 1. Core message model

The core message abstraction should evolve toward a structured block model.

Recommended phase-1 block set:

- `text`
- `image`
- `tool_call`
- `tool_result`

The key point is not the exact class name. The key point is that Quenda should own a provider-independent content model.

### 2. Capability enforcement

`vision` should become a runtime-checked capability, not just catalog metadata.

Recommended rule:

- if a message contains image blocks and the selected model does not support vision, fail early with `UnsupportedFeatureError`
- do not defer this failure until provider API invocation unless no reliable pre-check is possible

This keeps failure modes consistent across providers.

### 3. Provider-family mapping

Multimodal support should be implemented at the API-family mapping layer.

Recommended mapping strategy:

- OpenAI-compatible family maps `text` / `image` blocks to OpenAI-style content items
- Anthropic family maps `text` / `image` blocks to Anthropic content blocks
- provider-specific quirks should stay inside the family converter, not leak into Kernel or Session

### 4. Persistence strategy

Session storage should persist Quenda blocks and minimal image metadata, not raw provider payloads.

Recommended constraints:

- persist image references and metadata as first-class data
- treat base64 as a transport format, not the long-term canonical storage form
- keep replay-friendly metadata so that later stages can reason about source and provenance

### 5. Compression strategy

Phase 1 should not perform semantic compression of image content.

Recommended behavior:

- preserve image references and essential metadata
- let summaries describe the role of the image in the conversation
- avoid image-specific compression logic until the block model stabilizes

## Consequences

### Positive

- Quenda gets a real multimodal foundation rather than provider-specific special cases
- future `audio` / `file` / `reasoning` blocks can extend the same model
- storage, replay, and provider mapping stay cleaner
- model capability metadata becomes operationally meaningful

### Negative

- core message handling becomes more complex
- converter, storage, and test coverage all need to expand
- image source and security handling becomes a first-class concern

## Non-Goals

This ADR does not require phase-1 support for:

- OCR pipelines
- PDF / Office document parsing
- cross-modal semantic summaries
- image generation
- multi-image reasoning orchestration beyond basic input support

## Implementation Guidance

Recommended order:

1. make the multimodal block model explicit and stable
2. add runtime capability checks for vision
3. align provider-family converters on the same internal abstraction
4. move storage toward reference-first persistence
5. add end-to-end tests for image input and non-vision rejection

## Decision Summary

Quenda should treat multimodal input as a core message capability, with image input as the first supported phase.
