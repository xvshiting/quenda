"""
Tests for agent-local custom tool extensions (ADR-024).

Tests the complete flow from tool discovery to config resolution.
"""

import pytest
from pathlib import Path

from quenda.host.registry import (
    NamedToolSpec,
    LoadedToolCatalog,
    ToolRegistryBuilder,
)
from quenda.host.loader import load_agent_tools, AgentConfigYaml, ToolsConfig
from quenda.host.runner import _resolve_tools, _instantiate_tool
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


# Simple test tool
class EchoTool(Tool):
    """A simple echo tool for testing."""

    def __init__(self, name: str = "echo"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Echo back the input"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            call_id="",
            name=self.name,
            content=kwargs.get("message", ""),
        )


class TestToolRegistryBuilder:
    """Tests for ToolRegistryBuilder."""

    def test_register_tool(self) -> None:
        """Test registering a tool instance."""
        builder = ToolRegistryBuilder()
        tool = EchoTool()
        builder.register(tool, source="test")

        catalog = builder.build()
        assert catalog.has("echo")
        spec = catalog.get("echo")
        assert spec is not None
        assert spec.source == "test"
        assert spec.tool is tool

    def test_register_factory(self) -> None:
        """Test registering a tool factory."""
        builder = ToolRegistryBuilder()
        builder.register_factory("echo", EchoTool, source="test")

        catalog = builder.build()
        assert catalog.has("echo")
        spec = catalog.get("echo")
        assert spec is not None
        assert spec.factory is EchoTool

    def test_duplicate_tool_name_raises(self) -> None:
        """Test that duplicate tool names raise ValueError."""
        builder = ToolRegistryBuilder()
        builder.register(EchoTool(), source="source1")

        with pytest.raises(ValueError, match="Duplicate tool name"):
            builder.register(EchoTool(), source="source2")

    def test_duplicate_factory_name_raises(self) -> None:
        """Test that duplicate factory names raise ValueError."""
        builder = ToolRegistryBuilder()
        builder.register_factory("echo", EchoTool, source="source1")

        with pytest.raises(ValueError, match="Duplicate tool name"):
            builder.register_factory("echo", EchoTool, source="source2")


class TestNamedToolSpec:
    """Tests for NamedToolSpec."""

    def test_spec_with_tool(self) -> None:
        """Test creating a spec with a tool instance."""
        tool = EchoTool()
        spec = NamedToolSpec(name="echo", source="test", tool=tool)
        assert spec.tool is tool

    def test_spec_with_factory(self) -> None:
        """Test creating a spec with a factory."""
        spec = NamedToolSpec(name="echo", source="test", factory=EchoTool)
        assert spec.factory is EchoTool

    def test_spec_without_tool_or_factory_raises(self) -> None:
        """Test that spec without tool or factory raises."""
        with pytest.raises(ValueError, match="needs tool or factory"):
            NamedToolSpec(name="echo", source="test")


class TestLoadedToolCatalog:
    """Tests for LoadedToolCatalog."""

    def test_add_and_get(self) -> None:
        """Test adding and getting tools."""
        catalog = LoadedToolCatalog()
        tool = EchoTool()
        spec = NamedToolSpec(name="echo", source="test", tool=tool)

        catalog.add(spec)
        assert catalog.has("echo")
        assert catalog.get("echo") is spec

    def test_all_names(self) -> None:
        """Test getting all tool names."""
        catalog = LoadedToolCatalog()
        catalog.add(NamedToolSpec(name="echo", source="test", tool=EchoTool()))
        catalog.add(NamedToolSpec(name="ping", source="test", tool=EchoTool("ping")))

        names = catalog.all_names()
        assert set(names) == {"echo", "ping"}

    def test_empty_catalog(self) -> None:
        """Test empty catalog behavior."""
        catalog = LoadedToolCatalog()
        assert not catalog.has("nonexistent")
        assert catalog.get("nonexistent") is None
        assert catalog.all_names() == []


