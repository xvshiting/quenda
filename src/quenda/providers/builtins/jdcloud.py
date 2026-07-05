"""JD Cloud Coding (GLM) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelSpec
from quenda.providers.provider import ProviderSpec

JDCLOUD_SPEC = ProviderSpec(
    id="jdcloud",
    name="JD Cloud Coding",
    base_url="https://modelservice.jdcloud.com/coding/openai/v1",
    api="openai-completions",
    api_key="${JDCLOUD_API_KEY}",
    timeout=300.0,  # 5 minutes - JD Cloud API may be slower for complex tasks
    models=(
        ModelSpec(
            id="GLM-5",
            name="GLM-5",
            tool_calling=True,
        ),
        ModelSpec(
            id="Kimi-K2.5",
            name="Kimi-K2.5",
            tool_calling=True,
            vision=True,  # 支持多模态
        ),
        ModelSpec(
            id="GLM-4.7",
            name="GLM-4.7",
            tool_calling=True,
        ),
        ModelSpec(
            id="DeepSeek-V3.2",
            name="DeepSeek-V3.2",
            tool_calling=True,
        ),
        ModelSpec(
            id="MiniMax-M2.5",
            name="MiniMax-M2.5",
            tool_calling=True,
        ),
        ModelSpec(
            id="Kimi-K2-Turbo",
            name="Kimi-K2-Turbo",
            tool_calling=True,
        ),
        ModelSpec(
            id="Qwen3-Coder",
            name="Qwen3-Coder",
            tool_calling=True,
        ),
    ),
)
