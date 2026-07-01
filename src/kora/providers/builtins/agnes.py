"""Agnes AI provider specification (OpenAI-compatible)."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

AGNES_SPEC = ProviderSpec(
    id="agnes",
    name="Agnes AI",
    base_url="https://apihub.agnes-ai.com/v1",
    api="openai-completions",
    api_key="${AGNES_API_KEY}",
    models=(
        ModelSpec(
            id="agnes-2.0-flash",
            name="Agnes 2.0 Flash",
            context_window=512_000,  # 512K
            max_output_tokens=65_500,  # 65.5K
            tool_calling=True,
            vision=True,  # Supports image understanding
            cost=ModelCost(
                input=0.0,  # Currently free
                output=0.0,  # Currently free
            ),
        ),
    ),
)
