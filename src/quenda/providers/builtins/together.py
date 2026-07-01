"""Together AI provider specification (open-source model hosting)."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

TOGETHER_SPEC = ProviderSpec(
    id="together",
    name="Together AI",
    base_url="https://api.together.xyz/v1",
    api="openai-completions",
    api_key="${TOGETHER_API_KEY}",
    models=(
        # Llama 3.3 family
        ModelSpec(
            id="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            name="Llama 3.3 70B Instruct Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.88, output=0.88),
        ),
        # Llama 3.2 family
        ModelSpec(
            id="meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
            name="Llama 3.2 90B Vision Turbo",
            context_window=131_072,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            name="Llama 3.2 11B Vision Turbo",
            context_window=131_072,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.18, output=0.18),
        ),
        ModelSpec(
            id="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            name="Llama 3.2 3B Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.06, output=0.06),
        ),
        # Llama 3.1 family
        ModelSpec(
            id="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            name="Llama 3.1 405B Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=3.5, output=3.5),
        ),
        ModelSpec(
            id="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            name="Llama 3.1 70B Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.88, output=0.88),
        ),
        ModelSpec(
            id="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            name="Llama 3.1 8B Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.18, output=0.18),
        ),
        # Qwen family
        ModelSpec(
            id="Qwen/Qwen3-235B-A22B-fp8",
            name="Qwen3 235B A22B",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-72B-Instruct-Turbo",
            name="Qwen2.5 72B Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.88, output=0.88),
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-Coder-32B-Instruct",
            name="Qwen2.5 Coder 32B",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.8, output=0.8),
        ),
        # DeepSeek family
        ModelSpec(
            id="deepseek-ai/DeepSeek-V3",
            name="DeepSeek V3",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=1.25, output=1.25),
        ),
        ModelSpec(
            id="deepseek-ai/DeepSeek-R1",
            name="DeepSeek R1",
            context_window=163_840,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=3.0, output=7.0),
        ),
        ModelSpec(
            id="deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            name="DeepSeek R1 Distill Llama 70B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=1.0, output=1.0),
        ),
        # Mistral family
        ModelSpec(
            id="mistralai/Mixtral-8x7B-Instruct-v0.1",
            name="Mixtral 8x7B Instruct",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.6, output=0.6),
        ),
        ModelSpec(
            id="mistralai/Mistral-7B-Instruct-v0.3",
            name="Mistral 7B Instruct v0.3",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.2, output=0.2),
        ),
        # Gemma family
        ModelSpec(
            id="google/gemma-2-27b-it",
            name="Gemma 2 27B IT",
            context_window=8_192,
            tool_calling=True,
            cost=ModelCost(input=0.8, output=0.8),
        ),
        # Phi family
        ModelSpec(
            id="microsoft/Phi-4-multimodal-instruct",
            name="Phi-4 Multimodal",
            context_window=131_072,
            tool_calling=True,
            vision=True,
        ),
    ),
)
