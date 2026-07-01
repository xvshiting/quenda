"""
Model Provider Protocol for Kora Kernel.

Defines the interface that all model providers must implement.
This is a synchronous interface - async handling is done at the Runtime layer.
"""

from typing import Protocol, runtime_checkable

from quenda.kernel.tool import Tool
from quenda.kernel.types import Message, ModelResponse


@runtime_checkable
class Model(Protocol):
    """
    Protocol for model providers.

    All model providers (Anthropic, OpenAI, local models, etc.) must implement
    this interface. The Kernel calls this interface synchronously.

    The Model is responsible for:
    - Converting messages to provider-specific format
    - Making the API call
    - Converting the response to ModelResponse
    """

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        """
        Invoke the model with messages and available tools.

        Args:
            messages: The conversation history as a list of Message objects.
            tools: The tools available for the model to call.

        Returns:
            A standardized ModelResponse containing content and/or tool calls.

        Note:
            This is a synchronous method. The Runtime layer wraps it with
            run_in_executor for async compatibility.
        """
        ...


__all__ = ["Model"]
