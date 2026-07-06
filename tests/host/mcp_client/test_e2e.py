"""
End-to-end tests for MCP client integration.

These tests verify that Quenda can connect to MCP servers and use their tools.
"""

import asyncio
import pytest
from pathlib import Path
from types import SimpleNamespace

from quenda.host.mcp import (
    MCPConfig,
    MCPClientManager,
    MCPToolRegistry,
    StdioMCPConfig,
)
from quenda.host.runner import connect_mcp_servers


# Use absolute path to project root
PROJECT_ROOT = Path("/Users/xushiting/Workspace/quenda")
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CALCULATOR_SERVER = EXAMPLES_DIR / "mcp" / "calculator_server.py"


class TestMCPClientE2E:
    """End-to-end tests for MCP client."""

    @pytest.fixture
    def calculator_server_path(self) -> Path:
        """Get path to calculator server example."""
        return CALCULATOR_SERVER

    @pytest.mark.asyncio
    async def test_connect_to_stdio_server(self, calculator_server_path: Path) -> None:
        """Test connecting to a stdio MCP server."""
        if not calculator_server_path.exists():
            pytest.skip(f"Calculator server not found at {calculator_server_path}")

        config = MCPConfig.from_dict({
            "servers": {
                "calculator": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                }
            }
        })

        manager = MCPClientManager()

        try:
            # Connect
            connected = await manager.connect_from_config(config)
            assert "calculator" in connected

            # List tools
            tools = await manager.list_all_tools_flat()
            tool_names = [t.name for _, t in tools]

            assert "add" in tool_names
            assert "multiply" in tool_names

            # Call tool
            result = await manager.call_tool("calculator.add", {"a": 5, "b": 3})
            assert result == 8  # 5 + 3 = 8

            result = await manager.call_tool("mcp__calculator__multiply", {"a": 4, "b": 7})
            assert result == 28  # 4 * 7 = 28

        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_build_tool_adapters(self, calculator_server_path: Path) -> None:
        """Test building tool adapters from MCP server."""
        if not calculator_server_path.exists():
            pytest.skip(f"Calculator server not found at {calculator_server_path}")

        config = MCPConfig.from_dict({
            "servers": {
                "calc": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                }
            }
        })

        manager = MCPClientManager()

        try:
            await manager.connect_from_config(config)

            # Build tool registry
            registry = MCPToolRegistry(manager)
            tools = await registry.build_tools()

            tool_names = [t.name for t in tools]
            assert "mcp__calc__add" in tool_names
            assert "mcp__calc__multiply" in tool_names

            # Check tool descriptions
            add_tool = next(t for t in tools if t.name == "mcp__calc__add")
            assert "add" in add_tool.description.lower() or "two" in add_tool.description.lower()

        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_connect_mcp_servers_returns_tool_adapters(self, calculator_server_path: Path) -> None:
        """Test host runner MCP connection helper returns tools for the model pool."""
        if not calculator_server_path.exists():
            pytest.skip(f"Calculator server not found at {calculator_server_path}")

        config = MCPConfig.from_dict({
            "servers": {
                "calc": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                }
            }
        })
        manager = MCPClientManager()
        binding = SimpleNamespace(
            mcp_manager=manager,
            agent_package=SimpleNamespace(config=SimpleNamespace(mcp=config)),
        )

        try:
            tools = await connect_mcp_servers(binding)
            tool_names = [tool.name for tool in tools]

            assert "mcp__calc__add" in tool_names
            assert "mcp__calc__multiply" in tool_names
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_tool_adapter_async_execution(self, calculator_server_path: Path) -> None:
        """Test executing tools through async manager API."""
        if not calculator_server_path.exists():
            pytest.skip(f"Calculator server not found at {calculator_server_path}")

        config = MCPConfig.from_dict({
            "servers": {
                "calc": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                }
            }
        })

        manager = MCPClientManager()

        try:
            await manager.connect_from_config(config)

            # Build tools to verify tool specs are correct
            registry = MCPToolRegistry(manager)
            tools = await registry.build_tools()

            # Find add tool
            add_tool = next(t for t in tools if t.name == "mcp__calc__add")
            assert add_tool.name == "mcp__calc__add"
            assert "add" in add_tool.description.lower() or "two" in add_tool.description.lower()

            # Execute via manager's async API (sync execute() doesn't work in async context)
            result = await manager.call_tool("mcp__calc__add", {"a": 10, "b": 25})
            assert result == 35  # 10 + 25 = 35

        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_multiple_servers(self, calculator_server_path: Path) -> None:
        """Test connecting to multiple MCP servers."""
        if not calculator_server_path.exists():
            pytest.skip(f"Calculator server not found at {calculator_server_path}")

        config = MCPConfig.from_dict({
            "servers": {
                "calc1": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                },
                "calc2": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(calculator_server_path)],
                }
            }
        })

        manager = MCPClientManager()

        try:
            connected = await manager.connect_from_config(config)
            assert len(connected) == 2
            assert "calc1" in connected
            assert "calc2" in connected

            # Tools should be prefixed with server name
            tools = await manager.list_all_tools_flat()
            qualified_names = [f"{s}.{t.name}" for s, t in tools]

            assert "calc1.add" in qualified_names
            assert "calc2.add" in qualified_names

            # Call tools on different servers
            result1 = await manager.call_tool("calc1.add", {"a": 1, "b": 2})
            result2 = await manager.call_tool("calc2.add", {"a": 3, "b": 4})

            assert result1 == 3  # 1 + 2
            assert result2 == 7  # 3 + 4

        finally:
            await manager.close()
