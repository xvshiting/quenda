"""Tests for local Agent Home management."""

import json
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
    assert (home.path / "IDENTITY.md").is_file()
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
    prompt = (home.path / "AGENT.md").read_text(encoding="utf-8")
    assert "canonical Agent name is **`coder`**" in prompt
    assert "Agent Home is named **`agent-coder`**" in prompt
    assert (home.path / "custom.txt").read_text(encoding="utf-8") == "source content"
    assert home.created_from == str(source)


def test_ensure_installs_source_once_and_preserves_local_changes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENT.md").write_text("---\nname: template\n---\n\nPrompt.\n")
    manager = AgentHomeManager(tmp_path / "homes")

    installed = manager.ensure("quenda-code", source=source)
    (installed.path / "AGENT.md").write_text("local changes")
    ensured_again = manager.ensure("quenda-code", source=source)

    assert ensured_again.path == installed.path
    assert (installed.path / "AGENT.md").read_text() == "local changes"

    clone = manager.create("coding-assistant", source="quenda-code")
    assert (clone.path / "AGENT.md").read_text() != "local changes"
    assert "local changes" in (clone.path / "AGENT.md").read_text()


def test_prepare_migrates_existing_home_identity_without_rewriting_source_body(
    tmp_path: Path,
) -> None:
    manager = AgentHomeManager(tmp_path)
    home = manager.create("codertest")
    (home.path / "AGENT.md").write_text(
        "---\nname: quenda-code\n---\n\nYou are Quenda Code.\n",
        encoding="utf-8",
    )

    prepared = manager.prepare("codertest")
    prompt = (home.path / "AGENT.md").read_text(encoding="utf-8")

    assert prepared == home
    assert load_agent_package(home.path).name == "codertest"
    assert "canonical Agent name is **`codertest`**" in prompt
    assert "Any other Agent name in copied source content" in prompt
    assert "You are Quenda Code." in prompt


def test_create_from_agent_home_does_not_copy_runtime_state(tmp_path: Path) -> None:
    source = AgentHomeManager(tmp_path / "source-root").create("source")
    (source.path / "sessions" / "private.json").write_text("session", encoding="utf-8")
    (source.path / "workspace" / "private.txt").write_text("workspace", encoding="utf-8")
    (source.path / "artifacts" / "private.txt").write_text("artifact", encoding="utf-8")
    (source.path / "memory" / "private.md").write_text("detail", encoding="utf-8")
    (source.path / "MEMORY.md").write_text("durable memory", encoding="utf-8")

    clone = AgentHomeManager(tmp_path / "clone-root").create("clone", source=source.path)

    assert not (clone.path / "sessions" / "private.json").exists()
    assert not (clone.path / "workspace" / "private.txt").exists()
    assert not (clone.path / "artifacts" / "private.txt").exists()
    assert not (clone.path / "memory" / "private.md").exists()
    assert (clone.path / "MEMORY.md").read_text(encoding="utf-8") == "durable memory"
    assert json.loads((clone.path / "agent.yaml").read_text(encoding="utf-8"))["name"] == "clone"


def test_create_adds_name_to_source_without_frontmatter(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENT.md").write_text("A plain agent prompt.\n", encoding="utf-8")

    home = AgentHomeManager(tmp_path / "homes").create("named", source=source)

    assert load_agent_package(home.path).name == "named"
    assert "A plain agent prompt." in (home.path / "AGENT.md").read_text(encoding="utf-8")


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


def test_failed_scaffold_does_not_leave_partial_agent_home(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENT.md").write_bytes(b"\xff\xfe")
    manager = AgentHomeManager(tmp_path / "homes")

    with pytest.raises(UnicodeDecodeError):
        manager.create("broken", source=source)

    assert not manager.home_path("broken").exists()


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
    assert {
        "AGENT.md",
        "IDENTITY.md",
        "SOUL.md",
        "USER.md",
        "MEMORY.md",
    } <= home_source_names
