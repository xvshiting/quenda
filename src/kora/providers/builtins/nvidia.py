"""Nvidia NIM provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

NVIDIA_SPEC = ProviderSpec(
    id="nvidia",
    name="Nvidia NIM",
    base_url="https://integrate.api.nvidia.com/v1",
    api="openai-completions",
    api_key="${NVIDIA_API_KEY}",
    models=(
        # Nemotron 3 family
        ModelSpec(
            id="nvidia/nemotron-3-ultra-550b-a55b",
            name="Nemotron 3 Ultra 550B A55B",
            context_window=1_000_000,
            max_output_tokens=128_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="nvidia/nemotron-3-super-120b-a12b",
            name="Nemotron 3 Super 120B A12B",
            context_window=262_144,
            max_output_tokens=262_144,
            tool_calling=True,
        ),
        ModelSpec(
            id="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            name="Nemotron 3 Nano Omni 30B A3B Reasoning",
            context_window=256_000,
            max_output_tokens=65_536,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="nvidia/nemotron-3-content-safety",
            name="Nemotron 3 Content Safety",
            context_window=128_000,
            max_output_tokens=4_096,
        ),
        ModelSpec(
            id="nvidia/nemotron-3.5-content-safety",
            name="Nemotron 3.5 Content Safety",
            context_window=128_000,
            max_output_tokens=8_192,
        ),
        ModelSpec(
            id="nvidia/nemotron-voicechat",
            name="Nemotron VoiceChat",
            context_window=128_000,
            max_output_tokens=8_192,
        ),
        # Nemotron Cascade family
        ModelSpec(
            id="nvidia/nemotron-cascade-2-30b-a3b",
            name="Nemotron Cascade 2 30B A3B",
            context_window=256_000,
            max_output_tokens=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.14, output=0.6),
        ),
        # Llama family via Nvidia
        ModelSpec(
            id="meta/llama-3.3-70b-instruct",
            name="Llama 3.3 70B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta/llama-3.2-3b-instruct",
            name="Llama 3.2 3B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta/llama-3.2-1b-instruct",
            name="Llama 3.2 1B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta/llama-3.1-405b-instruct",
            name="Llama 3.1 405B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta/llama-3.1-70b-instruct",
            name="Llama 3.1 70B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta/llama-3.1-8b-instruct",
            name="Llama 3.1 8B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        # Mistral family via Nvidia
        ModelSpec(
            id="mistralai/mistral-large",
            name="Mistral Large (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="mistralai/mixtral-8x7b-instruct",
            name="Mixtral 8x7B Instruct (via Nvidia)",
            context_window=32_768,
            tool_calling=True,
        ),
        ModelSpec(
            id="mistralai/mistral-7b-instruct",
            name="Mistral 7B Instruct (via Nvidia)",
            context_window=32_768,
            tool_calling=True,
        ),
        # Qwen family via Nvidia
        ModelSpec(
            id="qwen/qwen3-235b-a22b",
            name="Qwen3 235B A22B (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen/qwen2.5-72b-instruct",
            name="Qwen2.5 72B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen/qwen2.5-7b-instruct",
            name="Qwen2.5 7B Instruct (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        # DeepSeek family via Nvidia
        ModelSpec(
            id="deepseek-ai/deepseek-r1",
            name="DeepSeek R1 (via Nvidia)",
            context_window=163_840,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="deepseek-ai/deepseek-v3",
            name="DeepSeek V3 (via Nvidia)",
            context_window=131_072,
            tool_calling=True,
        ),
        # Google family via Nvidia
        ModelSpec(
            id="google/gemma-2-27b-it",
            name="Gemma 2 27B IT (via Nvidia)",
            context_window=8_192,
            tool_calling=True,
        ),
        ModelSpec(
            id="google/gemma-2-9b-it",
            name="Gemma 2 9B IT (via Nvidia)",
            context_window=8_192,
            tool_calling=True,
        ),
        # Rerank models
        ModelSpec(
            id="nvidia/nemotron-reward",
            name="Nemotron Reward",
            context_window=4_096,
        ),
        ModelSpec(
            id="nvidia/llama-nemotron-rerank-vl-1b-v2",
            name="Llama Nemotron Rerank VL 1B v2",
            context_window=128_000,
        ),
    ),
)
