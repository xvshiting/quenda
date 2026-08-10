"""Tests for local Agent Home management."""

from pathlib import Path

import pytest

from quenda.host import AgentHomeManager, User
from quenda.host.instructions import resolve_instruction_sources
from quenda.host.loader import load_agent_package


def test_create_blank_agent_home_builds_runnable_scaffold(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path)

    home = manager.create("reviewer")

    assert home.path == tmp_path / "agent-reviewer"
    assert home.workspace.is_dir()
    assert (home.path / "AGENT.md").is_file()
    assert (home.path / "SOUL.md").is_file()
    assert (home.path / "USER.md").is_file()
    assert (home.path / "MEMORY.md").is_file()
    assert (home.path / "skills").is_dir()
    assert load_agent_package(home.path).name == "reviewer"


def test_create_from_source_copies_content_and_renames_agent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENT.md").write_text(
        "---\nname: template\nversion: 1.0.0\n---\n\nTemplate prompt.\n",
        encoding="utf-8",
    )
    (source / "custom.txt").write_text("source content", encoding="utf-8")
    manager = AgentHomeManager(tmp_path / "homes")

    home = manager.create("coder", source=source)
    (source / "custom.txt").write_text("changed later", encoding="utf-8")

    assert load_agent_package(home.path).name == "coder"
    assert (home.path / "custom.txt").read_text(encoding="utf-8") == "source content"
    assert home.created_from == str(source)


def test_list_uses_agent_directories_as_source_of_truth(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path)
    manager.create("writer")
    manager.create("reviewer")
    (tmp_path / "agent-incomplete").mkdir()

    assert [home.name for home in manager.list()] == ["reviewer", "writer"]


def test_create_rejects_existing_or_invalid_agent_names(tmp_path: Path) -> None:
    manager = AgentHomeManager(tmp_path)
    manager.create("reviewer")

    with pytest.raises(FileExistsError):
        manager.create("reviewer")
    with pytest.raises(ValueError):
        manager.create("../reviewer")


def test_source_must_be_agent_directory(tmp_path: Path) -> None:
    source = tmp_path / "not-an-agent"
    source.mkdir()

    with pytest.raises(ValueError, match="must contain AGENT.md"):
        AgentHomeManager(tmp_path / "homes").create("broken", source=source)


def test_agent_home_core_prompt_files_are_context_sources(tmp_path: Path) -> None:
    home = AgentHomeManager(tmp_path).create("reviewer")

    sources = resolve_instruction_sources(
        agent_package_path=home.path,
        agent_name=home.name,
        agent_md_content="Base prompt",
        agent_instructions=[],
        workspace_path=home.workspace,
        user=User(id="test-user", name="Test User"),
        workspace_id="workspace-id",
    )

    home_source_names = {
        source.path.name
        for source in sources
        if source.path is not None and source.path.parent == home.path
    }
    assert {"AGENT.md", "SOUL.md", "USER.md", "MEMORY.md"} <= home_source_names
