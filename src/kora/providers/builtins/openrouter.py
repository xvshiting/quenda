"""OpenRouter (multi-provider aggregation) provider specification."""

from __future__ import annotations

from kora.providers.model import ModelSpec
from kora.providers.provider import ProviderSpec

OPENROUTER_SPEC = ProviderSpec(
    id="openrouter",
    name="OpenRouter",
    base_url="https://openrouter.ai/api/v1",
    api="openai-completions",
    api_key="${OPENROUTER_API_KEY}",
    headers={"HTTP-Referer": "https://github.com/xvshiting/kora", "X-Title": "Kora"},
    models=(
        # Anthropic via OpenRouter
        ModelSpec(
            id="anthropic/claude-sonnet-4",
            name="Claude Sonnet 4 (via OpenRouter)",
            tool_calling=True,
        ),
        ModelSpec(
            id="anthropic/claude-3.7-sonnet",
            name="Claude 3.7 Sonnet (via OpenRouter)",
            tool_calling=True,
        ),
        ModelSpec(
            id="anthropic/claude-3.5-sonnet",
            name="Claude 3.5 Sonnet (via OpenRouter)",
            tool_calling=True,
        ),
        # OpenAI via OpenRouter
        ModelSpec(
            id="openai/gpt-4o",
            name="GPT-4o (via OpenRouter)",
            tool_calling=True,
        ),
        ModelSpec(
            id="openai/o3-mini",
            name="o3-mini (via OpenRouter)",
            tool_calling=True,
            reasoning=True,
        ),
        # Google via OpenRouter
        ModelSpec(
            id="google/gemini-2.5-pro-preview",
            name="Gemini 2.5 Pro (via OpenRouter)",
            tool_calling=True,
        ),
        ModelSpec(
            id="google/gemini-2.0-flash-001",
            name="Gemini 2.0 Flash (via OpenRouter)",
            tool_calling=True,
        ),
        # Meta via OpenRouter
        ModelSpec(
            id="meta-llama/llama-3.3-70b-instruct",
            name="Llama 3.3 70B (via OpenRouter)",
            tool_calling=True,
        ),
        ModelSpec(
            id="meta-llama/llama-3.2-90b-vision-instruct",
            name="Llama 3.2 90B Vision (via OpenRouter)",
            tool_calling=True,
            vision=True,
        ),
        # DeepSeek via OpenRouter
        ModelSpec(
            id="deepseek/deepseek-r1",
            name="DeepSeek R1 (via OpenRouter)",
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="deepseek/deepseek-chat-v3-0324",
            name="DeepSeek Chat V3 (via OpenRouter)",
            tool_calling=True,
        ),
        # Qwen via OpenRouter
        ModelSpec(
            id="qwen/qwen3-235b-a22b",
            name="Qwen3 235B (via OpenRouter)",
            tool_calling=True,
        ),
    ),
)
