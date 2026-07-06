# ADR-028: Capability-Based Model Routing

## Status

Proposed (2026-07-06)

## Context

Quenda 已经具备多模态输入的基础设施：

- Kernel 层有 `TextContent` / `ImageContent` 内容块
- `ModelSpec.vision: bool` 标记模型视觉能力
- Provider 消息转换器能处理多模态内容
- Session storage 能序列化图片块

ADR-027 明确了多模态输入应该作为核心能力，而非 provider 特性。但当前缺失：

- `vision=True` 只是元数据，没有运行时能力校验
- 用户发送图片到非 vision 模型时，没有自动路由机制
- 没有"default"和"vision"作为模型角色的概念

一个朴素的设计是"遇到图片就报错，提示用户手动切换"。但这有严重问题：

1. 图片可能来自浏览器截图、屏幕截图、工具返回值，用户频繁手动切模型会让多模态能力变得别扭
2. 用户第一轮发图，第二轮纯文本问"图里第二项是什么"，仍需 vision 模型——检查的是整个有效上下文，不只是当前消息
3. 自动切换容易错误实现成 `session.model = vision_model`，污染持久化状态

Quenda 需要一个更准确的抽象：

> **基于输入能力需求的 Model Routing：default 和 vision 是两个模型角色，Runtime 每一轮根据有效上下文选择模型。**

## Decision

### 1. 模型角色，而非模型类型

配置应理解为：

```text
default：普通任务首选模型
vision：需要视觉能力时首选模型
```

而非：

```text
一个文本模型 + 一个视觉模型
```

因为 vision 模型通常也能处理文本，而 default 也可能本身支持 vision。

### 2. 自动路由，但显式可观察

```text
构造本轮有效上下文
        ↓
分析所需能力：text / vision / audio...
        ↓
ModelRouter 选择对应模型角色
        ↓
校验实际 ModelSpec 是否满足能力
        ↓
执行模型调用
        ↓
记录 ModelRouted 事件
```

**自动不等于隐式。路由可以自动，但必须可解释、可记录。**

### 3. 检查整个有效上下文，而非当前消息

需求检测应遍历本轮发送给模型的所有消息：

- 用户消息附件
- 工具返回图片
- 历史消息中保留的图片块
- 压缩后仍保留的多模态内容

用户第一轮发图，第二轮纯文本追问，第二轮仍需 vision 模型。

### 4. 路由是 per-run 决策，不修改 Session 默认模型

区分：

```text
configured model    用户配置的默认角色
resolved model      Runtime 本轮实际选中的模型
```

模型选择是 **per-run / per-turn** 的决策，不应该改变 Session 的默认配置。

### 5. 优先级：显式选择 > Session 锁定 > 能力路由 > default

用户显式锁定非 vision 模型时，即使需要 vision，也不偷偷覆盖：

```text
本次调用显式指定模型
        >
Session 锁定模型
        >
能力自动路由
        >
default
```

用户锁定 + 需要不满足的能力 → `UnsupportedFeatureError`，而非绕过用户选择。

### 6. 能力集合抽象，而非布尔字段

路由接口不写死成：

```python
if has_image:
    use_vision_model()
```

而是使用 capability 集合：

```python
required = {
    ModelCapability.TEXT,
    ModelCapability.VISION,
}
```

即使底层 `ModelSpec` 暂时还是布尔字段，通过适配器转换：

```python
def capabilities_of(spec: ModelSpec) -> set[ModelCapability]:
    result = {ModelCapability.TEXT}
    if spec.vision:
        result.add(ModelCapability.VISION)
    return result
```

这样未来支持 audio、video、长上下文、推理模型时，接口无需推翻。

## Architecture

### Layer Responsibilities

| Layer | Owns | Does not own |
|-------|------|--------------|
| Kernel | `ModelCapability` enum, `ModelRequirements`, `UnsupportedFeatureError` | 路由决策，模型选择 |
| Provider | `ModelSpec` 能力声明，执行已选定的模型 | 自己偷偷换模型 |
| Runtime | `ModelRequirementResolver`, `ModelRouter`, `CapabilityGuard`, 本轮路由决策 | 模型配置格式 |
| Host | 模型角色配置，路由开关，UI 展示 | 路由算法，能力校验 |

### Core Components

#### 1. ModelCapability (Kernel)

```python
class ModelCapability(StrEnum):
    TEXT = "text"
    VISION = "vision"
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"
```

#### 2. ModelRequirements (Kernel)

```python
@dataclass
class ModelRequirements:
    capabilities: set[ModelCapability]
```

#### 3. ModelRequirementResolver (Runtime)

```python
def resolve_requirements(messages: list[Message]) -> ModelRequirements:
    capabilities = {ModelCapability.TEXT}
    for message in messages:
        for block in message.content:
            if isinstance(block, ImageContent):
                capabilities.add(ModelCapability.VISION)
    return ModelRequirements(capabilities)
```

