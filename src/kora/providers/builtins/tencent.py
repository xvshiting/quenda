"""Tencent (腾讯混元) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

TENCENT_SPEC = ProviderSpec(
    id="tencent",
    name="Tencent Hunyuan",
    base_url="https://api.hunyuan.cloud.tencent.com/v1",
    api="openai-completions",
    api_key="${TENCENT_API_KEY}",
    models=(
        # Hunyuan family
        ModelSpec(
            id="hunyuan-lite",
            name="Hunyuan Lite",
            context_window=256_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="hunyuan-standard",
            name="Hunyuan Standard",
            context_window=32_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="hunyuan-pro",
            name="Hunyuan Pro",
            context_window=32_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="hunyuan-turbo",
            name="Hunyuan Turbo",
            context_window=32_000,
            tool_calling=True,
        ),
        # Hy3 series
        ModelSpec(
            id="hy3-preview",
            name="Hy3 Preview",
            context_window=256_000,
            max_output_tokens=64_000,
            tool_calling=True,
            cost=ModelCost(input=0.06, output=0.21),
        ),
    ),
)
