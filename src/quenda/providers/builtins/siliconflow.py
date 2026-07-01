"""SiliconFlow (硅基流动) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

SILICONFLOW_SPEC = ProviderSpec(
    id="siliconflow",
    name="SiliconFlow",
    base_url="https://api.siliconflow.cn/v1",
    api="openai-completions",
    api_key="${SILICONFLOW_API_KEY}",
    models=(
        # Qwen 3 family
        ModelSpec(
            id="Qwen/Qwen3-235B-A22B",
            name="Qwen3 235B A22B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="Qwen/Qwen3-32B",
            name="Qwen3 32B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="Qwen/Qwen3-14B",
            name="Qwen3 14B",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="Qwen/Qwen3-8B",
            name="Qwen3 8B",
            context_window=131_072,
            tool_calling=True,
        ),
        # Qwen 2.5 family
        ModelSpec(
            id="Qwen/Qwen2.5-72B-Instruct",
            name="Qwen2.5 72B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-32B-Instruct",
            name="Qwen2.5 32B Instruct",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.35, output=0.35),
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-14B-Instruct",
            name="Qwen2.5 14B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-7B-Instruct",
            name="Qwen2.5 7B Instruct",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.07, output=0.07),
        ),
        ModelSpec(
            id="Qwen/Qwen2.5-Coder-32B-Instruct",
            name="Qwen2.5 Coder 32B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # DeepSeek family
        ModelSpec(
            id="deepseek-ai/DeepSeek-V3",
            name="DeepSeek V3",
            context_window=64_000,
            tool_calling=True,
            cost=ModelCost(input=0.28, output=1.1),
        ),
        ModelSpec(
            id="deepseek-ai/DeepSeek-R1",
            name="DeepSeek R1",
            context_window=64_000,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            name="DeepSeek R1 Distill Qwen 32B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        # GLM family
        ModelSpec(
            id="THUDM/glm-4-9b-chat",
            name="GLM-4 9B Chat",
            context_window=131_072,
            tool_calling=True,
        ),
        # Llama family
        ModelSpec(
            id="meta-llama/Llama-3.3-70B-Instruct",
            name="Llama 3.3 70B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="meta-llama/Meta-Llama-3.1-405B-Instruct",
            name="Llama 3.1 405B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # Other models
        ModelSpec(
            id="THUDM/glm-4-9b-chat",
            name="GLM-4 9B Chat",
            tool_calling=True,
        ),
    ),
)
