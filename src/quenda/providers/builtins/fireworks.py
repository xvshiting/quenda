"""Fireworks AI provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelSpec
from quenda.providers.provider import ProviderSpec

FIREWORKS_SPEC = ProviderSpec(
    id="fireworks",
    name="Fireworks AI",
    base_url="https://api.fireworks.ai/inference/v1",
    api="openai-completions",
    api_key="${FIREWORKS_API_KEY}",
    models=(
        # Llama family
        ModelSpec(
            id="accounts/fireworks/models/llama-v3p3-70b-instruct",
            name="Llama 3.3 70B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/llama-v3p1-405b-instruct",
            name="Llama 3.1 405B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/llama-v3p1-70b-instruct",
            name="Llama 3.1 70B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/llama-v3p1-8b-instruct",
            name="Llama 3.1 8B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # Qwen family
        ModelSpec(
            id="accounts/fireworks/models/qwen3-235b-a22b",
            name="Qwen3 235B A22B",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/qwen2p5-72b-instruct",
            name="Qwen2.5 72B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/qwen2p5-coder-32b-instruct",
            name="Qwen2.5 Coder 32B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # DeepSeek family
        ModelSpec(
            id="accounts/fireworks/models/deepseek-r1",
            name="DeepSeek R1",
            context_window=163_840,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/deepseek-v3",
            name="DeepSeek V3",
            context_window=131_072,
            tool_calling=True,
        ),
        # Mistral family
        ModelSpec(
            id="accounts/fireworks/models/mistral-large-2411",
            name="Mistral Large 2411",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="accounts/fireworks/models/mixtral-8x7b-instruct",
            name="Mixtral 8x7B Instruct",
            context_window=32_768,
            tool_calling=True,
        ),
        # Gemma family
        ModelSpec(
            id="accounts/fireworks/models/gemma2-27b-it",
            name="Gemma 2 27B IT",
            context_window=8_192,
            tool_calling=True,
        ),
        # Phi family
        ModelSpec(
            id="accounts/fireworks/models/phi-4",
            name="Phi-4",
            context_window=16_384,
            tool_calling=True,
        ),
    ),
)
