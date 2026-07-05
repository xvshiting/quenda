# 多模态落地路线图

## 目标

把当前“能接图片”的实现，推进成“可长期维护的多模态基础设施”。

## 当前状态

现有实现已经覆盖了最小闭环的主要部分：

- Kernel 层有 [`src/quenda/kernel/types.py`](/Users/xushiting/Workspace/quenda/src/quenda/kernel/types.py)
- OpenAI-compatible 转换在 [`src/quenda/providers/api/converters.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/api/converters.py)
- Anthropic 转换在 [`src/quenda/providers/api/anthropic_messages.py`](/Users/xushiting/Workspace/quenda/src/quenda/providers/api/anthropic_messages.py)
- Session 存储在 [`src/quenda/host/storage.py`](/Users/xushiting/Workspace/quenda/src/quenda/host/storage.py)
- CLI 图片输入在 [`src/quenda/cli.py`](/Users/xushiting/Workspace/quenda/src/quenda/cli.py)
- Runtime 消息注入在 [`src/quenda/runtime/run.py`](/Users/xushiting/Workspace/quenda/src/quenda/runtime/run.py)

这意味着“链路已存在”，但还没有达到“边界稳定”的阶段。

## 里程碑

### Milestone 1: Image Input 可用

目标：

- 用户可以从 CLI 传入图片
- 图片能进入 session
- 图片能送入支持 vision 的模型
- 不支持 vision 的模型能明确失败

交付物：

- 运行时 vision capability check
- 统一的 `UnsupportedFeatureError` 行为
- 基础端到端测试

验收标准：

- 至少一个 OpenAI-compatible vision model 可正常接收本地或 URL 图片
- 至少一个 Anthropic-family vision model 可正常接收图片
- non-vision model 遇到图片时会早失败，而不是靠 provider 返回错误

### Milestone 2: 存储引用化

目标：

- session 不再把 base64 当作长期 canonical 格式
- 图片来源可区分本地文件、远程 URL、临时引用

交付物：

- 图片来源抽象
- 最小元数据规范
- archive / replay 的引用保留策略

验收标准：

- session reload 可以恢复图片引用语义
- 存储文件体积不再随着图片 payload 线性膨胀

### Milestone 3: Block Model 稳定化

目标：

- 为未来 `audio` / `file` / `reasoning` 留出稳定扩展点
- 不再依赖“看第一个元素是什么”来判断消息语义

交付物：

- 显式 content block 规范
- provider-family block mapping 文档
- 更完整的 serialization / deserialization 测试

验收标准：

- 新 block 可以按相同机制扩展
- 旧的 text / tool flow 不需要大面积重写

### Milestone 4: 观测与压缩协同

目标：

- 多模态消息在压缩、回放、trace 中表现稳定

交付物：

- 压缩时保留图片引用和必要元数据
- trace 能展示图片来源与上下文

验收标准：

- 图片不会因为压缩而丢失关键语义
- 回放时能看出图片在会话中的角色

## 推进顺序

建议按下面顺序推进：

1. 先补 vision capability gate
2. 再复核 Anthropic / OpenAI 的消息转换语义
3. 然后把存储从 payload-first 迁到 reference-first
4. 最后稳定通用 block model

## 风险

### 1. 过早扩大 scope

如果同时做 image、audio、file、video，项目会很快进入抽象过载。

建议：

- phase 1 只做 image input

### 2. provider 语义漂移

OpenAI-compatible 的“兼容”不代表完全一致。

建议：

- 以 API family 为单位做适配验证
- 不要让单一 provider 的 payload 反向定义核心结构

### 3. 存储与安全成本上升

图片一旦进入 session，就会带来更高的持久化、审计和权限复杂度。

建议：

- 优先保存引用和最小元数据
- base64 仅作为传输形式

## 建议的里程碑优先级

1. Vision capability gate
2. Anthropic 语义复核
3. Reference-first storage
4. Explicit block model
5. Compression / replay 协同

## 一句话总结

先把“图片能可靠地进来、被识别、被存住、被恢复”做稳，再扩展到更通用的多模态能力。这样最不容易把核心架构做脆。
