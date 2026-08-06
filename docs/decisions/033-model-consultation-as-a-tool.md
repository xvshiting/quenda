# ADR-033: Model Consultation as a Tool

## 状态

提议 (2026-08-06)

## 背景

Quenda 当前通过 ADR-028 的 capability-based model routing，为一次模型调用选择
满足输入能力要求的模型角色。例如，默认模型 GLM-5.2 不支持图片，而 vision
角色 Kimi 支持图片时，Runtime 会把包含图片的调用路由到 Kimi。

这一机制适合直接的多模态问答，但在 Agentic workflow 中暴露了执行所有权问题：

1. 能力模型获得了主 Agent 的完整上下文和全部工具；
2. 只要有效上下文仍需要 vision，后续调用会持续由 vision 模型执行；
3. vision 模型可能继续规划、修改文件或结束整个 Run，而不是只完成视觉相关工作；
4. 主模型无法分析能力模型的结果后，再决定是否继续咨询或采取其他行动；
5. capability routing 把“选择合适的推理模型”和“转移 Agent 执行权”混成了同一件事。

实际需求不是在 Quenda Core 中引入 subagent，而是让单个 Agent 在保持一个
model-tool loop 的前提下，反复调用更适合某个有界任务的其他模型。例如：

- 让视觉模型直接解答图片中的数学题，而不只是执行 OCR；
- 主模型检查候选解答后，携带新的文字上下文再次向视觉模型追问；
- 让音频模型转写和分析录音，再由主模型决定下一步；
- 让专门的推理模型复核一个候选结论；
- 让视觉模型检查 PPT 截图，但仍由主模型修改 PPT 代码和决定任务完成。

该需求必须与 ADR-017 保持一致：Quenda Core 仍然是单 Agent 框架，不引入
Agent 间通信、子任务调度、独立子 Session 或多 Agent 生命周期。

## 决策

Quenda 将采用 **Model Consultation（模型咨询）**：主模型通过普通 Tool interface
发起一次有界的其他模型调用，咨询结果作为 ToolResult 返回主模型。主模型可以分析
结果，并在同一个 Run 中零次、一次或多次继续调用该 Tool。

第一版建议的模型可见工具名为：

```text
consult_model
```

概念 interface 为：

```python
consult_model(
    task: str,
    context: str | None = None,
    resources: list[ResourceRef] | None = None,
    capabilities: list[ModelCapability] | None = None,
) -> ModelConsultation
```

该 interface 表达“咨询另一个满足能力要求的模型”，而不是指定 provider/model、
切换 Session 默认模型或创建另一个 Agent。

## 领域模型

### Primary Model

执行当前 Agent model-tool loop 的模型。Primary Model：

- 持有任务执行权；
- 决定是否调用工具；
- 决定是否发起或重复模型咨询；
- 使用咨询结果继续推理和执行；
- 是唯一可以产生最终用户回答并自然完成 Run 的模型。

在当前目标场景中，GLM-5.2 是 Primary Model。

### Consulted Model

为一次 Consultation 执行单次模型推理的模型。Consulted Model：

- 根据声明的 capabilities 由框架配置解析；
- 只接收本次 task、显式 context 和 resources；
- 不继承 Primary Model 的完整 Session；
- 不获得 Agent 工具；
- 不持有独立 Session；
- 不运行独立 model-tool loop；
- 不直接向用户回答；
- 不决定主 Run 是否完成。

### Consultation

一次 `consult_model` 调用。每次 Consultation 都是：

```text
一次 ToolCall
    -> 一次 Consulted Model invocation
    -> 一个 ModelConsultation ToolResult
```

Consulted Model 的 `end_turn` 只表示本次 Consultation 完成，不表示主 Run 完成。

### Consultation Chain

Primary Model 在同一个 Run 中发起的多次相关 Consultation。连续性由 Primary Model
在下一次调用中显式提供 `context` 和 `resources`，而不是由 Consulted Model 维护
隐藏会话。

### ModelConsultation

一次 Consultation 的规范化结果。它是候选结论，不是最终用户回答。建议至少包含：

```python
@dataclass(frozen=True)
class ModelConsultation:
    response: str
    provider: str
    model_id: str
    capabilities: tuple[str, ...]
    resource_refs: tuple[str, ...] = ()
    usage: UsageStats | None = None
```

后续可以增加结构化数据、置信度和不确定项，但第一版不要求所有 provider 产生统一的
领域专用 schema。

## 参数语义

### task

描述 Consulted Model 本次必须完成的完整任务，而不是只描述资源读取动作。例如：

