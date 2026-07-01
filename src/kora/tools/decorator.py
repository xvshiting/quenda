"""
Tool decorator for easy tool definition.

The @tool decorator allows defining tools with minimal boilerplate:
- Automatically generates JSON Schema from type hints
- Extracts description from docstring
- Wraps function in Tool protocol
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from kora.kernel.types import ToolResult


@dataclass
class FunctionTool:
    """
    A Tool implementation that wraps a Python function.

    This is created by the @tool decorator.
    """

    _name: str
    _description: str
    _parameters_schema: dict[str, object]
    _func: Callable[..., Any]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, object]:
        return self._parameters_schema

    def execute(self, **kwargs: object) -> ToolResult:
        """Execute the wrapped function."""
        # Framework reserves _summary for display, remove before calling
        kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}

        try:
            result = self._func(**kwargs)

            # If function already returns ToolResult, use it
            if isinstance(result, ToolResult):
                return result

            # Otherwise, convert to string
            # Note: call_id will be set by Kernel
            return ToolResult(
                call_id="",
                name=self._name,
                content=str(result) if result is not None else "",
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                name=self._name,
                content=f"Error: {e}",
                is_error=True,
            )


def _python_type_to_json_schema(python_type: Any) -> dict[str, str]:
    """Convert Python type hint to JSON Schema type."""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Handle Optional types
    origin = getattr(python_type, "__origin__", None)
    if origin is type(None) | type:  # Union type (Optional)
        args = getattr(python_type, "__args__", ())
        if args:
            # Get the non-None type
            for arg in args:
                if arg is not type(None):
                    return _python_type_to_json_schema(arg)

    if python_type in type_map:
        return {"type": type_map[python_type]}

    return {"type": "string"}  # Default to string


def _generate_schema(func: Callable[..., Any]) -> dict[str, object]:
    """Generate JSON Schema from function signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    properties: dict[str, object] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        # Get type hint
        param_type = hints.get(param_name, str)

        # Get description from docstring param (if available)
        description = f"Parameter {param_name}"

        # Build property schema
        prop_schema: dict[str, object] = {
            "type": _python_type_to_json_schema(param_type)["type"],
            "description": description,
        }

        # Handle default values
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop_schema["default"] = param.default

        properties[param_name] = prop_schema

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(func: Callable[..., Any] | None = None, *, name: str | None = None) -> Any:
    """
    Decorator to create a Tool from a function.

    Usage:
        @tool
        def read_file(path: str) -> str:
            '''Read a file from disk.'''
            ...

        @tool(name="custom_name")
        def my_tool(x: int, y: int = 10) -> str:
            '''Add two numbers.'''
            ...

    The decorator:
    - Uses function name as tool name (or custom name if provided)
    - Extracts description from docstring
    - Generates JSON Schema from type hints
    - Wraps function in Tool protocol

    Note: Framework automatically adds a _summary parameter for display purposes.
    The wrapped function should not define _summary - it will be stripped before execution.

    Args:
        func: The function to wrap (when used without parentheses).
        name: Optional custom name for the tool.

    Returns:
        A FunctionTool instance.
    """

    def decorator(f: Callable[..., Any]) -> FunctionTool:
        # Get tool name
        tool_name = name or f.__name__

        # Get description from docstring
        doc = f.__doc__ or f"Tool: {tool_name}"
        description = doc.strip().split("\n")[0]  # First line only

        # Generate schema
        schema = _generate_schema(f)

        return FunctionTool(
            _name=tool_name,
            _description=description,
            _parameters_schema=schema,
            _func=f,
        )

    # Handle @tool and @tool(...) syntax
    if func is not None:
        return decorator(func)
    return decorator
