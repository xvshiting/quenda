"""
Tests for MCP configuration parsing.
"""

import pytest
from pathlib import Path

from quenda.host.mcp.config import MCPConfig, StdioMCPConfig, HTTPMCPConfig
from quenda.host.mcp.errors import MCPConfigError


class TestMCPConfig:
    """Tests for MCP configuration parsing."""

    def test_empty_config(self) -> None:
        """Test empty MCP config."""
        config = MCPConfig.from_dict({})
        assert config.servers == {}
        assert not config.has_servers()

    def test_no_servers(self) -> None:
        """Test config with servers key but no servers."""
        config = MCPConfig.from_dict({"servers": {}})
        assert config.servers == {}
        assert not config.has_servers()

    def test_stdio_server_config(self) -> None:
        """Test stdio server configuration."""
        config = MCPConfig.from_dict({
            "servers": {
                "calculator": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["calc.py"],
                    "env": {"DEBUG": "1"},
                }
            }
        })

        assert config.has_servers()
        assert "calculator" in config.servers

        server = config.servers["calculator"]
        assert isinstance(server, StdioMCPConfig)
        assert server.transport == "stdio"
        assert server.command == "python"
        assert server.args == ["calc.py"]
        assert server.env == {"DEBUG": "1"}

    def test_http_server_config(self) -> None:
        """Test HTTP server configuration."""
        config = MCPConfig.from_dict({
            "servers": {
                "knowledge": {
                    "transport": "streamable_http",
                    "url": "http://localhost:8000/mcp",
                    "headers": {"Authorization": "Bearer token"},
                }
            }
        })

        assert config.has_servers()
        assert "knowledge" in config.servers

        server = config.servers["knowledge"]
        assert isinstance(server, HTTPMCPConfig)
        assert server.transport == "streamable_http"
        assert server.url == "http://localhost:8000/mcp"
        assert server.headers == {"Authorization": "Bearer token"}

    def test_multiple_servers(self) -> None:
        """Test multiple server configurations."""
        config = MCPConfig.from_dict({
            "servers": {
                "calc": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["calc.py"],
                },
                "search": {
                    "transport": "streamable_http",
                    "url": "http://localhost:9000/mcp",
                }
            }
        })

        assert config.has_servers()
        assert len(config.servers) == 2
        assert "calc" in config.servers
        assert "search" in config.servers

    def test_invalid_transport(self) -> None:
        """Test invalid transport type raises error."""
        with pytest.raises(MCPConfigError) as exc_info:
            MCPConfig.from_dict({
                "servers": {
                    "test": {
                        "transport": "invalid",
                        "command": "python",
                    }
                }
            })

        assert "Unknown transport type" in str(exc_info.value)

    def test_servers_not_dict(self) -> None:
        """Test servers not being a dict raises error."""
        with pytest.raises(MCPConfigError):
            MCPConfig.from_dict({"servers": "invalid"})

    def test_server_config_not_dict(self) -> None:
        """Test server config not being a dict raises error."""
        with pytest.raises(MCPConfigError):
            MCPConfig.from_dict({"servers": {"test": "invalid"}})

    def test_stdio_defaults(self) -> None:
        """Test stdio server default values."""
        config = MCPConfig.from_dict({
            "servers": {
                "test": {
                    "transport": "stdio",
                    "command": "python",
                }
            }
        })

        server = config.servers["test"]
        assert server.args == []
        assert server.env == {}
        assert server.cwd is None

    def test_http_defaults(self) -> None:
        """Test HTTP server default values."""
        config = MCPConfig.from_dict({
            "servers": {
                "test": {
                    "transport": "streamable_http",
                    "url": "http://localhost/mcp",
                }
            }
        })

        server = config.servers["test"]
        assert server.headers == {}

    def test_get_server_ids(self) -> None:
        """Test getting server IDs."""
        config = MCPConfig.from_dict({
            "servers": {
                "a": {"transport": "stdio", "command": "a"},
                "b": {"transport": "stdio", "command": "b"},
            }
        })

        ids = config.get_server_ids()
        assert set(ids) == {"a", "b"}


class TestMCPConfigIntegration:
    """Tests for MCP config integration with AgentConfigYaml."""

    def test_agent_config_with_mcp(self) -> None:
        """Test AgentConfigYaml with MCP configuration."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "model": {"provider": "test", "name": "test-model"},
            "mcp": {
                "servers": {
                    "calc": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["calc.py"],
                    }
                }
            }
        })

        assert config.mcp is not None
        assert config.mcp.has_servers()
        assert "calc" in config.mcp.servers

    def test_agent_config_without_mcp(self) -> None:
        """Test AgentConfigYaml without MCP configuration."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "model": {"provider": "test", "name": "test-model"},
        })

        assert config.mcp is None

    def test_agent_config_empty_mcp(self) -> None:
        """Test AgentConfigYaml with empty MCP configuration."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "model": {"provider": "test", "name": "test-model"},
            "mcp": {}
        })

        # Empty mcp dict should result in None or empty config
        assert config.mcp is None or not config.mcp.has_servers()
