"""MiniMax (海螺 AI) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

MINIMAX_SPEC = ProviderSpec(
    id="minimax",
    name="MiniMax",
    base_url="https://api.minimax.io/v1",
    api="openai-completions",
    api_key="${MINIMAX_API_KEY}",
    models=(
        # MiniMax-M3 (latest)
        ModelSpec(
            id="MiniMax-M3",
            name="MiniMax M3",
            context_window=512_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=1.2),
        ),
        # MiniMax-M2.7 family
        ModelSpec(
            id="MiniMax-M2.7",
            name="MiniMax M2.7",
            context_window=204_800,
            max_output_tokens=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.25, output=1.0),
        ),
        ModelSpec(
            id="MiniMax-M2.7-highspeed",
            name="MiniMax M2.7 Highspeed",
            context_window=204_800,
            max_output_tokens=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.33, output=1.32),
        ),
        # MiniMax-M1 family
        ModelSpec(
            id="MiniMax-Text-01",
            name="MiniMax Text 01",
            context_window=1_000_000,
            tool_calling=True,
        ),
        # Abab family
        ModelSpec(
            id="abab6.5-chat",
            name="ABAB 6.5 Chat",
            context_window=245_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="abab6.5s-chat",
            name="ABAB 6.5S Chat",
            context_window=245_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="abab5.5-chat",
            name="ABAB 5.5 Chat",
            context_window=16_384,
            tool_calling=True,
        ),
        ModelSpec(
            id="abab5.5s-chat",
            name="ABAB 5.5S Chat",
            context_window=8_192,
            tool_calling=True,
        ),
    ),
)