```text
直接解答图片中的数学题，给出完整推导和最终答案。
```

或者在后续 Consultation 中：

```text
确认图片第二行的指数是 2 还是 3，并据此重新验证第二步推导。
```

### context

Primary Model 为本次 Consultation 选择的相关文字上下文，可以包括：

- 用户约束；
- 已确认事实；
- 上一次 Consultation 的候选结论；
- Primary Model 发现的矛盾或疑点；
- 本次不应重复的工作。

`context` 不等于完整 Session，不应默认复制全部对话、system prompt、工具历史或
工作区内容。

第一版使用显式文本而不是另一个消息历史结构，以保持 interface 小且容易审计。

### resources

Consulted Model 必须直接理解的资源引用，例如图片、音频或文档。Tool 参数只携带
受 Host 权限校验的 `ResourceRef`，不由模型提交任意未解析的本地路径或二进制内容。

### capabilities

本次任务需要的模型能力，例如 `vision`、`audio_input` 或 `reasoning`。Primary Model
声明需求，Host 根据显式配置解析实际 provider/model。第一版不要求动态效果、成本、
速度评分，也不允许 Primary Model 直接任意指定 provider/model。

## 执行语义

一个典型执行链为：

```text
User task
    -> Primary Model (GLM)
    -> consult_model ToolCall
    -> resolve Consulted Model (Kimi)
    -> invoke Kimi once with task/context/resources and tools=[]
    -> ModelConsultation ToolResult
    -> Primary Model (GLM)
    -> analyze / consult again / use another tool / answer user
```

重复咨询不创建 Consultation Session：

```text
Consultation 1 result
    -> Primary Model analysis
    -> Consultation 2(task + selected context + resources)
```

Provider 内部的 response/conversation ID 缓存可以作为透明优化，但不能成为 public
interface 的正确性依赖。

## 不变量

第一版必须保持以下不变量：

1. 一个 Run 只有一个 Agent 和一个 model-tool loop；
2. Primary Model 始终拥有执行权；
3. 一次 Consultation 只执行一次模型调用；
4. Consulted Model 不获得 Agent 工具；
5. Consulted Model 不持有独立 Session 或隐藏对话状态；
6. Consultation Result 通过标准 ToolResult 返回；
7. Primary Model 可以在同一个 Run 中反复调用 `consult_model`；
8. Consulted Model 的返回不能直接触发 `RunCompleted`；
9. Primary Model 不直接选择任意 provider/model，只声明能力需求；
10. 资源访问、模型可用性和预算仍由 Host/策略控制，而不是由提示词保证。

## 层级职责

### Kernel

Kernel 继续只理解普通 Model、ToolCall 和 ToolResult，不感知 Model Consultation、
subagent 或模型路由策略。

### Runtime

Runtime 继续执行一个 Agent Run 和标准工具阶段。咨询次数、token 和时间预算可以通过
现有 policy seam 约束，但 Runtime 不创建第二个 Agent 生命周期。

### Host

Host 负责：

- 解析 capability 到具体模型的受信任配置；
- 校验 ResourceRef 和工作区访问；
- 构造并注入 `consult_model` 的实现依赖；
- 控制可用咨询模型和预算策略。

### Tool implementation

`consult_model` 负责：

- 组装受限的 Consultation prompt；
- 将资源转换为 Consulted Model 可接受的内容块；
- 使用 `tools=[]` 执行一次模型调用；
- 将 provider 响应规范化为 ModelConsultation；
- 返回普通 ToolResult。

## 与现有 ADR 的关系

### ADR-017: Keep Multi-Agent Out of Quenda Core

本决策遵循 ADR-017。Model Consultation 不是 subagent，因为它没有独立 Agent、
Session、工具循环、调度或 Agent 间通信。

### ADR-022: Keep Core Minimal and Push Strategies to Policies

咨询预算、重试、模型选择和结果验证属于可替换策略，不进入 Kernel 的通用工具循环。

### ADR-023: Runtime Owns Tool Phase

`consult_model` 使用现有 ToolCall -> ToolResult -> next model step 语义，不建立并行的
执行协议。

### ADR-027: Multimodal Input Foundation

Consultation 的 resources 使用 Quenda 规范化资源和内容块，不向 Kernel 泄漏
provider-native multimodal payload。

### ADR-028: Capability-Based Model Routing

ADR-028 的整轮模型角色路由继续适用于直接多模态问答，但不再是 Agentic workflow
补足能力的唯一策略。需要 Primary Model 保持执行权的 Agent（特别是 Quenda Code）
应优先使用 Model Consultation，而不是让 capability model 接管后续工具循环。

