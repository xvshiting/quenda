"""JD Cloud Coding (GLM) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelSpec
from kora.providers.provider import ProviderSpec

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
            id="GLM-4",
            name="GLM-4",
            tool_calling=True,
        ),
        ModelSpec(
            id="glm-4-plus",
            name="GLM-4 Plus",
            tool_calling=True,
        ),
        ModelSpec(
            id="glm-4-flash",
            name="GLM-4 Flash",
            tool_calling=True,
        ),
        ModelSpec(
            id="glm-4-long",
            name="GLM-4 Long",
            tool_calling=True,
        ),
    ),
)
