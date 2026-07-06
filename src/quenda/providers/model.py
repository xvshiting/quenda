"""
Model specification and runtime Model for Quenda providers.

ModelSpec describes a model's capabilities, limitations, and pricing.
Model binds a ModelSpec to a Provider for actual invocation.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from quenda.kernel.tool import Tool
    from quenda.kernel.types import Message, ModelResponse, StreamChunk
    from quenda.providers.provider import Provider


@dataclass(frozen=True)
class ModelCost:
    """
    Pricing information for a model.

    All prices are per million tokens in USD.
    """

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0

    def __repr__(self) -> str:
        return (
            f"ModelCost(input=${self.input}/M, output=${self.output}/M, "
            f"cache_read=${self.cache_read}/M, cache_write=${self.cache_write}/M)"
        )


@dataclass(frozen=True)
class ModelSpec:
    """
    Specification for a model offered by a Provider.

    A ModelSpec describes:
    - Model identity (id, name)
    - Capabilities (input/output types, tool calling, streaming)
    - Limits (context window, max output)
    - Pricing
    - API overrides (if different from Provider defaults)

    ModelSpec is always bound to a Provider context.
    Model IDs are not globally unique - use (provider_id, model_id) tuple.
    """

    # Identity
    id: str
    name: str

    # Capabilities
    input: tuple[str, ...] = ("text",)
    output: tuple[str, ...] = ("text",)

    # Feature flags
    reasoning: bool = False
    tool_calling: bool = True
    streaming: bool = True
    vision: bool = False

    # Limits
    context_window: int | None = None
    max_output_tokens: int | None = None

    # Pricing
    cost: ModelCost | None = None

    # API overrides (if different from Provider defaults)
    api: str | None = None
    base_url: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)

    # Compatibility and metadata
    compat: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"ModelSpec(id={self.id!r}, name={self.name!r})"


def capabilities_of(spec: ModelSpec) -> set[str]:
    """
    Extract capabilities from a ModelSpec as a set of capability names.

    This adapter converts ModelSpec's boolean capability fields into a
    unified capability set, enabling capability-based model routing.

    The returned set always includes 'text' as all models support text.

    Args:
        spec: The ModelSpec to extract capabilities from.

    Returns:
        A set of capability names (e.g., {"text", "vision"}).

    Example:
        >>> spec = ModelSpec(id="gpt-4o", name="GPT-4o", vision=True)
        >>> capabilities_of(spec)
        {'text', 'vision'}
    """
    from quenda.kernel.types import ModelCapability

    capabilities = {ModelCapability.TEXT}

    if spec.vision:
        capabilities.add(ModelCapability.VISION)

    return capabilities


class Model:
    """
    A model bound to a Provider.

    This is the runtime representation of a model that can be invoked.
    It combines a Provider (authentication, connection) with a ModelSpec
    (capabilities, limits).

    Usage:
        model = provider.get_model("qwen-max")
        response = await model.invoke(messages, tools=tools)

    Or synchronous:
        response = model.invoke(messages, tools=tools)
    """

    def __init__(self, provider: Provider, spec: ModelSpec) -> None:
        self._provider = provider
        self._spec = spec

    @property
    def provider(self) -> Provider:
        """The provider this model belongs to."""
        return self._provider

    @property
    def spec(self) -> ModelSpec:
        """The model specification."""
        return self._spec

    @property
    def id(self) -> str:
        """Model ID."""
        return self._spec.id

    @property
    def name(self) -> str:
        """Model name."""
        return self._spec.name

    @property
    def context_window(self) -> int | None:
        """Context window size."""
        return self._spec.context_window

    @property
    def tool_calling(self) -> bool:
        """Whether model supports tool calling."""
        return self._spec.tool_calling

    def invoke(
        self,
        messages: list[Message],
        *,
        tools: list[Tool],
    ) -> ModelResponse:
        """
        Invoke the model with messages and tools.

        This is a synchronous method that delegates to the appropriate API.

        Args:
            messages: Conversation history.
            tools: Available tools for the model to call.

        Returns:
            ModelResponse with content and/or tool calls.
        """
        # Get effective configuration
        api_id = self._provider.resolve_api(self._spec)
        base_url = self._provider.resolve_base_url(self._spec)
        headers = self._provider.resolve_headers(self._spec)
        api_key = self._provider.resolve_api_key()

        # Get API implementation from registry
        api_registry = self._provider._api_registry
        if api_registry is None:
            raise RuntimeError(
                f"No API registry configured for provider '{self._provider.id}'"
            )

        api = api_registry.get(api_id)
        if api is None:
            raise ValueError(f"Unknown API protocol: {api_id}")

        # Delegate to API
        return api.invoke(
            base_url=base_url,
            api_key=api_key,
            headers=headers,
            model=self._spec.id,
            messages=messages,
            tools=tools,
            timeout=self._provider.spec.timeout,
            max_retries=self._provider.spec.max_retries or 3,
        )

    def invoke_stream(
        self,
        messages: list[Message],
        *,
        tools: list[Tool],
    ) -> Generator[StreamChunk, None, None]:
        """
        Stream model responses.

        This is a synchronous generator that yields response chunks.

        Args:
            messages: Conversation history.
            tools: Available tools for the model to call.

        Yields:
            StreamChunk objects containing partial responses.
        """
        # Get effective configuration
        api_id = self._provider.resolve_api(self._spec)
        base_url = self._provider.resolve_base_url(self._spec)
        headers = self._provider.resolve_headers(self._spec)
        api_key = self._provider.resolve_api_key()

        # Get API implementation from registry
        api_registry = self._provider._api_registry
        if api_registry is None:
            raise RuntimeError(
                f"No API registry configured for provider '{self._provider.id}'"
            )

        api = api_registry.get(api_id)
        if api is None:
            raise ValueError(f"Unknown API protocol: {api_id}")

        # Delegate to API streaming
        yield from api.invoke_stream(
            base_url=base_url,
            api_key=api_key,
            headers=headers,
            model=self._spec.id,
            messages=messages,
            tools=tools,
            timeout=self._provider.spec.timeout,
            max_retries=self._provider.spec.max_retries or 3,
        )

    def __repr__(self) -> str:
        return f"Model(provider={self._provider.id!r}, id={self.id!r})"
