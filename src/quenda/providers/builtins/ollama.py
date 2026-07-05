"""Ollama (local models) provider specification."""

from __future__ import annotations

from quenda.providers.model import ModelSpec
from quenda.providers.provider import ProviderSpec

OLLAMA_SPEC = ProviderSpec(
    id="ollama",
    name="Ollama",
    base_url="http://localhost:11434/v1",
    api="openai-completions",
    api_key="ollama",  # Ollama doesn't require real API keys
    models=(
        # Llama 3.x family
        ModelSpec(
            id="llama3.3:70b",
            name="Llama 3.3 70B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3.2:3b",
            name="Llama 3.2 3B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3.2:1b",
            name="Llama 3.2 1B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3.1:8b",
            name="Llama 3.1 8B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3.1:70b",
            name="Llama 3.1 70B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3:8b",
            name="Llama 3 8B",
            tool_calling=True,
        ),
        ModelSpec(
            id="llama3:70b",
            name="Llama 3 70B",
            tool_calling=True,
        ),
        # Qwen family
        ModelSpec(
            id="qwen3.6:35b-mlx",
            name="qwen3.6:35b-mlx",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen3:14b",
            name="Qwen3 14B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5:72b",
            name="Qwen2.5 72B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5:32b",
            name="Qwen2.5 32B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5:14b",
            name="Qwen2.5 14B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5:7b",
            name="Qwen2.5 7B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2.5-coder:32b",
            name="Qwen2.5 Coder 32B",
            tool_calling=True,
        ),
        ModelSpec(
            id="qwen2:7b",
            name="Qwen2 7B",
            tool_calling=True,
        ),
        # Mistral family
        ModelSpec(
            id="mistral:7b",
            name="Mistral 7B",
            tool_calling=True,
        ),
        ModelSpec(
            id="mistral-nemo:12b",
            name="Mistral NeMo 12B",
            tool_calling=True,
        ),
        ModelSpec(
            id="mistral-small:24b",
            name="Mistral Small 24B",
            tool_calling=True,
        ),
        # DeepSeek family
        ModelSpec(
            id="deepseek-r1:14b",
            name="DeepSeek R1 14B",
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="deepseek-r1:7b",
            name="DeepSeek R1 7B",
            tool_calling=True,
            reasoning=True,
        ),
        ModelSpec(
            id="deepseek-v2:16b",
            name="DeepSeek V2 16B",
            tool_calling=True,
        ),
        ModelSpec(
            id="deepseek-coder-v2:16b",
            name="DeepSeek Coder V2 16B",
            tool_calling=True,
        ),
        # Other popular models
        ModelSpec(
            id="gemma3:12b",
            name="Gemma 3 12B",
            tool_calling=True,
        ),
        ModelSpec(
            id="gemma2:27b",
            name="Gemma 2 27B",
            tool_calling=True,
        ),
        ModelSpec(
            id="phi4:14b",
            name="Phi-4 14B",
            tool_calling=True,
        ),
        ModelSpec(
            id="codeqwen:7b",
            name="CodeQwen 7B",
            tool_calling=True,
        ),
        ModelSpec(
            id="starcoder2:7b",
            name="StarCoder2 7B",
            tool_calling=True,
        ),
    ),
)
