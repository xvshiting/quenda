"""
MCP client - Wrapper around MCP SDK ClientSession.

Provides a thin adapter layer that:
- Manages connection lifecycle with AsyncExitStack
- Hides SDK types from the rest of Quenda
- Converts SDK exceptions to Quenda MCPError types
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quenda.host.mcp.config import HTTPMCPConfig, MCPServerConfig, StdioMCPConfig
from quenda.host.mcp.errors import (
    MCPConnectionError,
    MCPNotConnectedError,
    MCPToolError,
    wrap_mcp_exception,
)

if TYPE_CHECKING:
    from mcp import ClientSession

logger = logging.getLogger(__name__)


@dataclass
class MCPToolSpec:
    """Specification of an MCP tool."""

    name: str
    """Local tool name (without server prefix)."""

    description: str
    """Tool description."""

    input_schema: dict[str, Any]
    """JSON Schema for tool input."""

    title: str | None = None
    """Optional human-readable title."""


@dataclass
class MCPResourceSpec:
    """Specification of an MCP resource."""

    uri: str
    """Resource URI."""

    name: str
    """Human-readable name."""

    description: str | None = None
    """Optional description."""

    mime_type: str | None = None
    """Optional MIME type."""


@dataclass
class MCPClient:
    """
    Wrapper for a single MCP server connection.

    Uses AsyncExitStack to manage nested async context managers:
    1. Transport (stdio_client or streamable_http_client)
    2. ClientSession

    Usage:
        client = MCPClient(server_id="calculator", config=stdio_config)
        await client.connect()

        tools = await client.list_tools()
        result = await client.call_tool("add", {"a": 1, "b": 2})

        await client.close()
    """

    server_id: str
    config: MCPServerConfig

    _stack: AsyncExitStack | None = field(default=None, init=False, repr=False)
    _session: ClientSession | None = field(default=None, init=False, repr=False)
    _tools_cache: list[MCPToolSpec] = field(default_factory=list, init=False, repr=False)

    @property
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._session is not None

    async def connect(self) -> None:
        """
        Establish connection to the MCP server.

        Raises:
            MCPConnectionError: If connection fails.
        """
        if self._session is not None:
            return  # Already connected

        try:
            if isinstance(self.config, StdioMCPConfig):
                await self._connect_stdio()
            elif isinstance(self.config, HTTPMCPConfig):
                await self._connect_http()
            else:
                raise MCPConnectionError(
                    self.server_id,
                    f"Unknown transport type: {type(self.config).__name__}",
                )

            logger.info(f"MCP server '{self.server_id}' connected")

        except Exception as e:
            # Clean up on failure
            if self._stack is not None:
                await self._stack.aclose()
                self._stack = None
            self._session = None

            if isinstance(e, MCPConnectionError):
                raise
            raise MCPConnectionError(self.server_id, str(e)) from e

    async def _connect_stdio(self) -> None:
        """Connect to a stdio MCP server."""
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        config = self.config
        assert isinstance(config, StdioMCPConfig)

        stack = AsyncExitStack()

        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env or None,
            cwd=config.cwd,
        )

        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(params)
        )

        session = await stack.enter_async_context(
            self._create_session(read_stream, write_stream)
        )

        await session.initialize()

        self._stack = stack
        self._session = session

    async def _connect_http(self) -> None:
        """Connect to a Streamable HTTP MCP server."""
        from mcp.client.streamable_http import streamable_http_client

        config = self.config
        assert isinstance(config, HTTPMCPConfig)

        stack = AsyncExitStack()

        # streamable_http_client returns (read_stream, write_stream, session_id_callback)
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(config.url, headers=config.headers or None)
        )

        session = await stack.enter_async_context(
            self._create_session(read_stream, write_stream)
        )

        await session.initialize()

        self._stack = stack
        self._session = session

    def _create_session(self, read_stream: Any, write_stream: Any) -> "ClientSession":
        """Create a ClientSession with streams."""
        from mcp import ClientSession

        return ClientSession(read_stream, write_stream)

    async def list_tools(self) -> list[MCPToolSpec]:
        """
        List available tools from the server.

        Returns:
            List of tool specifications.

        Raises:
            MCPNotConnectedError: If not connected.
            MCPToolError: If the request fails.
        """
        session = self._require_session()

        try:
            response = await session.list_tools()
            tools: list[MCPToolSpec] = []

            # Handle different response formats (v1 vs v2)
            if hasattr(response, "tools"):
                # v1 format: ListToolsResult with .tools attribute
                for tool in response.tools:
                    tools.append(MCPToolSpec(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=getattr(tool, "inputSchema", getattr(tool, "input_schema", {})),
                        title=getattr(tool, "title", None),
                    ))
            else:
                # v2 format: async iterator or list of tuples
                async for item in response:
                    if item[0] == "tools":
                        for tool in item[1]:
                            tools.append(MCPToolSpec(
                                name=tool.name,
                                description=tool.description or "",
                                input_schema=getattr(tool, "inputSchema", getattr(tool, "input_schema", {})),
                                title=getattr(tool, "title", None),
                            ))

            self._tools_cache = tools
            return tools

        except Exception as e:
            raise wrap_mcp_exception(e, self.server_id)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute a tool on the server.

        Args:
            tool_name: The name of the tool to call.
            arguments: The arguments to pass to the tool.

        Returns:
            The tool result (extracted from structured content if available).

        Raises:
            MCPNotConnectedError: If not connected.
            MCPToolError: If tool execution fails.
        """
        session = self._require_session()

        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Extract result from structured content (FastMCP format)
            if hasattr(result, "structuredContent") and result.structuredContent is not None:
                sc = result.structuredContent
                # If it's a dict with just 'result', extract the value
                if isinstance(sc, dict) and len(sc) == 1 and "result" in sc:
                    return sc["result"]
                return sc

            # Fall back to structured_content (older format)
            if hasattr(result, "structured_content") and result.structured_content is not None:
                sc = result.structured_content
                if isinstance(sc, dict) and len(sc) == 1 and "result" in sc:
                    return sc["result"]
                return sc

            # Fall back to content list - extract text
            if hasattr(result, "content") and result.content:
                content = result.content
                if isinstance(content, list) and len(content) == 1:
                    item = content[0]
                    if hasattr(item, "text"):
                        # Try to parse as number if possible
                        text = item.text
                        try:
                            return int(text)
                        except ValueError:
                            try:
                                return float(text)
                            except ValueError:
                                return text
                return content

            return result

        except Exception as e:
            raise wrap_mcp_exception(e, self.server_id, tool_name)

    async def list_resources(self) -> list[MCPResourceSpec]:
        """
        List available resources from the server.

        Returns:
            List of resource specifications.

        Raises:
            MCPNotConnectedError: If not connected.
            MCPResourceError: If the request fails.
        """
        session = self._require_session()

        try:
            response = await session.list_resources()
            resources: list[MCPResourceSpec] = []

            if hasattr(response, "resources"):
                for resource in response.resources:
                    resources.append(MCPResourceSpec(
                        uri=resource.uri,
                        name=resource.name,
                        description=getattr(resource, "description", None),
                        mime_type=getattr(resource, "mimeType", None) or getattr(resource, "mime_type", None),
                    ))

            return resources

        except Exception as e:
            from quenda.host.mcp.errors import MCPResourceError
            raise MCPResourceError(self.server_id, "", str(e))

    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource from the server.

        Args:
            uri: The resource URI.

        Returns:
            The resource content.

        Raises:
            MCPNotConnectedError: If not connected.
            MCPResourceError: If reading fails.
        """
        session = self._require_session()

        try:
            result = await session.read_resource(uri)

            if hasattr(result, "contents"):
                return result.contents
            return result

        except Exception as e:
            from quenda.host.mcp.errors import MCPResourceError
            raise MCPResourceError(self.server_id, uri, str(e))

    async def close(self) -> None:
        """Close the connection to the server."""
        if self._stack is not None:
            try:
                await self._stack.aclose()
            except Exception as e:
                logger.warning(f"Error closing MCP server '{self.server_id}': {e}")
            finally:
                self._stack = None
                self._session = None
                self._tools_cache = []

        logger.info(f"MCP server '{self.server_id}' disconnected")

    def _require_session(self) -> "ClientSession":
        """Get the session or raise if not connected."""
        if self._session is None:
            raise MCPNotConnectedError(self.server_id)
        return self._session

    def get_cached_tools(self) -> list[MCPToolSpec]:
        """Get cached tools without making a request."""
        return list(self._tools_cache)


__all__ = [
    "MCPToolSpec",
    "MCPResourceSpec",
    "MCPClient",
]
