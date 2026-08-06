"""Volcengine Ark Coding Plan provider specifications."""

from __future__ import annotations

from quenda.providers.model import ModelSpec
from quenda.providers.provider import ProviderSpec


def _coding_plan_models() -> tuple[ModelSpec, ...]:
    """Return a fresh model catalog shared by both supported API protocols."""
    return (
        ModelSpec(
            id="ark-code-latest",
            name="Ark Code Latest (console-routed)",
            reasoning=True,
            tool_calling=True,
            vision=True,
            metadata={"routing": True},
        ),
        ModelSpec(
            id="auto",
            name="Auto",
            reasoning=True,
            tool_calling=True,
            vision=True,
            metadata={"routing": True},
        ),
        ModelSpec(
            id="doubao-seed-2.1-turbo",
            name="Doubao Seed 2.1 Turbo",
            reasoning=True,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="doubao-seed-2.0-code",
            name="Doubao Seed 2.0 Code",
            reasoning=True,
            tool_calling=True,
            vision=True,
            metadata={"deprecated": True},
        ),
        ModelSpec(
            id="doubao-seed-2.0-pro",
            name="Doubao Seed 2.0 Pro",
            reasoning=True,
            tool_calling=True,
            vision=True,
            metadata={"deprecated": True},
        ),
        ModelSpec(
            id="doubao-seed-2.0-lite",
            name="Doubao Seed 2.0 Lite",
            reasoning=True,
            tool_calling=True,
        ),
        ModelSpec(
            id="doubao-seed-code",
            name="Doubao Seed Code",
            reasoning=True,
            tool_calling=True,
            metadata={"deprecated": True},
        ),
        ModelSpec(
            id="deepseek-v4-flash",
            name="DeepSeek V4 Flash",
            reasoning=True,
            tool_calling=True,
        ),
        ModelSpec(
            id="glm-5.2",
            name="GLM 5.2",
            reasoning=True,
            tool_calling=True,
            context_window=1_000_000
        ),
        ModelSpec(
            id="glm-latest",
            name="GLM Latest",
            reasoning=True,
            tool_calling=True,
            metadata={"routing": True},
        ),
        ModelSpec(
            id="kimi-k2.7-code",
            name="Kimi K2.7 Code",
            reasoning=True,
            tool_calling=True,
            vision=True,
        ),
        ModelSpec(
            id="minimax-m3",
            name="MiniMax M3",
            reasoning=True,
            tool_calling=True,
        ),
        ModelSpec(
            id="deepseek-v4-pro",
            name="DeepSeek V4 Pro",
            reasoning=True,
            tool_calling=True,
        ),
        ModelSpec(
            id="minimax-m2.7",
            name="MiniMax M2.7",
            reasoning=True,
            tool_calling=True,
            metadata={"deprecated": True},
        ),
        ModelSpec(
            id="kimi-k2.6",
            name="Kimi K2.6",
            reasoning=True,
            tool_calling=True,
            metadata={"deprecated": True},
        ),
    )


VOLCENGINE_CODING_SPEC = ProviderSpec(
    id="volcengine-coding",
    name="Volcengine Ark Coding Plan",
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    api="openai-completions",
    api_key="${VOLCENGINE_API_KEY}",
    models=_coding_plan_models(),
)

VOLCENGINE_CODING_ANTHROPIC_SPEC = ProviderSpec(
    id="volcengine-coding-anthropic",
    name="Volcengine Ark Coding Plan (Anthropic API)",
    base_url="https://ark.cn-beijing.volces.com/api/coding",
    api="anthropic-messages",
    api_key="${VOLCENGINE_API_KEY}",
    models=_coding_plan_models(),
)
