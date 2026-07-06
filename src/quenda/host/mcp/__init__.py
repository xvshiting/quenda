"""
MCP integration for Quenda.

This module provides Model Context Protocol (MCP) support for Quenda agents.
MCP allows agents to use tools and resources from external MCP servers.

Key components:
- MCPConfig: Configuration for MCP server connections
- MCPClient: Wrapper for a single MCP server connection
- MCPClientManager: Manages multiple MCP server connections
- MCPToolAdapter: Adapts MCP tools to Quenda Tool interface

Usage:
    from quenda.host.mcp import MCPConfig, MCPClientManager

    # Parse config
    config = MCPConfig.from_dict({
        "servers": {
            "calculator": {
                "transport": "stdio",
                "command": "python",
                "args": ["servers/calculator.py"]
            }
        }
    })

    # Connect and use
    manager = MCPClientManager()
    await manager.connect_from_config(config)

    result = await manager.call_tool("calculator.add", {"a": 1, "b": 2})
    print(result)  # 3

    await manager.close()
"""

from quenda.host.mcp.config import (
    MCPConfig,
    MCPServerConfig,
    StdioMCPConfig,
    HTTPMCPConfig,
)
from quenda.host.mcp.client import (
    MCPClient,
    MCPToolSpec,
    MCPResourceSpec,
)
from quenda.host.mcp.manager import MCPClientManager
from quenda.host.mcp.adapter import (
    MCPToolAdapter,
    MCPToolRegistry,
)
from quenda.host.mcp.errors import (
    MCPError,
    MCPConnectionError,
    MCPToolError,
    MCPResourceError,
    MCPNotConnectedError,
    MCPConfigError,
)

__all__ = [
    # Configuration
    "MCPConfig",
    "MCPServerConfig",
    "StdioMCPConfig",
    "HTTPMCPConfig",
    # Client
    "MCPClient",
    "MCPToolSpec",
    "MCPResourceSpec",
    # Manager
    "MCPClientManager",
    # Adapter
    "MCPToolAdapter",
    "MCPToolRegistry",
    # Errors
    "MCPError",
    "MCPConnectionError",
    "MCPToolError",
    "MCPResourceError",
    "MCPNotConnectedError",
    "MCPConfigError",
]
