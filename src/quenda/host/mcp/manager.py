"""
MCP manager - Manage multiple MCP server connections.

Provides a central point for:
- Managing connections to multiple MCP servers
- Unified tool calling with qualified names (server_id.tool_name)
- Aggregating tools from all connected servers
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from quenda.host.mcp.client import MCPClient, MCPToolSpec, MCPResourceSpec
from quenda.host.mcp.config import MCPConfig
from quenda.host.mcp.errors import MCPError, MCPNotConnectedError

logger = logging.getLogger(__name__)


@dataclass
class MCPClientManager:
    """
    Manages multiple MCP server connections.

    Usage:
        manager = MCPClientManager()
        await manager.connect_from_config(mcp_config)

        # Get all tools from all servers
        tools = await manager.list_all_tools()

        # Call a tool with qualified name
        result = await manager.call_tool("calculator.add", {"a": 1, "b": 2})

        # Close all connections
        await manager.close()
    """

    _clients: dict[str, MCPClient] = field(default_factory=dict, init=False)
    _tools_by_qualified_name: dict[str, tuple[str, MCPToolSpec]] = field(
        default_factory=dict, init=False
    )

    @property
    def server_ids(self) -> list[str]:
        """Get list of connected server IDs."""
        return list(self._clients.keys())

    @property
    def is_connected(self) -> bool:
        """Check if any servers are connected."""
        return bool(self._clients)

    async def connect_from_config(self, config: MCPConfig) -> list[str]:
        """
        Connect to all servers defined in the configuration.

        Args:
            config: The MCP configuration.

        Returns:
            List of successfully connected server IDs.

        Raises:
            MCPError: If any connection fails.
        """
        connected: list[str] = []
        errors: list[tuple[str, Exception]] = []

        for server_id, server_config in config.servers.items():
            client = MCPClient(server_id=server_id, config=server_config)
            try:
                await client.connect()
                self._clients[server_id] = client
                connected.append(server_id)
                logger.info(f"Connected to MCP server: {server_id}")
            except MCPError as e:
                errors.append((server_id, e))
                logger.error(f"Failed to connect to MCP server '{server_id}': {e}")

        if errors:
            # Clean up successful connections
            await self.close()
            raise MCPError(
                f"Failed to connect to {len(errors)} MCP server(s): "
                + ", ".join(f"{sid}: {e}" for sid, e in errors)
            )

        # Build tool index
        await self._rebuild_tool_index()

        return connected

    async def add_client(self, client: MCPClient) -> None:
        """
        Add a pre-configured client and connect it.

        Args:
            client: The MCPClient to add.

        Raises:
            ValueError: If a client with the same server_id already exists.
            MCPError: If connection fails.
        """
        if client.server_id in self._clients:
            raise ValueError(f"MCP server '{client.server_id}' already exists")

        await client.connect()
        self._clients[client.server_id] = client

        # Update tool index
        tools = await client.list_tools()
        for tool in tools:
            qualified_name = f"{client.server_id}.{tool.name}"
            self._tools_by_qualified_name[qualified_name] = (client.server_id, tool)

    async def list_all_tools(self) -> dict[str, list[MCPToolSpec]]:
        """
        List tools from all connected servers.

        Returns:
            Dictionary mapping server_id to list of tool specs.
        """
        result: dict[str, list[MCPToolSpec]] = {}

        for server_id, client in self._clients.items():
            try:
                tools = await client.list_tools()
                result[server_id] = tools
            except MCPError as e:
                logger.warning(f"Failed to list tools from '{server_id}': {e}")
                result[server_id] = []

        return result

    async def list_all_tools_flat(self) -> list[tuple[str, MCPToolSpec]]:
        """
        List all tools with their server IDs.

        Returns:
            List of (server_id, tool_spec) tuples.
        """
        result: list[tuple[str, MCPToolSpec]] = []

        for server_id, client in self._clients.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    result.append((server_id, tool))
            except MCPError as e:
                logger.warning(f"Failed to list tools from '{server_id}': {e}")

        return result

    def get_qualified_tool_names(self) -> list[str]:
        """
        Get all qualified tool names (server_id.tool_name).

        Returns:
            List of qualified tool names.
        """
        return list(self._tools_by_qualified_name.keys())

    def parse_qualified_name(self, qualified_name: str) -> tuple[str, str]:
        """
        Parse a qualified name into server_id and tool_name.

        Args:
            qualified_name: Name in format "server_id.tool_name".

        Returns:
            Tuple of (server_id, tool_name).

        Raises:
            ValueError: If the name format is invalid.
        """
        parts = qualified_name.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid qualified name '{qualified_name}'. "
                f"Expected format: 'server_id.tool_name'"
            )
        return parts[0], parts[1]

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool by its qualified name.

        Args:
            qualified_name: Name in format "server_id.tool_name".
            arguments: Arguments to pass to the tool.

        Returns:
            The tool result.

        Raises:
            ValueError: If the qualified name format is invalid.
            MCPNotConnectedError: If the server is not connected.
            MCPError: If tool execution fails.
        """
        server_id, tool_name = self.parse_qualified_name(qualified_name)

        client = self._clients.get(server_id)
        if client is None:
            raise MCPNotConnectedError(server_id)

        return await client.call_tool(tool_name, arguments)

    async def call_tool_explicit(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """
        Call a tool with explicit server and tool names.

        Args:
            server_id: The server ID.
            tool_name: The tool name.
            arguments: Arguments to pass to the tool.

        Returns:
            The tool result.

        Raises:
            MCPNotConnectedError: If the server is not connected.
            MCPError: If tool execution fails.
        """
        client = self._clients.get(server_id)
        if client is None:
            raise MCPNotConnectedError(server_id)

        return await client.call_tool(tool_name, arguments)

    async def list_all_resources(self) -> dict[str, list[MCPResourceSpec]]:
        """
        List resources from all connected servers.

        Returns:
            Dictionary mapping server_id to list of resource specs.
        """
        result: dict[str, list[MCPResourceSpec]] = {}

        for server_id, client in self._clients.items():
            try:
                resources = await client.list_resources()
                result[server_id] = resources
            except MCPError as e:
                logger.warning(f"Failed to list resources from '{server_id}': {e}")
                result[server_id] = []

        return result

    async def read_resource(self, server_id: str, uri: str) -> Any:
        """
        Read a resource from a specific server.

        Args:
            server_id: The server ID.
            uri: The resource URI.

        Returns:
            The resource content.

        Raises:
            MCPNotConnectedError: If the server is not connected.
            MCPError: If reading fails.
        """
        client = self._clients.get(server_id)
        if client is None:
            raise MCPNotConnectedError(server_id)

        return await client.read_resource(uri)

    async def close(self) -> None:
        """Close all connections."""
        # Close in reverse order
        for server_id in reversed(list(self._clients.keys())):
            client = self._clients[server_id]
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP server '{server_id}': {e}")

        self._clients.clear()
        self._tools_by_qualified_name.clear()

    async def _rebuild_tool_index(self) -> None:
        """Rebuild the tool index from all connected clients."""
        self._tools_by_qualified_name.clear()

        for server_id, client in self._clients.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    qualified_name = f"{server_id}.{tool.name}"
                    self._tools_by_qualified_name[qualified_name] = (server_id, tool)
            except MCPError as e:
                logger.warning(f"Failed to index tools from '{server_id}': {e}")

    def get_client(self, server_id: str) -> MCPClient | None:
        """Get a specific client by server ID."""
        return self._clients.get(server_id)


__all__ = [
    "MCPClientManager",
]
