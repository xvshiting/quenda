"""StepFun (阶跃星辰) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

STEPFUN_SPEC = ProviderSpec(
    id="stepfun",
    name="StepFun",
    base_url="https://api.stepfun.com/v1",
    api="openai-completions",
    api_key="${STEPFUN_API_KEY}",
    models=(
        # Step 3.7 family (latest)
        ModelSpec(
            id="step-3.7-flash",
            name="Step 3.7 Flash",
            context_window=256_000,
            max_output_tokens=256_000,
            tool_calling=True,
        ),
        # Step 3.5 family
        ModelSpec(
            id="step-3.5-flash-2603",
            name="Step 3.5 Flash 2603",
            context_window=256_000,
            max_output_tokens=256_000,
            tool_calling=True,
            cost=ModelCost(input=0.1, output=0.3),
        ),
        # Step 2 family
        ModelSpec(
            id="step-2-16k",
            name="Step 2 16K",
            context_window=16_384,
            tool_calling=True,
        ),
        ModelSpec(
            id="step-1-8k",
            name="Step 1 8K",
            context_window=8_192,
            tool_calling=True,
        ),
    ),
)
