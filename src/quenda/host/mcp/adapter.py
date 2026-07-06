"""
MCP tool adapter - Adapt MCP tools to Quenda Tool interface.

Bridges the gap between MCP's async tool execution and Quenda's sync Tool protocol.

Key challenges:
1. MCP SDK is async, Quenda Tool.execute() is sync
2. Need to prefix tool names with server_id to avoid collisions
3. Need to manage connection lifecycle across tool invocations
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, override

from quenda.host.mcp.client import MCPToolSpec
from quenda.host.mcp.errors import MCPToolError
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult

if TYPE_CHECKING:
    from quenda.host.mcp.manager import MCPClientManager

logger = logging.getLogger(__name__)


class MCPToolAdapter(Tool):
    """
    Adapter that wraps an MCP tool as a Quenda Tool.

    This adapter:
    - Uses qualified name (mcp__server_id__tool_name) as the tool name
    - Bridges async MCP execution to sync Tool.execute()
    - Converts MCP results to Quenda ToolResult

    Note: The async-to-sync bridge uses asyncio.run() which creates
    a new event loop. This is acceptable for MVP but may need
    optimization for high-throughput scenarios.
    """

    def __init__(
        self,
        server_id: str,
        tool_spec: MCPToolSpec,
        manager: MCPClientManager,
    ) -> None:
        self._server_id = server_id
        self._tool_spec = tool_spec
        self._manager = manager

    @property
    @override
    def name(self) -> str:
        """Qualified tool name (mcp__server_id__tool_name)."""
        return f"mcp__{self._server_id}__{self._tool_spec.name}"

    @property
    @override
    def description(self) -> str:
        """Tool description."""
        return self._tool_spec.description

    @property
    @override
    def parameters(self) -> dict[str, object]:
        """JSON Schema for tool parameters."""
        return self._tool_spec.input_schema

    @override
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the MCP tool.

        Bridges async MCP execution to sync Tool interface.
        Uses asyncio.run() to create a new event loop.

        Note: This method should only be called from a sync context.
        In async contexts, use the manager's call_tool() directly.

        Args:
            **kwargs: Tool arguments.

        Returns:
            ToolResult with the execution result.
        """
        try:
            # Run async operation in a new event loop
            result = asyncio.run(self._async_execute(kwargs))
            return result
        except Exception as e:
            logger.error(f"MCP tool '{self.name}' execution failed: {e}")
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: {e}",
                is_error=True,
            )

    async def _async_execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Async implementation of tool execution."""
        try:
            result = await self._manager.call_tool(
                qualified_name=self.name,
                arguments=arguments,
            )

            # Convert result to string content
            if isinstance(result, str):
                content = result
            elif isinstance(result, dict):
                # Try to extract meaningful content
                if "content" in result:
                    content = self._format_content(result["content"])
                elif "result" in result:
                    content = str(result["result"])
                else:
                    import json
                    content = json.dumps(result, indent=2, ensure_ascii=False)
            elif isinstance(result, list):
                content = self._format_content_list(result)
            else:
                content = str(result)

            return ToolResult(
                call_id="",
                name=self.name,
                content=content,
                is_error=False,
                result_summary=f"Executed MCP tool: {self.name}",
            )

        except MCPToolError as e:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: {e}",
                is_error=True,
            )
        except Exception as e:
            logger.exception(f"Unexpected error in MCP tool '{self.name}'")
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Unexpected error: {e}",
                is_error=True,
            )

    def _format_content(self, content: Any) -> str:
        """Format a single content item."""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            if "text" in content:
                return content["text"]
            if "data" in content:
                return str(content["data"])
            import json
            return json.dumps(content, indent=2, ensure_ascii=False)
        return str(content)

    def _format_content_list(self, contents: list[Any]) -> str:
        """Format a list of content items."""
        formatted = []
        for item in contents:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    formatted.append(item.get("text", ""))
                elif item.get("type") == "image":
                    formatted.append("[Image content]")
                else:
                    formatted.append(self._format_content(item))
            else:
                formatted.append(str(item))
        return "\n".join(formatted)


class MCPToolRegistry:
    """
    Registry for all MCP tools from connected servers.

    Creates MCPToolAdapter instances for each tool discovered
    from connected MCP servers.
    """

    def __init__(self, manager: MCPClientManager) -> None:
        self._manager = manager

    async def build_tools(self) -> list[Tool]:
        """
        Build Tool adapters for all MCP tools.

        Returns:
            List of MCPToolAdapter instances.
        """
        tools: list[Tool] = []

        all_tools = await self._manager.list_all_tools_flat()

        for server_id, tool_spec in all_tools:
            adapter = MCPToolAdapter(
                server_id=server_id,
                tool_spec=tool_spec,
                manager=self._manager,
            )
            tools.append(adapter)

        return tools

    def build_tools_from_cache(self) -> list[Tool]:
        """
        Build Tool adapters from cached tool info.

        Use this when tools have already been discovered
        and you don't want to make network calls.

        Returns:
            List of MCPToolAdapter instances.
        """
        tools: list[Tool] = []

        for server_id, client in self._manager._clients.items():
            for tool_spec in client.get_cached_tools():
                adapter = MCPToolAdapter(
                    server_id=server_id,
                    tool_spec=tool_spec,
                    manager=self._manager,
                )
                tools.append(adapter)

        return tools


__all__ = [
    "MCPToolAdapter",
    "MCPToolRegistry",
]
