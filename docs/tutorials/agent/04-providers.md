# 模型提供者

Quenda 内置了 26 个模型提供商的支持（共 300+ 个模型），并提供了灵活的扩展机制。

---

## 架构概览

```
ProviderRegistry (全局注册表)
└── ProviderSpec (提供商配置)
    ├── id: "deepseek"
    ├── base_url: "https://api.deepseek.com/v1"
    ├── api: "openai-completions"  # 通信协议
    └── models:
        ├── ModelSpec(id="deepseek-v4-flash", ...)
        └── ModelSpec(id="deepseek-r1", ...)

Model (运行时实例)
└── Provider + ModelSpec → invoke()
```

---

## 获取模型

### 使用全局注册表

```python
from quenda import get_provider_registry

registry = get_provider_registry()

# 通过 (provider_id, model_id) 获取
model = registry.get_model("deepseek", "deepseek-v4-flash")

# 获取 Provider
provider = registry.get_provider("openai")
```

### 查看可用模型

```python
# 列出所有提供商
registry.list_providers()
# ['anthropic', 'cerebras', 'cohere', 'dashscope', 'deepseek', ...]

# 列出所有 (provider, model) 对
registry.list_all_models()
# [('deepseek', 'deepseek-v4-flash'), ('openai', 'gpt-5.5'), ...]
```

---

## 内置提供商一览

| Provider ID | 环境变量 | 协议 |
|------------|---------|------|
| `openai` | `OPENAI_API_KEY` | openai-completions |
| `anthropic` | `ANTHROPIC_API_KEY` | anthropic-messages |
| `deepseek` | `DEEPSEEK_API_KEY` | openai-completions |
| `deepseek-anthropic` | `DEEPSEEK_API_KEY` | anthropic-messages |
| `google` | `GOOGLE_API_KEY` | openai-completions |
| `dashscope` | `DASHSCOPE_API_KEY` | openai-completions |
| `zhipu` | `ZHIPU_API_KEY` | openai-completions |
| `moonshot` | `MOONSHOT_API_KEY` | openai-completions |
| `xai` | `XAI_API_KEY` | openai-completions |
| `mistral` | `MISTRAL_API_KEY` | openai-completions |
| `cohere` | `COHERE_API_KEY` | openai-completions |
| `groq` | `GROQ_API_KEY` | openai-completions |
| `together` | `TOGETHER_API_KEY` | openai-completions |
| `siliconflow` | `SILICONFLOW_API_KEY` | openai-completions |
| `openrouter` | `OPENROUTER_API_KEY` | openai-completions |
| `perplexity` | `PERPLEXITY_API_KEY` | openai-completions |
| `fireworks` | `FIREWORKS_API_KEY` | openai-completions |
| `cerebras` | `CEREBRAS_API_KEY` | openai-completions |
| `ollama` | (无需 key) | openai-completions |
| `nvidia` | `NVIDIA_API_KEY` | openai-completions |
| `volcengine` | `VOLCENGINE_API_KEY` | openai-completions |
| `minimax` | `MINIMAX_API_KEY` | openai-completions |
| `stepfun` | `STEPFUN_API_KEY` | openai-completions |
| `xiaomi` | `XIAOMI_API_KEY` | openai-completions |
| `tencent` | `TENCENT_API_KEY` | openai-completions |
| `jdcloud` | `JDCLOUD_API_KEY` | openai-completions |

> DeepSeek 实际上注册了两个 Provider：`deepseek`（OpenAI 协议）和 `deepseek-anthropic`（Anthropic 协议），因为 deepseek-v4-flash 支持 Anthropic 格式。

---

## 配置 API Key

所有 API Key 通过环境变量配置：

```bash
# 单模型
export DEEPSEEK_API_KEY="sk-xxx"

# 多模型
export OPENAI_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"
```

Quenda 的 `EnvAuthResolver` 自动从环境变量解析 `${VAR_NAME}` 模式的配置。

---

## Model 对象

获取到 Model 后，可以使用它进行调用：

```python
model = registry.get_model("deepseek", "deepseek-v4-flash")

# Model 属性
model.id              # "deepseek-v4-flash"
model.name            # "DeepSeek V4 Flash"
model.provider        # Provider 实例
model.spec            # ModelSpec
model.context_window  # 上下文窗口大小（可能为 None）
model.tool_calling    # 是否支持工具调用

# 直接调用（同步）
response = model.invoke(messages, tools=tools)

# 流式调用
for chunk in model.invoke_stream(messages, tools=tools):
    print(chunk.content)
```

