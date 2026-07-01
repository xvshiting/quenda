"""Perplexity AI provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

PERPLEXITY_SPEC = ProviderSpec(
    id="perplexity",
    name="Perplexity",
    base_url="https://api.perplexity.ai",
    api="openai-completions",
    api_key="${PERPLEXITY_API_KEY}",
    models=(
        # Sonar family (search-augmented)
        ModelSpec(
            id="sonar",
            name="Sonar",
            context_window=127_000,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=1.0),
        ),
        ModelSpec(
            id="sonar-pro",
            name="Sonar Pro",
            context_window=200_000,
            tool_calling=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="sonar-reasoning",
            name="Sonar Reasoning",
            context_window=127_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=1.0, output=5.0),
        ),
        ModelSpec(
            id="sonar-reasoning-pro",
            name="Sonar Reasoning Pro",
            context_window=127_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=2.0, output=8.0),
        ),
        # R1 series
        ModelSpec(
            id="r1-1776",
            name="R1 1776",
            context_window=127_000,
            tool_calling=True,
            reasoning=True,
        ),
    ),
)
