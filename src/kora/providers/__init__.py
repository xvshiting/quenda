"""
Model providers for Kora.

## Architecture

```
Provider (e.g., DashScope, JDCloud)
├── id: "dashscope"
├── base_url: "https://..."
├── api: "openai-completions"
├── api_key: "${DASHSCOPE_API_KEY}"
└── models:
    ├── ModelSpec(id="qwen-max", ...)
    └── ModelSpec(id="qwen-plus", ...)
```

**Provider**: A model service provider (DashScope, JDCloud, OpenRouter, etc.)
  - Owns authentication, base URL, and model catalog
  - Uses an API protocol (openai-completions, anthropic-messages)

**ModelSpec**: Describes a model's capabilities and limits
  - context_window, tool_calling, pricing, etc.
  - Can override Provider defaults

**API**: The communication protocol implementation
  - openai-completions: Used by most providers
  - anthropic-messages: Anthropic-specific

## Usage

```python
from kora.providers import get_provider_registry

registry = get_provider_registry()

# Get a model
model = registry.get_model("dashscope", "qwen-max")

# Use with Agent
agent = Agent(model=model, tools=[...])
result = await session.send("Hello")
```

## Registering Custom Providers

```python
from kora.providers import ProviderSpec, ModelSpec, get_provider_registry

registry = get_provider_registry()

registry.register(ProviderSpec(
    id="my-provider",
    name="My Provider",
    base_url="https://api.example.com/v1",
    api="openai-completions",  # Use OpenAI-compatible API
    api_key="${MY_API_KEY}",
    models=(
        ModelSpec(id="my-model", name="My Model", tool_calling=True),
    ),
))
```

## Built-in Providers

| Provider ID | Models | API Key Env |
|------------|--------|-------------|
| openai | gpt-5.5, gpt-5.4, gpt-4o | OPENAI_API_KEY |
| anthropic | claude-5, claude-4.x | ANTHROPIC_API_KEY |
| xai | grok-4.3, grok-3 | XAI_API_KEY |
| mistral | mistral-medium, mistral-small | MISTRAL_API_KEY |
| cohere | command-a, command-r | COHERE_API_KEY |
| dashscope | qwen3.7, qwen3.6 | DASHSCOPE_API_KEY |
| deepseek | deepseek-v4, deepseek-r1 | DEEPSEEK_API_KEY |
| zhipu | glm-5.2, glm-5.1 | ZHIPU_API_KEY |
| moonshot | kimi-k2.7, kimi-k2.6 | MOONSHOT_API_KEY |
| google | gemini-3.5, gemini-2.5 | GOOGLE_API_KEY |
| groq | llama-3.3-70b, mixtral | GROQ_API_KEY |
| together | llama, qwen, deepseek | TOGETHER_API_KEY |
| siliconflow | qwen, deepseek | SILICONFLOW_API_KEY |
| volcengine | doubao, deepseek | VOLCENGINE_API_KEY |
| minimax | MiniMax-M3, M2.7 | MINIMAX_API_KEY |
| nvidia | nemotron, llama | NVIDIA_API_KEY |
| xiaomi | mimo-v2.5 | XIAOMI_API_KEY |
| stepfun | step-3.7 | STEPFUN_API_KEY |
| perplexity | sonar, sonar-pro | PERPLEXITY_API_KEY |
| fireworks | llama, qwen, deepseek | FIREWORKS_API_KEY |
| cerebras | llama-3.3-70b | CEREBRAS_API_KEY |
| tencent | hunyuan, hy3 | TENCENT_API_KEY |
| openrouter | (multi-provider) | OPENROUTER_API_KEY |
| ollama | (local models) | (none) |
| jdcloud | glm-5, glm-4 | JDCLOUD_API_KEY |
"""

from kora.providers.model import Model, ModelCost, ModelSpec
from kora.providers.provider import Provider, ProviderSpec
from kora.providers.auth import AuthResolver, EnvAuthResolver
from kora.providers.registry import ProviderRegistry, get_provider_registry

# Errors
from kora.providers.errors import (
    KoraError,
    ProviderError,
    AuthenticationError,
    APIError,
    RateLimitError,
    NetworkError,
    ModelNotFoundError,
    UnsupportedFeatureError,
)

# API
from kora.providers.api import (
    Api,
    ApiRegistry,
    get_api_registry,
    OpenAICompletionsApi,
    AnthropicMessagesApi,
)

# Built-in specs
from kora.providers.builtins import (
    ANTHROPIC_SPEC,
    CEREBRAS_SPEC,
    COHERE_SPEC,
    DASHSCOPE_SPEC,
    DEEPSEEK_ANTHROPIC_SPEC,
    DEEPSEEK_SPEC,
    FIREWORKS_SPEC,
    GOOGLE_SPEC,
    GROQ_SPEC,
    JDCLOUD_SPEC,
    MINIMAX_SPEC,
    MISTRAL_SPEC,
    MOONSHOT_SPEC,
    NVIDIA_SPEC,
    OLLAMA_SPEC,
    OPENAI_SPEC,
    OPENROUTER_SPEC,
    PERPLEXITY_SPEC,
    SILICONFLOW_SPEC,
    STEPFUN_SPEC,
    TENCENT_SPEC,
    TOGETHER_SPEC,
    VOLCENGINE_SPEC,
    XAI_SPEC,
    XIAOMI_SPEC,
    ZHIPU_SPEC,
)

__all__ = [
    # Core types
    "Model",
    "ModelSpec",
    "ModelCost",
    "Provider",
    "ProviderSpec",
    # Auth
    "AuthResolver",
    "EnvAuthResolver",
    # Registry
    "ProviderRegistry",
    "get_provider_registry",
    # Errors
    "KoraError",
    "ProviderError",
    "AuthenticationError",
    "APIError",
    "RateLimitError",
    "NetworkError",
    "ModelNotFoundError",
    "UnsupportedFeatureError",
    # API
    "Api",
    "ApiRegistry",
    "get_api_registry",
    "OpenAICompletionsApi",
    "AnthropicMessagesApi",
    # Built-in specs
    "ANTHROPIC_SPEC",
    "CEREBRAS_SPEC",
    "COHERE_SPEC",
    "DASHSCOPE_SPEC",
    "DEEPSEEK_ANTHROPIC_SPEC",
    "DEEPSEEK_SPEC",
    "FIREWORKS_SPEC",
    "GOOGLE_SPEC",
    "GROQ_SPEC",
    "JDCLOUD_SPEC",
    "MINIMAX_SPEC",
    "MISTRAL_SPEC",
    "MOONSHOT_SPEC",
    "NVIDIA_SPEC",
    "OLLAMA_SPEC",
    "OPENAI_SPEC",
    "OPENROUTER_SPEC",
    "PERPLEXITY_SPEC",
    "SILICONFLOW_SPEC",
    "STEPFUN_SPEC",
    "TENCENT_SPEC",
    "TOGETHER_SPEC",
    "VOLCENGINE_SPEC",
    "XAI_SPEC",
    "XIAOMI_SPEC",
    "ZHIPU_SPEC",
]
