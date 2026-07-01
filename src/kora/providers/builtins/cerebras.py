"""Cerebras (ultra-fast inference) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelSpec
from kora.providers.provider import ProviderSpec

CEREBRAS_SPEC = ProviderSpec(
    id="cerebras",
    name="Cerebras",
    base_url="https://api.cerebras.ai/v1",
    api="openai-completions",
    api_key="${CEREBRAS_API_KEY}",
    models=(
        # Llama 3 family (optimized for speed)
        ModelSpec(
            id="llama-3.3-70b",
            name="Llama 3.3 70B",
            context_window=128_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="llama-3.1-8b",
            name="Llama 3.1 8B",
            context_window=128_000,
            tool_calling=True,
        ),
    ),
)
