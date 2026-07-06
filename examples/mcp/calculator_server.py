#!/usr/bin/env python3
"""
Simple MCP server example for testing.

Provides basic 'add' and 'multiply' tools.
"""

from mcp.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("simple-calculator")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        The product of a and b
    """
    return a * b


if __name__ == "__main__":
    mcp.run()
