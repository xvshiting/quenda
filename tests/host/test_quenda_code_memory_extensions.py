"""Integration tests for Quenda Code's context and memory extensions."""

from pathlib import Path

from quenda.host.extensions import (
    AgentExtensionContext,
    AgentInitializerRegistry,
    ContextProviderRegistry,
    ContextProviderRequest,
)
from quenda.host.identity import User
from quenda.host.loader import (
    find_builtin_agent,
    load_agent_context_providers,
    load_agent_initializers,
    load_agent_package,
    load_agent_tools,
)
from quenda.host.registry import ToolRegistryBuilder
from quenda.host.runner import _resolve_tools


def extension_context(tmp_path: Path) -> AgentExtensionContext:
    agent_path = find_builtin_agent("quenda-code")
    assert agent_path is not None
    user_agent_path = tmp_path / "users" / "alice" / "agents" / "quenda-code"
    user_agent_path.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return AgentExtensionContext(
        agent_name="quenda-code",
        agent_package_path=agent_path,
        user=User(id="alice"),
        user_agent_path=user_agent_path,
        workspace_path=workspace,
        workspace_id="ws-test",
    )


def test_profile_provider_loads_soul_user_and_core_memory(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    (context.user_agent_path / "USER.md").write_text(
        "Prefer Chinese.", encoding="utf-8"
    )
    (context.user_agent_path / "MEMORY.md").write_text(
        "Quenda has four layers.", encoding="utf-8"
    )
    registry = ContextProviderRegistry()

    loaded = load_agent_context_providers(
        context.agent_package_path,
        registry,
    )
    sources = registry.provide(ContextProviderRequest(extension=context))

    assert loaded == 1
    assert [source.path.name for source in sources if source.path] == [
        "SOUL.md",
        "USER.md",
        "MEMORY.md",
    ]
    composed = "\n".join(source.content for source in sources)
    assert "<agent_soul>" in composed
    assert "<user_profile>" in composed
    assert "<core_memory>" in composed


def test_profile_initializer_creates_private_scaffolding(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    registry = AgentInitializerRegistry()

    loaded = load_agent_initializers(context.agent_package_path, registry)
    registry.initialize(context)

    assert loaded == 1
    assert (context.user_agent_path / "USER.md").is_file()
    assert (context.user_agent_path / "MEMORY.md").is_file()
    assert (context.user_agent_path / "memory").is_dir()
    assert "Preferred language" in (
        context.user_agent_path / "USER.md"
    ).read_text(encoding="utf-8")


def test_profile_initializer_never_overwrites_existing_files(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    user_file = context.user_agent_path / "USER.md"
    memory_file = context.user_agent_path / "MEMORY.md"
    user_file.write_text("My explicit preferences.", encoding="utf-8")
    memory_file.write_text("My curated memory.", encoding="utf-8")
    registry = AgentInitializerRegistry()
    load_agent_initializers(context.agent_package_path, registry)

    registry.initialize(context)
    registry.initialize(context)

    assert user_file.read_text(encoding="utf-8") == "My explicit preferences."
    assert memory_file.read_text(encoding="utf-8") == "My curated memory."


def test_profile_provider_skips_missing_private_files(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    registry = ContextProviderRegistry()
    load_agent_context_providers(context.agent_package_path, registry)

    sources = registry.provide(ContextProviderRequest(extension=context))

    assert [source.path.name for source in sources if source.path] == ["SOUL.md"]


def test_memory_tools_search_and_get_without_index(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    memory_root = context.user_agent_path / "memory"
    (memory_root / "projects").mkdir(parents=True)
    (memory_root / "projects" / "quenda.md").write_text(
        "# Quenda\n\nThe ContextProvider seam composes fresh context every Run.\n",
        encoding="utf-8",
    )
    (memory_root / "2026-07-27.md").write_text(
        "# Daily note\n\nDiscussed Markdown memory retrieval.\n",
        encoding="utf-8",
    )
    builder = ToolRegistryBuilder()
    load_agent_tools(context.agent_package_path, builder, context)
    catalog = builder.build()
    search = catalog.get("memory_search")
    get = catalog.get("memory_get")
    assert search is not None and search.tool is not None
    assert get is not None and get.tool is not None

    search_result = search.tool.execute(query="ContextProvider", limit=6)
    get_result = get.tool.execute(path="projects/quenda.md", start_line=1)

    assert not search_result.is_error
    assert "projects/quenda.md:3" in search_result.content
    assert not get_result.is_error
    assert "ContextProvider seam" in get_result.content


def test_memory_get_rejects_path_escape(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    builder = ToolRegistryBuilder()
    load_agent_tools(context.agent_package_path, builder, context)
    spec = builder.build().get("memory_get")
    assert spec is not None and spec.tool is not None

    result = spec.tool.execute(path="../MEMORY.md")

    assert result.is_error
    assert "escapes the memory library" in result.content


def test_quenda_code_config_grants_memory_tools(tmp_path: Path) -> None:
    context = extension_context(tmp_path)
    builder = ToolRegistryBuilder()
    load_agent_tools(context.agent_package_path, builder, context)
    package = load_agent_package(context.agent_package_path)

    tools = _resolve_tools(
        context.workspace_path,
        package.config,
        builder.build(),
    )

    names = {tool.name for tool in tools}
    assert {"memory_search", "memory_get"} <= names
