"""Anthropic (Claude) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

ANTHROPIC_SPEC = ProviderSpec(
    id="anthropic",
    name="Anthropic",
    base_url="https://api.anthropic.com/v1",
    api="anthropic-messages",
    api_key="${ANTHROPIC_API_KEY}",
    models=(
        # Claude 5 family
        ModelSpec(
            id="claude-fable-5-20260609",
            name="Claude Fable 5",
            context_window=1_000_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=10.0, output=50.0),
        ),
        # Claude 4.8
        ModelSpec(
            id="claude-opus-4-8-20260528",
            name="Claude Opus 4.8",
            context_window=1_000_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=4.29, output=21.46),
        ),
        # Claude 4.7
        ModelSpec(
            id="claude-opus-4-7-20260416",
            name="Claude Opus 4.7",
            context_window=1_000_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=4.5, output=22.5),
        ),
        # Claude 4.6
        ModelSpec(
            id="claude-sonnet-4-6-20260313",
            name="Claude Sonnet 4.6",
            context_window=1_000_000,
            max_output_tokens=64_000,
            tool_calling=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="claude-opus-4-6-20260313",
            name="Claude Opus 4.6",
            context_window=1_000_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=5.0, output=25.0),
        ),
        # Claude 4 family
        ModelSpec(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            context_window=200_000,
            max_output_tokens=16_384,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="claude-opus-4-20250514",
            name="Claude Opus 4",
            context_window=200_000,
            max_output_tokens=32_000,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=15.0, output=75.0),
        ),
        # Claude 3.7
        ModelSpec(
            id="claude-3-7-sonnet-20250219",
            name="Claude 3.7 Sonnet",
            context_window=200_000,
            max_output_tokens=16_384,
            tool_calling=True,
            vision=True,
            reasoning=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        # Claude 3.5 family
        ModelSpec(
            id="claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            context_window=200_000,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            context_window=200_000,
            max_output_tokens=8_192,
            tool_calling=True,
            cost=ModelCost(input=0.8, output=4.0),
        ),
        # Claude 3 family
        ModelSpec(
            id="claude-3-opus-20240229",
            name="Claude 3 Opus",
            context_window=200_000,
            max_output_tokens=4_096,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=15.0, output=75.0),
        ),
        ModelSpec(
            id="claude-3-sonnet-20240229",
            name="Claude 3 Sonnet",
            context_window=200_000,
            max_output_tokens=4_096,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=3.0, output=15.0),
        ),
        ModelSpec(
            id="claude-3-haiku-20240307",
            name="Claude 3 Haiku",
            context_window=200_000,
            max_output_tokens=4_096,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.25, output=1.25),
        ),
    ),
)