---

## ModelSpec 详解

```python
from quenda.providers import ModelSpec, ModelCost

spec = ModelSpec(
    # 标识
    id="qwen-max",
    name="Qwen Max",

    # 能力
    input=("text",),
    output=("text",),
    reasoning=False,
    tool_calling=True,
    streaming=True,
    vision=False,

    # 限制
    context_window=128000,
    max_output_tokens=8192,

    # 价格（每百万 token，美元）
    cost=ModelCost(
        input=2.0,
        output=6.0,
        cache_read=0.5,
        cache_write=1.0,
    ),

    # API 覆盖（可覆盖 Provider 默认值）
    api="openai-completions",
    base_url="https://custom.url/v1",
)
```

---

## 注册自定义提供商

### 方式一：代码注册

```python
from quenda.providers import (
    ProviderSpec, ModelSpec, ModelCost,
    get_provider_registry,
)

registry = get_provider_registry()

registry.register(ProviderSpec(
    id="my-provider",
    name="My Custom Provider",
    base_url="https://api.example.com/v1",
    api="openai-completions",  # 使用 OpenAI 兼容协议
    api_key="${MY_API_KEY}",   # 从环境变量获取
    models=(
        ModelSpec(
            id="my-model",
            name="My Model",
            tool_calling=True,
            context_window=32000,
        ),
    ),
))

# 使用
model = registry.get_model("my-provider", "my-model")
```

### 方式二：Model 覆盖

某些模型需要不同的 base_url 或 headers：

```python
registry.register(ProviderSpec(
    id="custom",
    name="Custom",
    base_url="https://default.api/v1",
    api="openai-completions",
    api_key="${CUSTOM_KEY}",
    models=(
        ModelSpec(
            id="special-model",
            name="Special Model",
            base_url="https://special.api/v1",  # 覆盖 provider 的 base_url
            headers={"X-Custom": "value"},       # 额外请求头
        ),
    ),
))
```

---

## API 协议

Quenda 支持两种内置通信协议：

| 协议 ID | 适用提供商 | 说明 |
|---------|-----------|------|
| `openai-completions` | OpenAI、DeepSeek、通义千问等 | 大多数兼容 |
| `anthropic-messages` | Anthropic Claude | Anthropic 原生格式 |

也可以通过 `ApiRegistry` 注册自定义协议：

```python
from quenda.providers.api import get_api_registry, Api

registry = get_api_registry()

class CustomApi(Api):
    def invoke(self, base_url, api_key, headers, model,
               messages, tools, timeout, max_retries):
        # 实现自定义调用逻辑
        ...

    def invoke_stream(self, *args, **kwargs):
        # 实现流式调用
        ...

registry.register("custom-protocol", CustomApi())
```

---

## 运行时切换模型

在 Agent 运行中可以动态切换模型：

```python
# 在 Agent 上切换
agent.set_model(new_model)

# 在 Session 上切换
session.set_model(new_model)

# 在 run/send 时临时切换
result = await session.send("你好", model=new_model)
result = await agent.run("你好", model=new_model)
```

---

## 错误处理

```python
from quenda.providers.errors import (
    ProviderError,        # 所有提供商错误的基类
    AuthenticationError,  # 认证失败
    RateLimitError,       # 限流
    NetworkError,         # 网络错误
    ModelNotFoundError,   # 模型未找到
    UnsupportedFeatureError,  # 不支持的特性
)

try:
    model = registry.get_model("unknown", "xxx")
except KeyError:
    print("提供商或模型不存在")

try:
    response = model.invoke(messages, tools=tools)
except AuthenticationError:
    print("请检查 API Key")
except RateLimitError:
    print("请求过于频繁，稍后重试")
except NetworkError:
    print("网络连接失败")
```

---

## 下一步

- [会话管理](./05-sessions.md) — 持久化与上下文管理
- [事件系统](./06-events.md) — 监控 Agent 的运行过程

---

<div align="right">
  <a href="./03-tools.md">← 上一页</a> ·
  <a href="../README.md">📚 教程首页</a> · <a href="../../README.md">🏠 项目首页</a> ·
  <a href="./05-sessions.md">下一页 →</a>
</div>
