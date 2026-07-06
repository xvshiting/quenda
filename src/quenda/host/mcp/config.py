"""
MCP configuration - Configuration models for MCP server connections.

Supports two transport types:
- stdio: Launch a local subprocess MCP server
- streamable_http: Connect to a remote HTTP MCP server

Example config.yaml:

    mcp:
      servers:
        calculator:
          transport: stdio
          command: python
          args:
            - servers/calculator.py
        knowledge:
          transport: streamable_http
          url: http://localhost:8000/mcp
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class StdioMCPConfig(BaseModel):
    """Configuration for stdio MCP server (local subprocess)."""

    transport: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | Path | None = None

    model_config = {"extra": "forbid"}


class HTTPMCPConfig(BaseModel):
    """Configuration for Streamable HTTP MCP server."""

    transport: Literal["streamable_http"] = "streamable_http"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


# Union type for MCP server configuration using discriminator
MCPServerConfig = Annotated[
    StdioMCPConfig | HTTPMCPConfig,
    Field(discriminator="transport"),
]


@dataclass
class MCPConfig:
    """
    Top-level MCP configuration for an agent.

    Attributes:
        servers: Dictionary of server ID to server configuration.
    """

    servers: dict[str, MCPServerConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPConfig:
        """
        Parse MCP configuration from a dictionary.

        Args:
            data: The parsed YAML configuration.

        Returns:
            An MCPConfig instance.

        Raises:
            MCPConfigError: If the configuration is invalid.
        """
        from quenda.host.mcp.errors import MCPConfigError

        servers: dict[str, MCPServerConfig] = {}

        servers_data = data.get("servers", {})
        if not isinstance(servers_data, dict):
            raise MCPConfigError("'servers' must be a dictionary")

        for server_id, server_config in servers_data.items():
            if not isinstance(server_config, dict):
                raise MCPConfigError(f"Server '{server_id}' configuration must be a dictionary")

            transport = server_config.get("transport", "stdio")
            try:
                if transport == "stdio":
                    servers[server_id] = StdioMCPConfig(**server_config)
                elif transport == "streamable_http":
                    servers[server_id] = HTTPMCPConfig(**server_config)
                else:
                    raise MCPConfigError(f"Unknown transport type: {transport}")
            except Exception as e:
                raise MCPConfigError(f"Invalid configuration for server '{server_id}': {e}") from e

        return cls(servers=servers)

    def get_server_ids(self) -> list[str]:
        """Get list of all configured server IDs."""
        return list(self.servers.keys())

    def has_servers(self) -> bool:
        """Check if any servers are configured."""
        return bool(self.servers)


__all__ = [
    "StdioMCPConfig",
    "HTTPMCPConfig",
    "MCPServerConfig",
    "MCPConfig",
]