后续需要明确配置层如何区分：

```text
takeover routing：能力模型回答当前整轮
consultation：Primary Model 通过 Tool 借用能力模型
```

## 拒绝的方案

### 方案 A：继续让 capability model 接管整个 Run

拒绝作为 Quenda Code 默认行为。它使视觉模型获得无关工具和主任务控制权，并且缺少
明确的 return-to-primary 语义。

### 方案 B：切回 Primary Model 并伪造 assistant/user 消息

拒绝。伪造 assistant 消息会让 Primary Model 误认为内容由自己生成；伪造 user 消息
会把 Runtime 观察冒充成用户指令。标准 ToolResult 已经提供正确的消息语义。

### 方案 C：把 Consulted Model 实现成完整 subagent

暂不采用。独立 Agent、Session、工具循环、调度、取消和权限继承超出当前真实需求，
并违反 ADR-017 的 Core 边界。

### 方案 D：将能力模型限制为 OCR 或资源描述器

拒绝。Consulted Model 应直接完成本次 `task`，例如直接解题、分析图表或复核结论，
避免先转成有损文本再由 Primary Model 重做推理。

### 方案 E：为 vision/audio/reasoning 分别增加多个 public tool

暂不采用。一个 `consult_model` interface 加 capability 声明能隐藏模型选择和调用机制，
避免随着能力种类增长扩大主 Agent 的工具表。

## 后果

### 正面

- 保持 Quenda 的单 Agent 定位；
- Primary Model 的执行权稳定且可解释；
- 能复用不同 provider/model 的视觉、音频和推理能力；
- 支持 Primary Model 分析结果并进行多轮针对性咨询；
- 使用标准 Tool 协议，避免跨模型 assistant 身份混淆；
- consulted model 没有写工具，安全边界由代码保证；
- 比 Agent-as-tool 或 subagent orchestration 更轻。

### 负面

- 每次 Consultation 增加模型延迟和 token 成本；
- Primary Model 需要选择高质量的 task 和 context；
- Tool 内部调用模型需要独立的用量、错误和 trace 记录；
- consultation result 可能被 Primary Model 错误采纳或错误改写；
- capability 到模型的配置需要稳定、可解释的解析规则。

### 风险与缓解

| 风险 | 缓解方向 |
|---|---|
| 完整 Session 被复制到 context | 第一版只接受显式文本 context 和 ResourceRef |
| 无限反复咨询 | 每 Run 次数、token、时间和单资源预算 |
| 咨询模型越权执行 | 固定 `tools=[]`，不继承 Agent 工具 |
| 主模型选择错误能力 | 清晰 Tool 描述、显式 capability 配置和错误结果 |
| 专家答案被主模型改坏 | 返回来源元数据，提示其为完整候选结论，并允许复核 |
| provider 调用失败 | 规范化错误，返回可供主模型决策的失败结果或按策略重试 |
| 咨询过程不可观察 | 增加调用来源、模型、资源、usage、duration 的结构化 trace/event |

## 第一阶段范围

第一阶段只验证一个真实路径：

```text
Quenda Code + Primary GLM + vision consultation + Kimi
```

验收场景包括：

1. GLM 调用 Kimi 直接解答图片数学题；
2. GLM 基于第一次结果和新的文字疑点再次咨询；
3. Kimi 检查 PPT 截图后，控制权返回 GLM 修改代码；
4. Kimi 无法调用写文件或 Shell 工具；
5. Kimi 的 `end_turn` 不会结束主 Run；
6. 咨询调用和成本在事件流中可观察。

第一阶段不实现：

- Consultation Session 或 `continue_from`；
- Consulted Model 自主工具调用；
- 动态多模型投票或并行 ensemble；
- provider 效果/成本/速度自动评分；
- 通用 multi-agent orchestration；
- nested consultation。

## 待验证问题

实现前仍需通过原型和测试确认：

1. `capabilities` 由 Primary Model 显式填写，还是可根据 resources 自动补全；
2. `context` 第一版是否只接受字符串，还是接受受限的 TextContent 列表；
3. Consultation failure 应作为失败 ToolResult 还是抛出 Runtime 错误；
4. `ModelConsulted` 应是独立事件，还是扩展现有 ModelCalled/ModelResponded；
5. Quenda Code 如何从 takeover routing 迁移到 consultation；
6. 默认咨询预算及耗尽后的用户可见语义；
7. ToolResult 是否需要第一版就支持结构化 response schema。