#### 4. ModelRouter (Runtime)

```python
@dataclass
class ModelRoutingResult:
    requested_role: str
    resolved_role: str
    model: Model
    required_capabilities: set[ModelCapability]
    reason: str

def route_model(
    requirements: ModelRequirements,
    default_model: Model,
    capability_models: dict[ModelCapability, Model],
) -> ModelRoutingResult:
    # default 满足能力时优先使用 default
    if capabilities_of(default_model.spec).issuperset(requirements.capabilities):
        return ModelRoutingResult(
            requested_role="default",
            resolved_role="default",
            model=default_model,
            required_capabilities=requirements.capabilities,
            reason="default model satisfies requirements",
        )

    # 需要额外能力时路由到对应模型
    for capability in requirements.capabilities:
        if capability not in capabilities_of(default_model.spec):
            capability_model = capability_models.get(capability)
            if capability_model is None:
                raise UnsupportedFeatureError(
                    f"No model configured for capability: {capability}"
                )
            return ModelRoutingResult(
                requested_role="default",
                resolved_role=capability.name,
                model=capability_model,
                required_capabilities=requirements.capabilities,
                reason=f"requires {capability.name}",
            )

    return ModelRoutingResult(...)  # fallback
```

#### 5. CapabilityGuard (Runtime)

```python
def ensure_supported(model: Model, requirements: ModelRequirements) -> None:
    model_caps = capabilities_of(model.spec)
    missing = requirements.capabilities - model_caps
    if missing:
        raise UnsupportedFeatureError(
            f"Model {model.id} does not support: {missing}"
        )
```

#### 6. Events (Runtime)

```python
@dataclass
class ModelRouted(Event):
    requested_role: str
    resolved_role: str
    provider: str
    model_id: str
    required_capabilities: set[str]
    reason: str
```

### Configuration

```yaml
# config.yaml
models:
  default:
    provider: openrouter
    model: deepseek/deepseek-v3.2

  vision:
    provider: dashscope
    model: qwen3-vl-plus

routing:
  capability_routing: true
  missing_capability: error  # error | warn | ignore
```

### Routing Behavior

| 场景 | 选择 |
|-----|------|
| 纯文本上下文 | `default` |
| 当前消息含图片 | `vision`（若 default 不支持） |
| 历史有效上下文含图片 | `vision`（若 default 不支持） |
| 工具返回截图 | `vision`（若 default 不支持） |
| `default` 本身支持 vision | 直接使用 `default` |
| 未配置 vision 模型 | `UnsupportedFeatureError` |
| 用户显式锁定非 vision 模型 + 发图 | `UnsupportedFeatureError` |

## Phase 1 Implementation Scope

第一阶段最小实现：

1. **配置层**：`models.default` + `models.vision`
2. **Kernel**：`ModelCapability`, `ModelRequirements`, `UnsupportedFeatureError`
3. **Runtime**：
   - `ModelRequirementResolver`
   - `ModelRouter`（仅 TEXT + VISION）
   - `CapabilityGuard`
   - `ModelRouted` Event
4. **Host**：
   - 模型角色配置解析
   - REPL 输出路由信息
   - `/models` 命令展示配置

暂不实现：

- audio routing
- video routing
- 复杂 fallback 链
- 成本优先路由策略
- 多模型并行调用

## Consequences

### Positive

- 建立了一套可扩展的 capability-based routing 机制
- vision 只是第一种非文本能力，未来 audio/video 可复用
- 自动路由提升用户体验，无需频繁手动切换
- 路由显式可观察，便于调试、审计、成本追踪
- 不污染 Session 持久化状态

### Negative

- 增加了 Runtime 编排复杂度
- 需要新的配置格式和事件类型
- 需要处理工具返回图片的场景
- 用户显式锁定模型时的错误处理需要清晰提示

## Alternatives Considered

### A. 早期失败 + 用户手动切换

Pros: 实现简单，显式清晰

Cons: 多模态体验别扭，图片来自工具返回时无法手动干预

Conclusion: 作为兜底机制保留，但不应是主要体验

### B. 遇到图片就修改 Session.model

Pros: 实现最简单

Cons: 污染持久化状态，下一轮纯文本时模型状态混乱

Conclusion: 拒绝

### C. 检查当前用户消息是否带图

Pros: 实现简单

Cons: 用户第一轮发图、第二轮追问时，误判为纯文本

Conclusion: 拒绝——必须检查整个有效上下文

## Decision Summary

Quenda 应建立 **capability-based model routing**：

- 配置层提供 default 和 vision 两个模型角色
- Runtime 根据本轮完整上下文解析能力需求并选择模型
- Kernel 定义能力语言与错误类型
- Provider 声明并执行已选定的模型
- Host 负责配置和展示

一句话概括：

> 不是给 Quenda 加一个"vision 模型切换按钮"，而是建立一套最小的 capability-based model routing。vision 只是这套机制支持的第一种非文本能力。