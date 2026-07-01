"""
Tool registry for Kora Host layer.

Provides a Host-owned tool registration and resolution mechanism for:
- built-in named tools
- built-in bundles
- agent-local custom tools
- future skill-provided tools

This is a Host concern, not Runtime or Kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from quenda.kernel.tool import Tool


@dataclass
class NamedToolSpec:
    """
    Represents one resolved tool candidate before instantiation.

    Attributes:
        name: Unique tool name.
        source: Where the tool came from (builtin, agent_local, skill).
        tool: The Tool instance (if already instantiated).
        factory: Optional factory function to create the tool with context.
    """

    name: str
    source: str  # "builtin", "agent_local", "skill"
    tool: Tool | None = None
    factory: Callable[[], Tool] | Callable[[Path], Tool] | None = None

    def __post_init__(self) -> None:
        """Validate that either tool or factory is provided."""
        if self.tool is None and self.factory is None:
            raise ValueError(f"NamedToolSpec '{self.name}' needs tool or factory")


@dataclass
class LoadedToolCatalog:
    """
    Catalog of all loaded tools from various sources.

    Used during Host resolution to build the final tool set.

    Attributes:
        tools: Dictionary mapping tool name to NamedToolSpec.
    """

    tools: dict[str, NamedToolSpec] = field(default_factory=dict)

    def add(self, spec: NamedToolSpec) -> None:
        """Add a tool spec to the catalog."""
        self.tools[spec.name] = spec

    def get(self, name: str) -> NamedToolSpec | None:
        """Get a tool spec by name."""
        return self.tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool exists in the catalog."""
        return name in self.tools

    def all_names(self) -> list[str]:
        """Get all tool names in the catalog."""
        return list(self.tools.keys())

    def all_specs(self) -> list[NamedToolSpec]:
        """Get all tool specs in the catalog."""
        return list(self.tools.values())


class ToolRegistryBuilder:
    """
    Builder for constructing a LoadedToolCatalog.

    Used during Host loading to register tools from various sources:
    - built-in named tools
    - built-in bundles
    - agent-local custom tools

    Enforces name uniqueness within a single loading session.
    """

    def __init__(self) -> None:
        self._catalog = LoadedToolCatalog()

    def register(
        self,
        tool: Tool,
        *,
        source: str,
    ) -> None:
        """
        Register a tool instance.

        Args:
            tool: The Tool instance to register.
            source: Where the tool came from.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        name = tool.name

        if self._catalog.has(name):
            existing = self._catalog.get(name)
            raise ValueError(
                f"Duplicate tool name '{name}': "
                f"already registered from {existing.source}, "
                f"cannot register from {source}"
            )

        self._catalog.add(NamedToolSpec(
            name=name,
            source=source,
            tool=tool,
        ))

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Tool] | Callable[[Path], Tool],
        *,
        source: str,
    ) -> None:
        """
        Register a tool factory.

        Factories are useful for tools that need runtime context
        like workspace path.

        Args:
            name: The tool name.
            factory: Factory function that creates the tool.
            source: Where the tool came from.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if self._catalog.has(name):
            existing = self._catalog.get(name)
            raise ValueError(
                f"Duplicate tool name '{name}': "
                f"already registered from {existing.source}, "
                f"cannot register from {source}"
            )

        self._catalog.add(NamedToolSpec(
            name=name,
            source=source,
            factory=factory,
        ))

    def build(self) -> LoadedToolCatalog:
        """
        Build and return the final catalog.

        Returns:
            The LoadedToolCatalog with all registered tools.
        """
        return self._catalog


__all__ = [
    "NamedToolSpec",
    "LoadedToolCatalog",
    "ToolRegistryBuilder",
]
