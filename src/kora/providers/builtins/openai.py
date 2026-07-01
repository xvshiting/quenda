"""OpenAI provider specification."""

from __future__ import annotations

from kora.providers.model import ModelCost, ModelSpec
from kora.providers.provider import ProviderSpec

OPENAI_SPEC = ProviderSpec(
    id="openai",
    name="OpenAI",
    base_url="https://api.openai.com/v1",
    api="openai-completions",
    api_key="${OPENAI_API_KEY}",
    models=(
        # GPT-5.5 family (latest)
        ModelSpec(
            id="gpt-5.5",
            name="GPT-5.5",
            context_window=1_050_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=3.0, output=18.0),
        ),
        ModelSpec(
            id="gpt-5.5-pro",
            name="GPT-5.5 Pro",
            context_window=1_050_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=27.27, output=163.64),
        ),
        ModelSpec(
            id="gpt-5.5-instant",
            name="GPT-5.5 Instant",
            context_window=400_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=5.0, output=30.0),
        ),
        # GPT-5.4 family
        ModelSpec(
            id="gpt-5.4",
            name="GPT-5.4",
            context_window=1_050_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=2.2, output=14.0),
        ),
        ModelSpec(
            id="gpt-5.4-pro",
            name="GPT-5.4 Pro",
            context_window=1_050_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=27.0, output=160.0),
        ),
        ModelSpec(
            id="gpt-5.4-mini",
            name="GPT-5.4 mini",
            context_window=400_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.68, output=4.0),
        ),
        ModelSpec(
            id="gpt-5.4-nano",
            name="GPT-5.4 nano",
            context_window=400_000,
            max_output_tokens=128_000,
            tool_calling=True,
            cost=ModelCost(input=0.18, output=1.1),
        ),
        # GPT-5.3
        ModelSpec(
            id="gpt-5.3-chat-latest",
            name="GPT-5.3 Chat",
            context_window=128_000,
            max_output_tokens=16_384,
            tool_calling=True,
            cost=ModelCost(input=1.75, output=14.0),
        ),
        # GPT-4o family
        ModelSpec(
            id="gpt-4o",
            name="GPT-4o",
            context_window=128_000,
            max_output_tokens=16_384,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=2.5, output=10.0),
        ),
        ModelSpec(
            id="gpt-4o-mini",
            name="GPT-4o mini",
            context_window=128_000,
            max_output_tokens=16_384,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        # o-series reasoning models
        ModelSpec(
            id="o3",
            name="o3",
            context_window=200_000,
            max_output_tokens=100_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=10.0, output=40.0),
        ),
        ModelSpec(
            id="o3-mini",
            name="o3-mini",
            context_window=200_000,
            max_output_tokens=100_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=1.1, output=4.4),
        ),
        ModelSpec(
            id="o1",
            name="o1",
            context_window=200_000,
            max_output_tokens=100_000,
            tool_calling=True,
            reasoning=True,
            cost=ModelCost(input=15.0, output=60.0),
        ),
        ModelSpec(
            id="o1-mini",
            name="o1-mini",
            context_window=128_000,
            max_output_tokens=65_536,
            reasoning=True,
            cost=ModelCost(input=1.1, output=4.4),
        ),
        # GPT-4.1 family
        ModelSpec(
            id="gpt-4.1",
            name="GPT-4.1",
            context_window=1_047_576,
            max_output_tokens=32_768,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=2.0, output=8.0),
        ),
        ModelSpec(
            id="gpt-4.1-mini",
            name="GPT-4.1 mini",
            context_window=1_047_576,
            max_output_tokens=32_768,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.4, output=1.6),
        ),
        ModelSpec(
            id="gpt-4.1-nano",
            name="GPT-4.1 nano",
            context_window=1_047_576,
            max_output_tokens=32_768,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=0.1, output=0.4),
        ),
        # GPT-4 Turbo
        ModelSpec(
            id="gpt-4-turbo",
            name="GPT-4 Turbo",
            context_window=128_000,
            max_output_tokens=4_096,
            tool_calling=True,
            vision=True,
            cost=ModelCost(input=10.0, output=30.0),
        ),
        # GPT-4
        ModelSpec(
            id="gpt-4",
            name="GPT-4",
            context_window=8_192,
            tool_calling=True,
            cost=ModelCost(input=30.0, output=60.0),
        ),
        # GPT-3.5
        ModelSpec(
            id="gpt-3.5-turbo",
            name="GPT-3.5 Turbo",
            context_window=16_385,
            max_output_tokens=4_096,
            tool_calling=True,
            cost=ModelCost(input=0.5, output=1.5),
        ),
    ),
)
