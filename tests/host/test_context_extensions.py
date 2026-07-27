"""Tests for agent-local context provider extensions."""

from pathlib import Path

import pytest

from quenda.host.extensions import (
    AgentExtensionContext,
    AgentInitializerRegistry,
    ContextProviderRegistry,
    ContextProviderRequest,
)
from quenda.host.identity import User
from quenda.host.instructions import InstructionScope, InstructionSource
from quenda.host.loader import (
    load_agent_context_providers,
    load_agent_initializers,
)
from quenda.host.runner import (
    StableHostBinding,
    refresh_run_context,
    setup_host_binding,
)


def make_request(tmp_path: Path) -> ContextProviderRequest:
    extension = AgentExtensionContext(
        agent_name="test-agent",
        agent_package_path=tmp_path / "agent",
        user=User(id="user-1"),
        user_agent_path=tmp_path / "user-agent",
        workspace_path=tmp_path / "workspace",
        workspace_id="ws-1",
    )
    return ContextProviderRequest(extension=extension, session_id="session-1")


class StaticProvider:
    def __init__(self, content: str) -> None:
        self.content = content

    def provide(self, request: ContextProviderRequest) -> list[InstructionSource]:
        return [
            InstructionSource(
                scope=InstructionScope.AGENT_INSTRUCTIONS,
                content=f"{self.content}:{request.session_id}",
            )
        ]


def test_registry_preserves_provider_order(tmp_path: Path) -> None:
    registry = ContextProviderRegistry()
    registry.register(StaticProvider("first"))
    registry.register(StaticProvider("second"))

    sources = registry.provide(make_request(tmp_path))

    assert [source.content for source in sources] == [
        "first:session-1",
        "second:session-1",
    ]


def test_registry_rejects_invalid_provider_result(tmp_path: Path) -> None:
    class InvalidProvider:
        def provide(self, request: ContextProviderRequest) -> list[str]:
            del request
            return ["not-an-instruction-source"]

    registry = ContextProviderRegistry()
    registry.register(InvalidProvider())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="list\\[InstructionSource\\]"):
        registry.provide(make_request(tmp_path))


def test_load_agent_context_providers(tmp_path: Path) -> None:
    context_dir = tmp_path / "extensions" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "profile.py").write_text(
        """
from quenda.host.extensions import ContextProviderRequest
from quenda.host.instructions import InstructionScope, InstructionSource

class ProfileProvider:
    def provide(self, request: ContextProviderRequest):
        return [InstructionSource(
            scope=InstructionScope.USER_AGENT,
            content=f"user:{request.extension.user.id}",
        )]

providers = [ProfileProvider()]
""",
        encoding="utf-8",
    )
    registry = ContextProviderRegistry()

    loaded = load_agent_context_providers(tmp_path, registry)
    sources = registry.provide(make_request(tmp_path))

    assert loaded == 1
    assert [source.content for source in sources] == ["user:user-1"]


def test_tool_register_can_receive_extension_context(tmp_path: Path) -> None:
    from quenda.host.loader import load_agent_tools
    from quenda.host.registry import ToolRegistryBuilder

    tools_dir = tmp_path / "extensions" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "context_tool.py").write_text(
        """
from quenda.kernel.types import ToolResult

class ContextTool:
    name = "context_path"
    description = "Return the resolved user-agent path."
    parameters = {"type": "object", "properties": {}}

    def __init__(self, path):
        self.path = path

    def execute(self, **kwargs):
        return ToolResult("", self.name, str(self.path))

def register(builder, context):
    builder.register(ContextTool(context.user_agent_path), source="agent_local")
""",
        encoding="utf-8",
    )
    builder = ToolRegistryBuilder()
    extension_context = make_request(tmp_path).extension

    loaded = load_agent_tools(tmp_path, builder, extension_context)
    tool = builder.build().get("context_path")

    assert loaded == 1
    assert tool is not None and tool.tool is not None
    assert tool.tool.execute().content == str(extension_context.user_agent_path)


def test_refresh_run_context_invokes_registered_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_path = tmp_path / "agent"
    agent_path.mkdir()
    (agent_path / "AGENT.md").write_text(
        "---\nname: test-agent\nversion: 1.0.0\n---\nBase instructions.",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request = make_request(tmp_path)
    registry = ContextProviderRegistry()
    registry.register(StaticProvider("extension"))
    binding = StableHostBinding(
        agent_package_path=agent_path,
        workspace_path=workspace,
        workspace_id="ws-1",
        user=request.extension.user,
        provider_name="test",
        model_name="test",
        model_instance=object(),  # type: ignore[arg-type]
        tools=[],
        sandbox_config=object(),  # type: ignore[arg-type]
        extension_context=request.extension,
        context_providers=registry,
    )

    snapshot = refresh_run_context(binding, session_id="session-2")

    assert "extension:session-2" in snapshot.composed_prompt


def test_load_and_run_agent_initializer(tmp_path: Path) -> None:
    setup_dir = tmp_path / "extensions" / "setup"
    setup_dir.mkdir(parents=True)
    (setup_dir / "files.py").write_text(
        """
class FileInitializer:
    def initialize(self, context):
        (context.user_agent_path / "initialized.txt").write_text(
            context.agent_name,
            encoding="utf-8",
        )

initializers = [FileInitializer()]
""",
        encoding="utf-8",
    )
    request = make_request(tmp_path)
    request.extension.user_agent_path.mkdir(parents=True)
    registry = AgentInitializerRegistry()

    loaded = load_agent_initializers(tmp_path, registry)
    registry.initialize(request.extension)

    assert loaded == 1
    assert (
        request.extension.user_agent_path / "initialized.txt"
    ).read_text(encoding="utf-8") == "test-agent"


def test_setup_host_binding_runs_initializers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_path = tmp_path / "agent"
    setup_dir = agent_path / "extensions" / "setup"
    setup_dir.mkdir(parents=True)
    (agent_path / "AGENT.md").write_text(
        "---\nname: setup-agent\n---\nTest agent.",
        encoding="utf-8",
    )
    (setup_dir / "marker.py").write_text(
        """
class MarkerInitializer:
    def initialize(self, context):
        (context.user_agent_path / "marker.txt").write_text(
            context.workspace_id,
            encoding="utf-8",
        )

initializers = [MarkerInitializer()]
""",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class ProviderRegistry:
        def get_model(self, provider: str, model: str) -> object:
            del provider, model
            return object()

    binding = setup_host_binding(
        agent_path,
        workspace,
        provider_registry=ProviderRegistry(),  # type: ignore[arg-type]
    )

    assert binding is not None and binding.extension_context is not None
    marker = binding.extension_context.user_agent_path / "marker.txt"
    assert marker.read_text(encoding="utf-8") == binding.workspace_id
