# 多模态实现评审

## 结论

当前实现方向是合理的，尤其是“内部先抽象，再分 provider family 做转换”这条主线是对的。

但如果按“可长期维护的多模态基础设施”标准来看，现阶段更像是一个可用的 phase-1 骨架，而不是完整闭环。核心问题不在于能不能发图片，而在于：

- 运行时是否会在进入 provider 之前做能力校验
- 消息模型是否足够稳定，能否承载未来的 `audio`、`file`、`reasoning`
- 存储格式是不是在长期上会把实现锁死到 base64 payload
- Anthropic / OpenAI 两条适配链路是否都保持了同一语义

如果目标是“先把 image input 跑通”，现状是可以接受的。
如果目标是“把多模态作为平台能力铺开”，还需要再补几层边界。

## 现状判断

### 已经做对的部分

1. 内核层已经承认多模态消息
   - `TextContent` / `ImageContent` 已经进入 [`src/quenda/kernel/types.py`](/Users/xushiting/Workspace/quenda/src/quenda/kernel/types.py)
   - `Message.content` 允许文本、工具调用、以及文本+图片块

2. provider 适配是分家族做的
   - OpenAI-compatible 走 [`src/quenda/providers/api/converters.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/api/converters.py)
   - Anthropic 走 [`src/quenda/providers/api/anthropic_messages.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/api/anthropic_messages.py)
   - 这避免了把某一家 provider 的 payload 直接塞进核心层

3. 会话存储已经能 round-trip 图片块
   - [`src/quenda/host/storage.py`](/Users/xushiting/Workspace/quenda/src/quenda/host/storage.py) 已经序列化 / 反序列化 `TextContent` 与 `ImageContent`
   - 这说明图片不是只存在于内存里，而是能进入 session 持久化

4. CLI 和 runtime 已经把图片接入主流程
   - [`src/quenda/cli.py`](/Users/xushiting/Workspace/quenda/src/quenda/cli.py) 能从本地文件读取并转 base64
   - [`src/quenda/runtime/run.py`](/Users/xushiting/Workspace/quenda/src/quenda/runtime/run.py) 会把多模态 user message 写入 session，再送入 kernel/provider

5. 模型元数据已经有 vision 位
   - [`src/quenda/providers/model.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/model.py) 有 `vision: bool`
   - 各 provider 的 builtin spec 也有在标注 vision model

## 主要问题

### 1. 视觉能力目前更像“元数据”，还不是强约束

现在 `vision=True` 只是模型规格上的标记，没有看到一个统一的运行时 gate。

这意味着：

- 用户把图片发给不支持 vision 的模型时，可能会在 provider 层才失败
- 不同 provider 对“错误请求”的反馈时机和错误类型可能不一致
- 上层无法稳定依赖 `UnsupportedFeatureError`

这在产品体验上会变成“有时能提前拒绝，有时直到 API 返回 4xx 才知道不行”。

### 2. Anthropic 适配里存在语义风险

[`src/quenda/providers/api/anthropic_messages.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/api/anthropic_messages.py) 在处理 `ToolCall` 消息时，会先发一个 assistant `tool_use`，然后又追加空的 `tool_result` 占位块。

这和 runtime 里已经显式写入的真实 `tool_result` 消息叠加后，容易形成重复或顺序不符合预期的 payload。

这块是目前最需要复核的一点，因为它可能直接影响 Anthropic 路径的正确性，而不是只是架构洁癖。

### 3. 存储格式把 base64 当成了主路径

CLI 和 storage 现在都倾向于把图片编码成 base64，并直接写进 session JSON。

这对 phase 1 是能用的，但长期会有这些问题：

- session 文件体积变大
- 历史回放、diff、审计都更重
- 图片来源的语义丢失了，后续很难区分本地文件、远程 URL、临时上传引用

如果目标是长期演进，建议把“图片引用”与“图片 payload”分开设计。

### 4. `Message.content` 还是一个“按类型分流”的联合类型

目前的设计已经比纯字符串强很多，但它还是依赖：

- `str`
- `Sequence[ToolCall | ToolResult]`
- `Sequence[TextContent | ImageContent]`

这会带来两个限制：

- 代码里到处要靠“看第一个元素是什么”来判断语义
- 一旦未来引入 `audio`、`file`、`reasoning`、`citation`，这个推断方式会越来越脆

它适合 MVP，不适合长期作为唯一核心抽象。

### 5. 测试覆盖还停留在局部

目前能看到：

- provider 直连测试
- kernel types 测试
- 一个 debug multimodal 脚本

但还缺少完整链路验证：

- CLI 输入 -> runtime -> session -> storage -> reload -> provider
- vision model / non-vision model 的分支行为
- OpenAI / Anthropic 两个 family 的同一消息语义一致性

## 架构建议

### 推荐的分层目标

```text
Host 输入
  -> Runtime 归一化
  -> Kernel 统一消息模型
  -> Provider family 转换
  -> Provider 请求 payload
```

### 建议保持的原则

1. 核心层只认识“内容块”，不认识 provider schema
2. 运行时负责能力校验，不把失败推迟到 provider
3. 存储层优先保存引用，payload 只做必要兜底
4. family 级适配优先于单 provider 特判
5. phase 1 只做 image input，不要同时扩大到 audio/video/file

## 推荐补强项

### P0

1. 在 runtime 或 model invocation 前增加 vision capability check
2. 对不支持 vision 的模型统一抛 `UnsupportedFeatureError`
3. 复核 Anthropic message conversion，避免 tool_use / tool_result 语义重复

### P1

1. 给图片来源引入更清晰的引用层，比如 `source_kind + uri/path + media_type`
2. 把 base64 payload 降级为“传输格式”，不要作为长期存储主格式
3. 增加端到端多模态测试

### P2

1. 把 `Message.content` 演进成显式 block model
2. 预留 `audio`、`file`、`reasoning` block 的扩展口
3. 给 compression / replay 增加对 image reference 的策略

## 分阶段路线

### Phase 1: 图像输入可用

- CLI 支持本地图片输入
- runtime 可以把图片送进模型
- session 可以保存和恢复图片块
- vision model 通过，non-vision model 明确失败

### Phase 2: 引用化存储

- session 里保存 image reference
- base64 只作为临时传输编码
- archive / replay 只记录最小必要元数据

### Phase 3: 通用多模态

- 扩展到 `audio` / `file` / `reasoning`
- 建立统一 block 规范
- provider family 继续只做映射，不扩散语义

## 一句话建议

现在的实现“方向正确、基础可用、但还不够硬”。

如果你们当前目标是快速验证 image input，这套实现可以继续推进。
如果你们要把多模态作为长期平台能力，我建议先补 capability gate 和 Anthropic 语义复核，再考虑继续扩展 block model。
