"""
MCP errors - Unified error handling for MCP integration.

Converts MCP SDK exceptions to Quenda-specific exceptions,
providing a consistent error interface across the framework.
"""

from __future__ import annotations


class MCPError(Exception):
    """Base exception for MCP-related errors."""

    pass


class MCPConnectionError(MCPError):
    """Failed to connect to an MCP server."""

    def __init__(self, server_id: str, message: str) -> None:
        self.server_id = server_id
        super().__init__(f"MCP server '{server_id}': {message}")


class MCPToolError(MCPError):
    """MCP tool execution failed."""

    def __init__(self, server_id: str, tool_name: str, message: str) -> None:
        self.server_id = server_id
        self.tool_name = tool_name
        super().__init__(f"MCP tool '{server_id}.{tool_name}': {message}")


class MCPResourceError(MCPError):
    """Failed to read an MCP resource."""

    def __init__(self, server_id: str, uri: str, message: str) -> None:
        self.server_id = server_id
        self.uri = uri
        super().__init__(f"MCP resource '{uri}' on server '{server_id}': {message}")


class MCPNotConnectedError(MCPError):
    """Attempted to use an MCP client that is not connected."""

    def __init__(self, server_id: str) -> None:
        self.server_id = server_id
        super().__init__(f"MCP server '{server_id}' is not connected")


class MCPConfigError(MCPError):
    """Invalid MCP server configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(f"MCP configuration error: {message}")


def wrap_mcp_exception(e: Exception, server_id: str, tool_name: str | None = None) -> MCPError:
    """
    Wrap an MCP SDK exception into a Quenda MCPError.

    Args:
        e: The original exception.
        server_id: The MCP server ID.
        tool_name: Optional tool name if the error occurred during tool execution.

    Returns:
        An appropriate MCPError subclass.
    """
    # Check for specific MCP SDK exception types
    error_message = str(e)

    if "not connected" in error_message.lower() or "not initialized" in error_message.lower():
        return MCPNotConnectedError(server_id)

    if tool_name:
        return MCPToolError(server_id, tool_name, error_message)

    return MCPConnectionError(server_id, error_message)


__all__ = [
    "MCPError",
    "MCPConnectionError",
    "MCPToolError",
    "MCPResourceError",
    "MCPNotConnectedError",
    "MCPConfigError",
    "wrap_mcp_exception",
]
