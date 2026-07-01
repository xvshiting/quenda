"""
Built-in provider specifications for Kora.

These are pre-configured providers that come with the framework.
Each provider is defined in its own module for maintainability.
"""

from __future__ import annotations

from quenda.providers.builtins.agnes import AGNES_SPEC
from quenda.providers.builtins.anthropic import ANTHROPIC_SPEC
from quenda.providers.builtins.cerebras import CEREBRAS_SPEC
from quenda.providers.builtins.cohere import COHERE_SPEC
from quenda.providers.builtins.dashscope import DASHSCOPE_SPEC
from quenda.providers.builtins.deepseek import DEEPSEEK_ANTHROPIC_SPEC, DEEPSEEK_SPEC
from quenda.providers.builtins.fireworks import FIREWORKS_SPEC
from quenda.providers.builtins.google import GOOGLE_SPEC
from quenda.providers.builtins.groq import GROQ_SPEC
from quenda.providers.builtins.jdcloud import JDCLOUD_SPEC
from quenda.providers.builtins.minimax import MINIMAX_SPEC
from quenda.providers.builtins.mistral import MISTRAL_SPEC
from quenda.providers.builtins.moonshot import MOONSHOT_SPEC
from quenda.providers.builtins.nvidia import NVIDIA_SPEC
from quenda.providers.builtins.ollama import OLLAMA_SPEC
from quenda.providers.builtins.openai import OPENAI_SPEC
from quenda.providers.builtins.openrouter import OPENROUTER_SPEC
from quenda.providers.builtins.perplexity import PERPLEXITY_SPEC
from quenda.providers.builtins.siliconflow import SILICONFLOW_SPEC
from quenda.providers.builtins.stepfun import STEPFUN_SPEC
from quenda.providers.builtins.tencent import TENCENT_SPEC
from quenda.providers.builtins.together import TOGETHER_SPEC
from quenda.providers.builtins.volcengine import VOLCENGINE_SPEC
from quenda.providers.builtins.xai import XAI_SPEC
from quenda.providers.builtins.xiaomi import XIAOMI_SPEC
from quenda.providers.builtins.zhipu import ZHIPU_SPEC

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
