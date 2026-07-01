"""xAI (Grok) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

XAI_SPEC = ProviderSpec(
    id="xai",
    name="xAI",
    base_url="https://api.x.ai/v1",
    api="openai-completions",
    api_key="${XAI_API_KEY}",
    models=(
        # Grok 4 family
        ModelSpec(
            id="grok-4.3",
            name="Grok 4.3",
            context_window=1_000_000,
            max_output_tokens=30_000,
            tool_calling=True,
            cost=ModelCost(input=1.25, output=2.5),
        ),
        ModelSpec(
            id="grok-4.20-reasoning",
            name="Grok 4.20 Reasoning",
            context_window=1_000_000,
            max_output_tokens=30_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=1.25, output=2.5),
        ),
        ModelSpec(
            id="grok-4.20-non-reasoning",
            name="Grok 4.20 Non-Reasoning",
            context_window=1_000_000,
            max_output_tokens=30_000,
            tool_calling=True,
            cost=ModelCost(input=1.25, output=2.5),
        ),
        ModelSpec(
            id="grok-build-0.1",
            name="Grok Build 0.1",
            context_window=256_000,
            max_output_tokens=256_000,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=2.0),
        ),
        # Grok 3 family
        ModelSpec(
            id="grok-3",
            name="Grok 3",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="grok-3-fast",
            name="Grok 3 Fast",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=0.5),
        ),
        ModelSpec(
            id="grok-3-mini",
            name="Grok 3 Mini",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=0.5),
        ),
        # Grok 2 family
        ModelSpec(
            id="grok-2-1212",
            name="Grok 2 1212",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=2.0, output=10.0),
        ),
        ModelSpec(
            id="grok-2-vision-1212",
            name="Grok 2 Vision 1212",
            context_window=32_768,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=2.0, output=10.0),
        ),
        # Grok Beta
        ModelSpec(
            id="grok-beta",
            name="Grok Beta",
            context_window=131_072,
            tool_calling=True,
        ),
    ),
)
