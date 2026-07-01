"""
Tests for agent capability declaration in config.yaml.

Tests the MVP for agents requesting tools and execution capabilities.
"""

import pytest
from pathlib import Path

from quenda.host.loader import (
    AgentConfigYaml,
    ToolsConfig,
    ExecutionConfig,
    PythonExecutionConfig,
)
from quenda.host.runner import _resolve_tools, _resolve_sandbox_config


class TestToolsConfig:
    """Tests for ToolsConfig parsing."""

    def test_empty_tools_config(self) -> None:
        """Test empty tools config."""
        config = ToolsConfig.from_dict({})
        assert config.bundles == []
        assert config.include == []

    def test_bundles_parsing(self) -> None:
        """Test parsing bundles list."""
        config = ToolsConfig.from_dict({
            "bundles": ["core", "network"],
        })
        assert config.bundles == ["core", "network"]
        assert config.include == []

    def test_include_parsing(self) -> None:
        """Test parsing include list."""
        config = ToolsConfig.from_dict({
            "include": ["http_request", "web_fetch"],
        })
        assert config.bundles == []
        assert config.include == ["http_request", "web_fetch"]


class TestExecutionConfig:
    """Tests for ExecutionConfig parsing."""

    def test_empty_execution_config(self) -> None:
        """Test empty execution config."""
        config = ExecutionConfig.from_dict({})
        assert config.python.allowed_modules == []

    def test_python_allowed_modules(self) -> None:
        """Test parsing allowed modules."""
        config = ExecutionConfig.from_dict({
            "python": {
                "allowed_modules": ["requests", "httpx"],
            },
        })
        assert config.python.allowed_modules == ["requests", "httpx"]


class TestResolveSandboxConfig:
    """Tests for sandbox config resolution."""

    def test_default_sandbox_config(self) -> None:
        """Test default sandbox config without agent request."""
        config = _resolve_sandbox_config(None)
        assert "math" in config.allowed_modules
        assert "json" in config.allowed_modules
        # Blocked modules should still be blocked
        assert "os" in config.blocked_modules

    def test_merge_requested_modules(self) -> None:
        """Test merging agent-requested modules with defaults."""
        agent_config = AgentConfigYaml(
            execution=ExecutionConfig(
                python=PythonExecutionConfig(
                    allowed_modules=["requests", "httpx"],
                ),
            ),
        )
        config = _resolve_sandbox_config(agent_config)
        # Default modules
        assert "math" in config.allowed_modules
        assert "json" in config.allowed_modules
        # Requested modules
        assert "requests" in config.allowed_modules
        assert "httpx" in config.allowed_modules

    def test_no_duplicate_modules(self) -> None:
        """Test that already-present modules aren't duplicated."""
        agent_config = AgentConfigYaml(
            execution=ExecutionConfig(
                python=PythonExecutionConfig(
                    allowed_modules=["math", "json", "requests"],
                ),
            ),
        )
        config = _resolve_sandbox_config(agent_config)
        # Count occurrences
        assert config.allowed_modules.count("math") == 1
        assert config.allowed_modules.count("json") == 1


class TestResolveTools:
    """Tests for tool resolution based on capability declaration."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a workspace directory."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        return ws

    def test_core_tools_by_default(self, workspace: Path) -> None:
        """Test that core tools are provided by compatibility default when no config."""
        # No config → compatibility default: ["core"]
        tools = _resolve_tools(workspace, None)
        tool_names = {t.name for t in tools}

        # Core tools from compatibility default
        assert "list_files" in tool_names
        assert "search_text" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "apply_patch" in tool_names
        assert "execute_python" in tool_names
        assert "run_shell" in tool_names
        assert "request_interaction" in tool_names
        assert "request_skill_activation" in tool_names

        # Network tools NOT included (not requested)
        assert "http_request" not in tool_names
        assert "web_fetch" not in tool_names

    def test_explicit_core_bundle(self, workspace: Path) -> None:
        """Test that explicitly requesting 'core' gives core tools."""
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # Core tools present
        assert "list_files" in tool_names
        assert "execute_python" in tool_names
        assert "request_skill_activation" in tool_names

        # No network tools
        assert "http_request" not in tool_names

    def test_network_tools_when_requested(self, workspace: Path) -> None:
        """Test that network tools are added when requested (core must be explicit)."""
        # Request both core and network
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core", "network"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # Core tools present
        assert "list_files" in tool_names
        assert "execute_python" in tool_names

        # Network tools now included
        assert "http_request" in tool_names
        assert "web_fetch" in tool_names
        assert "web_search" in tool_names

    def test_network_only_no_core(self, workspace: Path) -> None:
        """Test that requesting only 'network' gives only network tools."""
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["network"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # No core tools
        assert "list_files" not in tool_names
        assert "execute_python" not in tool_names

        # Only network tools
        assert "http_request" in tool_names
        assert "web_fetch" in tool_names
        assert "web_search" in tool_names

    def test_custom_sandbox_applied(self, workspace: Path) -> None:
        """Test that custom sandbox config is applied to Python tool."""
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"]),  # Need core for Python execution
            execution=ExecutionConfig(
                python=PythonExecutionConfig(
                    allowed_modules=["requests"],
                ),
            ),
        )
        tools = _resolve_tools(workspace, agent_config)

        # Find Python execution tool
        python_tool = next(t for t in tools if t.name == "execute_python")
        assert python_tool is not None

        # Verify sandbox config includes requests
        assert "requests" in python_tool.config.allowed_modules


class TestAgentConfigYamlIntegration:
    """Tests for full config.yaml parsing with capability declaration."""

    def test_full_config_parsing(self) -> None:
        """Test parsing a complete config with tools and execution."""
        config_data = {
            "model": {"provider": "deepseek", "name": "deepseek-v4-flash"},
            "skills": ["code-review"],
            "tools": {
                "bundles": ["network"],
            },
            "execution": {
                "python": {
                    "allowed_modules": ["requests", "httpx"],
                },
            },
        }
        config = AgentConfigYaml.from_dict(config_data)

        assert config.model_provider == "deepseek"
        assert config.model_name == "deepseek-v4-flash"
        assert config.skills == ["code-review"]
        assert config.include_skill_catalog is False
        assert config.tools.bundles == ["network"]
        assert config.execution.python.allowed_modules == ["requests", "httpx"]
