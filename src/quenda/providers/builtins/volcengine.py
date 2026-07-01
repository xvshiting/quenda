"""Volcengine (火山方舟 / 字节豆包) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

VOLCENGINE_SPEC = ProviderSpec(
    id="volcengine",
    name="Volcengine Ark",
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api="openai-completions",
    api_key="${VOLCENGINE_API_KEY}",
    models=(
        # Doubao (豆包) family - most popular
        ModelSpec(
            id="doubao-seed-1-6-250415",
            name="Doubao Seed 1.6",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.8, output=2.0),
        ),
        ModelSpec(
            id="doubao-pro-256k-241115",
            name="Doubao Pro 256K",
            context_window=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.5, output=1.5),
        ),
        ModelSpec(
            id="doubao-pro-32k-241028",
            name="Doubao Pro 32K",
            context_window=32_000,
            tool_calling=True,
            cost=ModelCost(input=0.35, output=0.7),
        ),
        ModelSpec(
            id="doubao-1-5-pro-32k-250115",
            name="Doubao 1.5 Pro 32K",
            context_window=32_000,
            tool_calling=True,
            cost=ModelCost(input=0.8, output=2.0),
        ),
        ModelSpec(
            id="doubao-1-5-pro-256k-250115",
            name="Doubao 1.5 Pro 256K",
            context_window=256_000,
            tool_calling=True,
            cost=ModelCost(input=1.2, output=3.0),
        ),
        ModelSpec(
            id="doubao-1-5-pro-context-1m-250328",
            name="Doubao 1.5 Pro 1M Context",
            context_window=1_048_576,
            tool_calling=True,
            cost=ModelCost(input=5.0, output=12.0),
        ),
        ModelSpec(
            id="doubao-1-5-thinking-pro-250415",
            name="Doubao 1.5 Thinking Pro",
            context_window=128_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=4.0, output=10.0),
        ),
        # DeepSeek via Volcengine
        ModelSpec(
            id="deepseek-r1-250120",
            name="DeepSeek R1 (via Volcengine)",
            context_window=64_000,
            tool_calling=True,
            reasoning=True,
        ),
        # Qwen via Volcengine
        ModelSpec(
            id="qwen2-5-72b-instruct",
            name="Qwen2.5 72B (via Volcengine)",
            context_window=131_072,
            tool_calling=True,
        ),
    ),
)
