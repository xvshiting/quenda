"""DashScope (Alibaba Cloud 百炼 / 通义千问) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

DASHSCOPE_SPEC = ProviderSpec(
    id="dashscope",
    name="DashScope",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api="openai-completions",
    api_key="${DASHSCOPE_API_KEY}",
    models=(
        # Qwen 3.7 family (latest)
        ModelSpec(
            id="qwen3.7-max",
            name="Qwen3.7 Max",
            context_window=1_000_000,
            max_output_tokens=65_536,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen3.7-plus",
            name="Qwen3.7 Plus",
            context_window=1_000_000,
            max_output_tokens=64_000,
            tool_calling=True,
        ),
        # Qwen 3.6 family
        ModelSpec(
            id="qwen3.6-max-preview",
            name="Qwen3.6 Max Preview",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=1.04, output=6.24),
        ),
        ModelSpec(
            id="qwen3.6-plus",
            name="Qwen3.6 Plus",
            context_window=1_000_000,
            max_output_tokens=65_536,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen3.6-flash",
            name="Qwen3.6 Flash",
            context_window=1_000_000,
            max_output_tokens=65_536,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen3.6-27b",
            name="Qwen3.6 27B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.2, output=1.5),
        ),
        ModelSpec(
            id="qwen3.6-35b-a3b",
            name="Qwen3.6 35B A3B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
        ),
        # Qwen 3.5 family
        ModelSpec(
            id="qwen3.5-122b-a10b",
            name="Qwen3.5 122B A10B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.12, output=0.92),
        ),
        ModelSpec(
            id="qwen3.5-27b",
            name="Qwen3.5 27B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.09, output=0.69),
        ),
        ModelSpec(
            id="qwen3.5-35b-a3b",
            name="Qwen3.5 35B A3B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.06, output=0.46),
        ),
        ModelSpec(
            id="qwen3.5-9b",
            name="Qwen3.5 9B",
            context_window=262_144,
            max_output_tokens=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.1, output=0.15),
        ),
        ModelSpec(
            id="qwen3.5-plus",
            name="Qwen3.5 Plus",
            context_window=131_072,
            tool_calling=True,
        ),
        # Qwen 3 family
        ModelSpec(
            id="qwen3-235b-a22b",
            name="Qwen3 235B A22B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=2.0, output=8.0),
        ),
        ModelSpec(
            id="qwen3-32b",
            name="Qwen3 32B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="qwen3-14b",
            name="Qwen3 14B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="qwen3-8b",
            name="Qwen3 8B",
            context_window=131_072,
            tool_calling=True,
            reasoning=True,
        ),
        # Qwen 2.5 family
        ModelSpec(
            id="qwen2.5-72b-instruct",
            name="Qwen2.5 72B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5-32b-instruct",
            name="Qwen2.5 32B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5-14b-instruct",
            name="Qwen2.5 14B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5-7b-instruct",
            name="Qwen2.5 7B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5-coder-32b-instruct",
            name="Qwen2.5 Coder 32B Instruct",
            context_window=131_072,
            tool_calling=True,
        ),
        # Qwen-Max family
        ModelSpec(
            id="qwen-max",
            name="Qwen Max",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=2.0, output=6.0),
        ),
        ModelSpec(
            id="qwen-plus",
            name="Qwen Plus",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.4, output=2.0),
        ),
        ModelSpec(
            id="qwen-turbo",
            name="Qwen Turbo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.2, output=0.6),
        ),
        ModelSpec(
            id="qwen-long",
            name="Qwen Long",
            context_window=1_000_000,
            tool_calling=True,
            cost=ModelCost(input=0.2, output=0.2),
        ),
        # Qwen-VL (vision)
        ModelSpec(
            id="qwen-vl-max",
            name="Qwen VL Max",
            context_window=32_768,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="qwen-vl-plus",
            name="Qwen VL Plus",
            context_window=32_768,
            tool_calling=True,
            vision=True,
        ),
    ),
)
