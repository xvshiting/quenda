"""Groq provider specification (ultra-fast inference)."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

GROQ_SPEC = ProviderSpec(
    id="groq",
    name="Groq",
    base_url="https://api.groq.com/openai/v1",
    api="openai-completions",
    api_key="${GROQ_API_KEY}",
    models=(
        # Llama 3.3 family
        ModelSpec(
            id="llama-3.3-70b-versatile",
            name="Llama 3.3 70B Versatile",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.59, output=0.79),
        ),
        ModelSpec(
            id="llama-3.3-70b-specdec",
            name="Llama 3.3 70B SpecDec",
            context_window=8_192,
            tool_calling=True,
        ),
        # Llama 3.2 family
        ModelSpec(
            id="llama-3.2-90b-vision-preview",
            name="Llama 3.2 90B Vision",
            context_window=128_000,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="llama-3.2-11b-vision-preview",
            name="Llama 3.2 11B Vision",
            context_window=128_000,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.01, output=0.01),
        ),
        ModelSpec(
            id="llama-3.2-3b-preview",
            name="Llama 3.2 3B",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.01, output=0.01),
        ),
        ModelSpec(
            id="llama-3.2-1b-preview",
            name="Llama 3.2 1B",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.01, output=0.01),
        ),
        # Llama 3.1 family
        ModelSpec(
            id="llama-3.1-8b-instant",
            name="Llama 3.1 8B Instant",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.01, output=0.01),
        ),
        ModelSpec(
            id="llama-3.1-70b-versatile",
            name="Llama 3.1 70B Versatile",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.59, output=0.79),
        ),
        # Mixtral family
        ModelSpec(
            id="mixtral-8x7b-32768",
            name="Mixtral 8x7B",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.24, output=0.24),
        ),
        ModelSpec(
            id="mixtral-8x22b-instruct",
            name="Mixtral 8x22B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # Gemma family
        ModelSpec(
            id="gemma2-9b-it",
            name="Gemma 2 9B IT",
            context_window=8_192,
            tool_calling=True,
            cost=ModelCost(input=0.01, output=0.01),
        ),
        # Qwen family
        ModelSpec(
            id="qwen-2.5-coder-32b",
            name="Qwen2.5 Coder 32B",
            context_window=128_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen-2.5-32b",
            name="Qwen2.5 32B",
            context_window=128_000,
            tool_calling=True,
        ),
        # DeepSeek family
        ModelSpec(
            id="deepseek-r1-distill-llama-70b",
            name="DeepSeek R1 Distill Llama 70B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
    ),
)
