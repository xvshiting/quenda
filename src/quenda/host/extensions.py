"""Host-owned seams for agent-local context extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from quenda.host.identity import User
from quenda.host.instructions import InstructionSource


@dataclass(frozen=True)
class AgentExtensionContext:
    """Stable Host context available while loading agent-local extensions."""

    agent_name: str
    agent_package_path: Path
    user: User
    user_agent_path: Path
    workspace_path: Path
    workspace_id: str


@dataclass(frozen=True)
class ContextProviderRequest:
    """Per-Run context passed to registered context providers."""

    extension: AgentExtensionContext
    session_id: str = ""


@runtime_checkable
class ContextProvider(Protocol):
    """Provide additional textual context for one Run."""

    def provide(self, request: ContextProviderRequest) -> list[InstructionSource]:
        """Return fresh instruction sources for the current Run."""
        ...


@runtime_checkable
class AgentInitializer(Protocol):
    """Perform idempotent setup for one resolved agent binding."""

    def initialize(self, context: AgentExtensionContext) -> None:
        """Create or validate Agent-owned state without overwriting user data."""
        ...


@dataclass
class AgentInitializerRegistry:
    """Ordered registry for Agent setup extensions."""

    initializers: list[AgentInitializer] = field(default_factory=list)

    def register(self, initializer: AgentInitializer) -> None:
        if not isinstance(initializer, AgentInitializer):
            raise TypeError("Agent initializer must implement initialize(context)")
        self.initializers.append(initializer)

    def initialize(self, context: AgentExtensionContext) -> None:
        for initializer in self.initializers:
            initializer.initialize(context)


@dataclass
class ContextProviderRegistry:
    """Ordered registry for agent-local context providers."""

    providers: list[ContextProvider] = field(default_factory=list)

    def register(self, provider: ContextProvider) -> None:
        if not isinstance(provider, ContextProvider):
            raise TypeError("Context provider must implement provide(request)")
        self.providers.append(provider)

    def provide(self, request: ContextProviderRequest) -> list[InstructionSource]:
        sources: list[InstructionSource] = []
        for provider in self.providers:
            provided = provider.provide(request)
            if not isinstance(provided, list) or not all(
                isinstance(source, InstructionSource) for source in provided
            ):
                raise TypeError(
                    "Context provider must return list[InstructionSource]"
                )
            sources.extend(provided)
        return sources


__all__ = [
    "AgentExtensionContext",
    "AgentInitializer",
    "AgentInitializerRegistry",
    "ContextProvider",
    "ContextProviderRegistry",
    "ContextProviderRequest",
]
