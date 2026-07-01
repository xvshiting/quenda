"""Mistral AI provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

MISTRAL_SPEC = ProviderSpec(
    id="mistral",
    name="Mistral AI",
    base_url="https://api.mistral.ai/v1",
    api="openai-completions",
    api_key="${MISTRAL_API_KEY}",
    models=(
        # Mistral Medium family
        ModelSpec(
            id="mistral-medium-2604",
            name="Mistral Medium 3.5",
            context_window=262_144,
            max_output_tokens=262_144,
            tool_calling=True,
            cost=ModelCost(input=1.5, output=7.5),
        ),
        ModelSpec(
            id="mistral-medium-latest",
            name="Mistral Medium (latest)",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=2.7, output=8.1),
        ),
        # Mistral Small family
        ModelSpec(
            id="mistral-small-latest",
            name="Mistral Small (latest)",
            context_window=256_000,
            max_output_tokens=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        ModelSpec(
            id="mistral-small-2603",
            name="Mistral Small 4",
            context_window=256_000,
            max_output_tokens=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        ModelSpec(
            id="mistral-small-2409",
            name="Mistral Small 24.09",
            context_window=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.2, output=0.6),
        ),
        # Mistral Large family
        ModelSpec(
            id="mistral-large-latest",
            name="Mistral Large (latest)",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=2.0, output=6.0),
        ),
        ModelSpec(
            id="mistral-large-2407",
            name="Mistral Large 2",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=2.0, output=6.0),
        ),
        # Codestral (code)
        ModelSpec(
            id="codestral-latest",
            name="Codestral (latest)",
            context_window=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=0.9),
        ),
        ModelSpec(
            id="codestral-2501",
            name="Codestral 25.01",
            context_window=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=0.9),
        ),
        # Mistral NeMo family
        ModelSpec(
            id="open-mistral-nemo",
            name="Mistral NeMo",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.15, output=0.15),
        ),
        ModelSpec(
            id="open-mistral-nemo-2407",
            name="Mistral NeMo 2407",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.15, output=0.15),
        ),
        # Mixtral family
        ModelSpec(
            id="open-mixtral-8x22b",
            name="Mixtral 8x22B",
            context_window=65_536,
            tool_calling=True,
            cost=ModelCost(input=0.65, output=0.65),
        ),
        ModelSpec(
            id="open-mixtral-8x7b",
            name="Mixtral 8x7B",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.24, output=0.24),
        ),
        # Mistral 7B
        ModelSpec(
            id="open-mistral-7b",
            name="Mistral 7B",
            context_window=32_768,
            tool_calling=True,
            cost=ModelCost(input=0.06, output=0.06),
        ),
        # Embedding models
        ModelSpec(
            id="mistral-embed",
            name="Mistral Embed",
            context_window=8_192,
            cost=ModelCost(input=0.1, output=0.0),
        ),
    ),
)