class TestLoadAgentTools:
    """Tests for load_agent_tools function."""

    @pytest.fixture
    def agent_with_tools(self, tmp_path: Path) -> Path:
        """Create an agent package with custom tools."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True)

        # Create AGENT.md
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")

        # Create tools directory
        tools_dir = agent_dir / "extensions" / "tools"
        tools_dir.mkdir(parents=True)

        # Create tool module with tools list
        (tools_dir / "echo_tool.py").write_text('''
from quenda import tool

@tool
def echo(message: str) -> str:
    """Echo back the message."""
    return message

tools = [echo]
''')

        # Create tool module with register function
        (tools_dir / "ping_tool.py").write_text('''
from quenda.host.registry import ToolRegistryBuilder

class PingTool:
    name = "ping"
    description = "Ping tool"
    parameters = {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        from quenda.kernel.types import ToolResult
        return ToolResult(call_id="", name="ping", content="pong")

def register(builder: ToolRegistryBuilder):
    builder.register(PingTool(), source="agent_local")
''')

        return agent_dir

    def test_load_tools_list(self, agent_with_tools: Path) -> None:
        """Test loading tools from tools list export."""
        builder = ToolRegistryBuilder()
        loaded = load_agent_tools(agent_with_tools, builder)

        assert loaded >= 1
        catalog = builder.build()
        assert catalog.has("echo")

    def test_load_register_function(self, agent_with_tools: Path) -> None:
        """Test loading tools from register function export."""
        builder = ToolRegistryBuilder()
        load_agent_tools(agent_with_tools, builder)

        catalog = builder.build()
        assert catalog.has("ping")

    def test_no_tools_directory(self, tmp_path: Path) -> None:
        """Test when no tools directory exists."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text("---\nname: test\n---\n")

        builder = ToolRegistryBuilder()
        loaded = load_agent_tools(agent_dir, builder)

        assert loaded == 0
        catalog = builder.build()
        assert len(catalog.all_names()) == 0


class TestResolveToolsWithCustom:
    """Tests for _resolve_tools with custom tools."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a workspace directory."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        return ws

    @pytest.fixture
    def custom_catalog(self) -> LoadedToolCatalog:
        """Create a catalog with custom tools."""
        catalog = LoadedToolCatalog()
        catalog.add(NamedToolSpec(
            name="custom_echo",
            source="agent_local",
            tool=EchoTool("custom_echo"),
        ))
        return catalog

    def test_include_custom_tool(self, workspace: Path, custom_catalog: LoadedToolCatalog) -> None:
        """Test including a custom tool."""
        config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"], include=["custom_echo"]),
        )
        tools = _resolve_tools(workspace, config, custom_catalog)
        tool_names = {t.name for t in tools}

        # Core tools
        assert "list_files" in tool_names
        # Custom tool
        assert "custom_echo" in tool_names

    def test_include_nonexistent_tool_raises(self, workspace: Path) -> None:
        """Test that including nonexistent tool raises."""
        config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"], include=["nonexistent"]),
        )

        with pytest.raises(ValueError, match="not found"):
            _resolve_tools(workspace, config, None)

    def test_custom_tool_overrides_builtin_raises(self, workspace: Path) -> None:
        """Test that custom tool cannot override built-in tool."""
        # Create catalog with tool named "list_files" (conflicts with builtin)
        catalog = LoadedToolCatalog()
        catalog.add(NamedToolSpec(
            name="list_files",
            source="agent_local",
            tool=EchoTool("list_files"),
        ))

        config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"]),
        )

        with pytest.raises(ValueError, match="conflicts with built-in"):
            _resolve_tools(workspace, config, catalog)


class TestInstantiateTool:
    """Tests for _instantiate_tool helper."""

    def test_instantiate_from_tool(self) -> None:
        """Test instantiating from tool instance."""
        tool = EchoTool()
        spec = NamedToolSpec(name="echo", source="test", tool=tool)

        result = _instantiate_tool(spec, Path.cwd())
        assert result is tool

    def test_instantiate_from_factory_no_args(self) -> None:
        """Test instantiating from factory without args."""
        def factory_no_args() -> EchoTool:
            return EchoTool("echo")

        spec = NamedToolSpec(name="echo", source="test", factory=factory_no_args)

        result = _instantiate_tool(spec, Path.cwd())
        assert result.name == "echo"

    def test_instantiate_from_factory_with_workspace(self, tmp_path: Path) -> None:
        """Test instantiating from factory with workspace arg."""
        def factory_with_workspace(ws: Path) -> EchoTool:
            return EchoTool(f"echo_{ws.name}")

        spec = NamedToolSpec(name="echo", source="test", factory=factory_with_workspace)

        result = _instantiate_tool(spec, tmp_path)
        assert tmp_path.name in result.name
