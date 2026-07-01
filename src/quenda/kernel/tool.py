"""
Tool Protocol for Quenda Kernel.

Defines the interface that all tools must implement.
Tools are the primary way for agents to interact with the world.
"""

from typing import Protocol, runtime_checkable

from quenda.kernel.types import ToolResult


@runtime_checkable
class Tool(Protocol):
    """
    Protocol for tools.

    Tools can be defined in two ways:
    1. Implementing this Protocol directly (for complex tools)
    2. Using the @tool decorator (for simple function-based tools)

    The Kernel executes tools synchronously via the execute() method.
    """

    @property
    def name(self) -> str:
        """The unique name of the tool."""
        ...

    @property
    def description(self) -> str:
        """A description of what the tool does, shown to the model."""
        ...

    @property
    def parameters(self) -> dict[str, object]:
        """
        JSON Schema for the tool's parameters.

        Example:
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            }
        """
        ...

    def execute(self, **kwargs: object) -> ToolResult:
        """
        Execute the tool with the given parameters.

        Args:
            **kwargs: The parameters matching the JSON Schema.

        Returns:
            A ToolResult containing the output or error message.
            Note: The call_id may be empty; the Kernel will set it.
        """
        ...


# Reserved parameter names for framework use
RESERVED_PARAMS = {"_summary"}


class ToolRegistry:
    """
    Registry for tools.

    Tools are registered by name and can be looked up during execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name, or None if not found."""
        return self._tools.get(name)

    def all_tools(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __len__(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)
