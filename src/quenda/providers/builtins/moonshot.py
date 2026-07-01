"""Moonshot AI (月之暗面 Kimi) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

MOONSHOT_SPEC = ProviderSpec(
    id="moonshot",
    name="Moonshot AI",
    base_url="https://api.moonshot.cn/v1",
    api="openai-completions",
    api_key="${MOONSHOT_API_KEY}",
    models=(
        # Kimi K2.7 family (latest)
        ModelSpec(
            id="kimi-k2.7-code",
            name="Kimi K2.7 Code",
            context_window=262_144,
            max_output_tokens=262_144,
            tool_calling=True,
        ),
        ModelSpec(
            id="kimi-k2.7-code-highspeed",
            name="Kimi K2.7 Code Highspeed",
            context_window=262_144,
            max_output_tokens=262_144,
            tool_calling=True,
            cost=ModelCost(input=1.9, output=8.0),
        ),
        # Kimi K2.6
        ModelSpec(
            id="kimi-k2.6",
            name="Kimi K2.6",
            context_window=262_144,
            max_output_tokens=262_144,
            tool_calling=True,
        ),
        # Kimi K2
        ModelSpec(
            id="kimi-k2-0905-preview",
            name="Kimi K2 Preview",
            context_window=131_072,
            tool_calling=True,
        ),
        # Moonshot V1 family
        ModelSpec(
            id="moonshot-v1-8k",
            name="Moonshot V1 8K",
            context_window=8_192,
            tool_calling=True,
            cost=ModelCost(input=12.0, output=12.0),
        ),
        ModelSpec(
            id="moonshot-v1-32k",
            name="Moonshot V1 32K",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=24.0, output=24.0),
        ),
        ModelSpec(
            id="moonshot-v1-128k",
            name="Moonshot V1 128K",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=60.0, output=60.0),
        ),
        ModelSpec(
            id="moonshot-v1-auto",
            name="Moonshot V1 Auto",
            tool_calling=True,
        ),
    ),
)
