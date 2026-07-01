"""Google Gemini provider specification (via OpenAI-compatible endpoint)."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

GOOGLE_SPEC = ProviderSpec(
    id="google",
    name="Google AI",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    api="openai-completions",
    api_key="${GOOGLE_API_KEY}",
    models=(
        # Gemini 2.5 family
        ModelSpec(
            id="gemini-2.5-pro-preview-06-05",
            name="Gemini 2.5 Pro Preview",
            context_window=1_048_576,
            max_output_tokens=65_536,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=1.25, output=5.0),
        ),
        ModelSpec(
            id="gemini-2.5-flash-preview-05-20",
            name="Gemini 2.5 Flash Preview",
            context_window=1_048_576,
            max_output_tokens=65_536,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        # Gemini 2.0 family
        ModelSpec(
            id="gemini-2.0-flash",
            name="Gemini 2.0 Flash",
            context_window=1_048_576,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.1, output=0.4),
        ),
        ModelSpec(
            id="gemini-2.0-flash-lite",
            name="Gemini 2.0 Flash Lite",
            context_window=1_048_576,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.075, output=0.3),
        ),
        ModelSpec(
            id="gemini-2.0-pro-exp",
            name="Gemini 2.0 Pro Experimental",
            context_window=1_048_576,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
        ),
        # Gemini 1.5 family
        ModelSpec(
            id="gemini-1.5-pro",
            name="Gemini 1.5 Pro",
            context_window=2_097_152,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=1.25, output=5.0),
        ),
        ModelSpec(
            id="gemini-1.5-flash",
            name="Gemini 1.5 Flash",
            context_window=1_048_576,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.075, output=0.3),
        ),
        ModelSpec(
            id="gemini-1.5-flash-8b",
            name="Gemini 1.5 Flash 8B",
            context_window=1_048_576,
            max_output_tokens=8_192,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.0375, output=0.15),
        ),
        # Gemini 1.0
        ModelSpec(
            id="gemini-1.0-pro",
            name="Gemini 1.0 Pro",
            context_window=32_000,
            tool_calling=True,
            cost=ModelCost(input=0.5, output=1.5),
        ),
    ),
)
