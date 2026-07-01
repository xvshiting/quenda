"""DeepSeek provider specifications (OpenAI-compatible and Anthropic-compatible)."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

DEEPSEEK_SPEC = ProviderSpec(
    id="deepseek",
    name="DeepSeek",
    base_url="https://api.deepseek.com",
    api="openai-completions",
    api_key="${DEEPSEEK_API_KEY}",
    models=(
        # V4 series (latest)
        ModelSpec(
            id="deepseek-v4-flash",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            max_output_tokens=384_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="deepseek-v4-pro",
            name="DeepSeek V4 Pro",
            context_window=1_000_000,
            max_output_tokens=384_000,
            tool_calling=True,
        ),
        # V3 series
        ModelSpec(
            id="deepseek-chat",
            name="DeepSeek Chat (V3)",
            context_window=1_000_000,
            max_output_tokens=384_000,
            tool_calling=True,
            cost=ModelCost(input=0.14, output=0.28),
        ),
        ModelSpec(
            id="deepseek-coder",
            name="DeepSeek Coder",
            context_window=64_000,
            tool_calling=True,
            cost=ModelCost(input=0.14, output=0.28),
        ),
        # R1 reasoning series
        ModelSpec(
            id="deepseek-reasoner",
            name="DeepSeek Reasoner (R1)",
            context_window=1_000_000,
            max_output_tokens=384_000,
            reasoning=True,
            tool_calling=True,
            cost=ModelCost(input=0.55, output=2.19),
        ),
    ),
)

DEEPSEEK_ANTHROPIC_SPEC = ProviderSpec(
    id="deepseek-anthropic",
    name="DeepSeek (Anthropic API)",
    base_url="https://api.deepseek.com/anthropic",
    api="anthropic-messages",
    api_key="${DEEPSEEK_API_KEY}",
    models=(
        ModelSpec(
            id="deepseek-v4-flash",
            name="DeepSeek V4 Flash",
            context_window=1_000_000,
            max_output_tokens=384_000,
            tool_calling=True,
        ),
        ModelSpec(
            id="deepseek-v4-pro",
            name="DeepSeek V4 Pro",
            context_window=1_000_000,
            max_output_tokens=384_000,
            tool_calling=True,
        ),
    ),
)
