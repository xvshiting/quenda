"""Cohere provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelCost, ModelSpec
from quenda.providers.provider import ProviderSpec

COHERE_SPEC = ProviderSpec(
    id="cohere",
    name="Cohere",
    base_url="https://api.cohere.ai/v2",
    api="openai-completions",
    api_key="${COHERE_API_KEY}",
    models=(
        # Command A family
        ModelSpec(
            id="command-a-plus-05-2026",
            name="Command A Plus",
            context_window=128_000,
            max_output_tokens=64_000,
            tool_calling=True,
            cost=ModelCost(input=2.5, output=10.0),
        ),
        ModelSpec(
            id="command-a",
            name="Command A",
            context_window=256_000,
            max_output_tokens=8_192,
            tool_calling=True,
        ),
        # North family (code)
        ModelSpec(
            id="north-mini-code-1-0",
            name="North Mini Code",
            context_window=256_000,
            max_output_tokens=64_000,
            tool_calling=True,
        ),
        # Command R family
        ModelSpec(
            id="command-r7b-12-2024",
            name="Command R7B",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.0375, output=0.1875),
        ),
        ModelSpec(
            id="command-r-08-2024",
            name="Command R",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=0.15, output=0.6),
        ),
        ModelSpec(
            id="command-r-plus-08-2024",
            name="Command R+",
            context_window=131_072,
            tool_calling=True,
            cost=ModelCost(input=2.5, output=10.0),
        ),
        # Command family
        ModelSpec(
            id="command",
            name="Command",
            context_window=4_096,
            tool_calling=True,
            cost=ModelCost(input=1.0, output=2.0),
        ),
        ModelSpec(
            id="command-light",
            name="Command Light",
            context_window=4_096,
            tool_calling=True,
            cost=ModelCost(input=0.3, output=0.6),
        ),
        ModelSpec(
            id="command-nightly",
            name="Command Nightly",
            context_window=4_096,
            tool_calling=True,
        ),
        ModelSpec(
            id="command-light-nightly",
            name="Command Light Nightly",
            context_window=4_096,
            tool_calling=True,
        ),
        # Embedding models
        ModelSpec(
            id="embed-v4.0",
            name="Embed v4.0",
            context_window=512,
            cost=ModelCost(input=0.0001, output=0.0),
        ),
        ModelSpec(
            id="embed-english-v3.0",
            name="Embed English v3.0",
            context_window=512,
            cost=ModelCost(input=0.0001, output=0.0),
        ),
        ModelSpec(
            id="embed-multilingual-v3.0",
            name="Embed Multilingual v3.0",
            context_window=512,
            cost=ModelCost(input=0.0001, output=0.0),
        ),
        # Rerank models
        ModelSpec(
            id="rerank-v3.5",
            name="Rerank v3.5",
            context_window=4_096,
        ),
        ModelSpec(
            id="rerank-english-v3.0",
            name="Rerank English v3.0",
            context_window=4_096,
        ),
    ),
)
