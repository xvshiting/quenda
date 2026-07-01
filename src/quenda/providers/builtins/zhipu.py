"""Zhipu AI (智谱 GLM) provider specification via open.bigmodel.cn."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

ZHIPU_SPEC = ProviderSpec(
    id="zhipu",
    name="Zhipu AI",
    base_url="https://open.bigmodel.cn/api/paas/v4",
    api="openai-completions",
    api_key="${ZHIPU_API_KEY}",
    models=(
        # GLM-5.2 family (latest)
        ModelSpec(
            id="glm-5.2",
            name="GLM-5.2",
            context_window=1_000_000,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
        # GLM-5.1 family
        ModelSpec(
            id="glm-5.1",
            name="GLM-5.1",
            context_window=200_000,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
        # GLM-5 family
        ModelSpec(
            id="glm-5-turbo",
            name="GLM-5 Turbo",
            context_window=200_000,
            max_output_tokens=131_072,
            tool_calling=True,
            cost=ModelCost(input=1.2, output=4.0),
        ),
        # GLM-4 family
        ModelSpec(
            id="glm-4-plus",
            name="GLM-4 Plus",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=50.0, output=50.0),
        ),
        ModelSpec(
            id="glm-4-air",
            name="GLM-4 Air",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=1.0),
        ),
        ModelSpec(
            id="glm-4-airx",
            name="GLM-4 AirX",
            context_window=8_192,
            tool_calling=True,
            cost=ModelCost(input=10.0, output=10.0),
        ),
        ModelSpec(
            id="glm-4-flash",
            name="GLM-4 Flash",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.1, output=0.1),
        ),
        ModelSpec(
            id="glm-4-flashx",
            name="GLM-4 FlashX",
            context_window=128_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="glm-4-long",
            name="GLM-4 Long",
            context_window=1_048_576,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=1.0),
        ),
        # GLM-Z1 reasoning models
        ModelSpec(
            id="glm-z1-airx",
            name="GLM-Z1 AirX",
            context_window=8_192,
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="glm-z1-flash",
            name="GLM-Z1 Flash",
            context_window=128_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=0.35, output=0.35),
        ),
        # GLM-Vision
        ModelSpec(
            id="glm-5v-turbo",
            name="GLM-5V Turbo",
            context_window=200_000,
            max_output_tokens=131_072,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="glm-4v-plus",
            name="GLM-4V Plus",
            context_window=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=50.0, output=50.0),
        ),
        ModelSpec(
            id="glm-4v-flash",
            name="GLM-4V Flash",
            context_window=8_192,
            tool_calling=True,
            vision=True,
        ),
        # Older models
        ModelSpec(
            id="glm-4",
            name="GLM-4",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=100.0, output=100.0),
        ),
        ModelSpec(
            id="glm-3-turbo",
            name="GLM-3 Turbo",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=1.0),
        ),
    ),
)
