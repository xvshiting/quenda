"""
Built-in provider specifications for Kora.

These are pre-configured providers that come with the framework.
Each provider is defined in its own module for maintainability.
"""

from __future__ import annotations

from kora.providers.builtins.agnes import AGNES_SPEC
from kora.providers.builtins.anthropic import ANTHROPIC_SPEC
from kora.providers.builtins.cerebras import CEREBRAS_SPEC
from kora.providers.builtins.cohere import COHERE_SPEC
from kora.providers.builtins.dashscope import DASHSCOPE_SPEC
from kora.providers.builtins.deepseek import DEEPSEEK_ANTHROPIC_SPEC, DEEPSEEK_SPEC
from kora.providers.builtins.fireworks import FIREWORKS_SPEC
from kora.providers.builtins.google import GOOGLE_SPEC
from kora.providers.builtins.groq import GROQ_SPEC
from kora.providers.builtins.jdcloud import JDCLOUD_SPEC
from kora.providers.builtins.minimax import MINIMAX_SPEC
from kora.providers.builtins.mistral import MISTRAL_SPEC
from kora.providers.builtins.moonshot import MOONSHOT_SPEC
from kora.providers.builtins.nvidia import NVIDIA_SPEC
from kora.providers.builtins.ollama import OLLAMA_SPEC
from kora.providers.builtins.openai import OPENAI_SPEC
from kora.providers.builtins.openrouter import OPENROUTER_SPEC
from kora.providers.builtins.perplexity import PERPLEXITY_SPEC
from kora.providers.builtins.siliconflow import SILICONFLOW_SPEC
from kora.providers.builtins.stepfun import STEPFUN_SPEC
from kora.providers.builtins.tencent import TENCENT_SPEC
from kora.providers.builtins.together import TOGETHER_SPEC
from kora.providers.builtins.volcengine import VOLCENGINE_SPEC
from kora.providers.builtins.xai import XAI_SPEC
from kora.providers.builtins.xiaomi import XIAOMI_SPEC
from kora.providers.builtins.zhipu import ZHIPU_SPEC

__all__ = [
    "AGNES_SPEC",
    "ANTHROPIC_SPEC",
    "CEREBRAS_SPEC",
    "COHERE_SPEC",
    "DASHSCOPE_SPEC",
    "DEEPSEEK_ANTHROPIC_SPEC",
    "DEEPSEEK_SPEC",
    "FIREWORKS_SPEC",
    "GOOGLE_SPEC",
    "GROQ_SPEC",
    "JDCLOUD_SPEC",
    "MINIMAX_SPEC",
    "MISTRAL_SPEC",
    "MOONSHOT_SPEC",
    "NVIDIA_SPEC",
    "OLLAMA_SPEC",
    "OPENAI_SPEC",
    "OPENROUTER_SPEC",
    "PERPLEXITY_SPEC",
    "SILICONFLOW_SPEC",
    "STEPFUN_SPEC",
    "TENCENT_SPEC",
    "TOGETHER_SPEC",
    "VOLCENGINE_SPEC",
    "XAI_SPEC",
    "XIAOMI_SPEC",
    "ZHIPU_SPEC",
]
