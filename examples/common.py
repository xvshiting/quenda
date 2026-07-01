"""
Common utilities for Kora examples.

This module provides shared code used across multiple demos.
Uses the new Provider-centric architecture.
"""

import os

from quenda.kernel import Message
from quenda.providers import get_provider_registry, ProviderSpec, ModelSpec
from quenda.providers.model import Model
from quenda.tools import tool


# === Common Tools ===

@tool
def echo(message: str) -> str:
    """Echo back a message."""
    return f"Echo: {message}"


@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression. Supports +, -, *, /, **."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def read_file(path: str) -> str:
    """Read a file from disk."""
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


# === Model Provider Helper ===

def get_model(provider_id: str, model_id: str) -> Model:
    """
    Get a model from the provider registry.

    Args:
        provider_id: Provider ID (e.g., "deepseek", "openai", "anthropic")
        model_id: Model ID (e.g., "deepseek-chat", "gpt-4o")

    Returns:
        A Model instance ready to use with Agent.

    Example:
        model = get_model("deepseek", "deepseek-chat")
        agent = Agent(name="assistant", model=model, tools=[...])
    """
    registry = get_provider_registry()
    return registry.get_model(provider_id, model_id)


def get_deepseek_model(model_id: str = "deepseek-chat") -> Model:
    """
    Get a DeepSeek model.

    Requires DEEPSEEK_API_KEY environment variable.
    """
    return get_model("deepseek", model_id)


def get_deepseek_anthropic_model(model_id: str = "deepseek-v4-flash") -> Model:
    """
    Get a DeepSeek model via Anthropic API.

    Requires DEEPSEEK_API_KEY environment variable.
    """
    return get_model("deepseek-anthropic", model_id)


def get_openai_model(model_id: str = "gpt-4o") -> Model:
    """
    Get an OpenAI model.

    Requires OPENAI_API_KEY environment variable.
    """
    return get_model("openai", model_id)


def get_anthropic_model(model_id: str = "claude-3-5-sonnet-20241022") -> Model:
    """
    Get an Anthropic Claude model.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    return get_model("anthropic", model_id)


def get_moonshot_model(model_id: str = "moonshot-v1-8k") -> Model:
    """
    Get a Moonshot (Kimi) model.

    Requires MOONSHOT_API_KEY environment variable.
    """
    return get_model("moonshot", model_id)


def get_dashscope_model(model_id: str = "qwen-max") -> Model:
    """
    Get a DashScope (Qwen) model.

    Requires DASHSCOPE_API_KEY environment variable.
    """
    return get_model("dashscope", model_id)


# === Legacy GLMModel (for backward compatibility) ===
# This is now a thin wrapper around the provider system

class GLMModel:
    """
    GLM model provider using JD Cloud API.

    This is a convenience class that wraps the provider system.
    Requires KORA_GLM_API_KEY environment variable.

    Configuration:
        base_url: https://modelservice.jdcloud.com/coding/openai/v1
        model: GLM-5

    Note: This class is kept for backward compatibility.
    Prefer using get_model("jdcloud", "glm-5") directly.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "glm-5",
    ) -> None:
        # Get API key from environment
        env_key = os.environ.get("KORA_GLM_API_KEY")
        if api_key:
            # Set temporarily for auth resolver
            os.environ["JDCLOUD_API_KEY"] = api_key
        elif env_key:
            os.environ["JDCLOUD_API_KEY"] = env_key

        self._model = get_model("jdcloud", model)

    def invoke(self, messages: list[Message], *, tools) -> "ModelResponse":
        """Invoke the model with messages and tools."""
        return self._model.invoke(messages, tools=tools)

    def invoke_stream(self, messages: list[Message], *, tools):
        """Stream model responses."""
        yield from self._model.invoke_stream(messages, tools=tools)


# Import for type hint
from quenda.kernel import ModelResponse
