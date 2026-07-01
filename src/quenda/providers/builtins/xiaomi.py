"""Xiaomi (MiMo) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

XIAOMI_SPEC = ProviderSpec(
    id="xiaomi",
    name="Xiaomi MiMo",
    base_url="https://api.xiaomimimo.com/v1",
    api="openai-completions",
    api_key="${XIAOMI_API_KEY}",
    models=(
        # MiMo V2.5 family (latest)
        ModelSpec(
            id="mimo-v2.5-pro-ultraspeed",
            name="MiMo V2.5 Pro UltraSpeed",
            context_window=1_048_576,
            max_output_tokens=131_072,
            tool_calling=True,
            cost=ModelCost(input=1.3, output=2.61),
        ),
        ModelSpec(
            id="mimo-v2.5-pro",
            name="MiMo V2.5 Pro",
            context_window=1_048_576,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="mimo-v2.5",
            name="MiMo V2.5",
            context_window=1_048_576,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
        # MiMo V2 family
        ModelSpec(
            id="mimo-v2-omni",
            name="MiMo V2 Omni",
            context_window=262_144,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
        ModelSpec(
            id="mimo-v2-pro",
            name="MiMo V2 Pro",
            context_window=1_048_576,
            max_output_tokens=131_072,
            tool_calling=True,
        ),
    ),
)
