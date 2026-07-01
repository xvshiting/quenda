"""
Tests for instruction layer (ADR-007).
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kora.host.instructions import (
    InstructionScope,
    InstructionSource,
    TemplateContext,
    InstructionComposer,
    resolve_instruction_sources,
)
from kora.host.loader import AgentPackage, AgentConfigYaml, load_agent_package
from kora.host.identity import User


class TestInstructionScope:
    """Tests for InstructionScope enum."""

    def test_scope_order(self) -> None:
        """Scopes are ordered by priority."""
        assert InstructionScope.FRAMEWORK < InstructionScope.AGENT_PACKAGE
        assert InstructionScope.AGENT_PACKAGE < InstructionScope.WORKSPACE
        assert InstructionScope.WORKSPACE < InstructionScope.WORKSPACE_AGENT


class TestInstructionSource:
    """Tests for InstructionSource."""

    def test_source_creation(self) -> None:
        """Create an instruction source."""
        source = InstructionSource(
            scope=InstructionScope.AGENT_PACKAGE,
            content="You are a helpful assistant.",
            path=Path("/path/to/AGENT.md"),
        )
        assert source.scope == InstructionScope.AGENT_PACKAGE
        assert source.content == "You are a helpful assistant."

    def test_source_frozen(self) -> None:
        """InstructionSource is immutable."""
        source = InstructionSource(
            scope=InstructionScope.AGENT_PACKAGE,
            content="test",
        )
        with pytest.raises(Exception):
            source.content = "changed"  # type: ignore


class TestTemplateContext:
    """Tests for TemplateContext."""

    def test_context_creation(self) -> None:
        """Create a template context."""
        context = TemplateContext(
            agent_name="kora-code",
            agent_version="0.1.0",
            workspace_id="ws_abc123",
            workspace_path="/home/user/project",
            user_id="user_123",
            model_provider="deepseek",
            model_name="deepseek-v4-flash",
            date="2024-01-15",
            session_id="session_xyz",
        )
        assert context.agent_name == "kora-code"
        assert context.workspace_id == "ws_abc123"


class TestInstructionComposer:
    """Tests for InstructionComposer."""

    def test_compose_single_source(self) -> None:
        """Compose with a single source."""
        context = TemplateContext(
            agent_name="test",
            agent_version="0.1.0",
            workspace_id="ws_123",
            workspace_path="/tmp",
            user_id="user_1",
            model_provider="test",
            model_name="test-model",
            date="2024-01-01",
            session_id="sess_1",
        )
        composer = InstructionComposer(context)
        sources = [
            InstructionSource(
                scope=InstructionScope.AGENT_PACKAGE,
                content="You are a test assistant.",
            )
        ]
        result = composer.compose(sources)
        assert result == "You are a test assistant."

    def test_compose_multiple_sources(self) -> None:
        """Compose with multiple sources (append-only)."""
        context = TemplateContext(
            agent_name="test",
            agent_version="0.1.0",
            workspace_id="ws_123",
            workspace_path="/tmp",
            user_id="user_1",
            model_provider="test",
            model_name="test-model",
            date="2024-01-01",
            session_id="sess_1",
        )
        composer = InstructionComposer(context)
        sources = [
            InstructionSource(
                scope=InstructionScope.AGENT_PACKAGE,
                content="Base prompt.",
            ),
            InstructionSource(
                scope=InstructionScope.WORKSPACE,
                content="Workspace-specific rules.",
            ),
        ]
        result = composer.compose(sources)
        assert result == "Base prompt.\n\nWorkspace-specific rules."

    def test_render_template_simple(self) -> None:
        """Render simple template variables."""
        context = TemplateContext(
            agent_name="kora-code",
            agent_version="0.1.0",
            workspace_id="ws_123",
            workspace_path="/home/user/project",
            user_id="user_1",
            model_provider="deepseek",
            model_name="deepseek-v4-flash",
            date="2024-01-15",
            session_id="sess_1",
        )
        composer = InstructionComposer(context)
        content = "Agent: {{agent.name}}, Workspace: {{workspace.id}}"
        result = composer.render_template(content)
        assert result == "Agent: kora-code, Workspace: ws_123"

    def test_render_template_all_variables(self) -> None:
        """Render all whitelisted variables."""
        context = TemplateContext(
            agent_name="kora-code",
            agent_version="1.0.0",
            workspace_id="ws_abc",
            workspace_path="/home/user/project",
            user_id="user_123",
            model_provider="openai",
            model_name="gpt-4",
            date="2024-06-23",
            session_id="sess_xyz",
        )
        composer = InstructionComposer(context)

        content = """Agent: {{agent.name}} v{{agent.version}}
Workspace: {{workspace.id}} at {{workspace.path}}
User: {{user.id}}
Model: {{model.provider}}/{{model.name}}
Date: {{date}}
Session: {{session.id}}"""

        result = composer.render_template(content)

        assert "Agent: kora-code v1.0.0" in result
        assert "Workspace: ws_abc at /home/user/project" in result
        assert "User: user_123" in result
        assert "Model: openai/gpt-4" in result
        assert "Date: 2024-06-23" in result
        assert "Session: sess_xyz" in result

    def test_render_template_unknown_variable(self) -> None:
        """Unknown variables are replaced with empty string."""
        context = TemplateContext(
            agent_name="test",
            agent_version="0.1.0",
            workspace_id="ws",
            workspace_path="/tmp",
            user_id="u",
            model_provider="p",
            model_name="m",
            date="d",
            session_id="s",
        )
        composer = InstructionComposer(context)
        content = "Unknown: {{unknown.var}}"
        result = composer.render_template(content)
        assert result == "Unknown: "

    def test_skip_empty_sources(self) -> None:
        """Empty sources are skipped."""
        context = TemplateContext(
            agent_name="test",
            agent_version="0.1.0",
            workspace_id="ws",
            workspace_path="/tmp",
            user_id="u",
            model_provider="p",
            model_name="m",
            date="d",
            session_id="s",
        )
        composer = InstructionComposer(context)
        sources = [
            InstructionSource(scope=InstructionScope.AGENT_PACKAGE, content="Valid."),
            InstructionSource(scope=InstructionScope.WORKSPACE, content="   "),  # Whitespace only
            InstructionSource(scope=InstructionScope.WORKSPACE_AGENT, content="Also valid."),
        ]
        result = composer.compose(sources)
        assert result == "Valid.\n\nAlso valid."


class TestResolveInstructionSources:
    """Tests for resolve_instruction_sources."""

    def test_resolve_with_workspace_instructions(self, tmp_path: Path) -> None:
        """Resolve workspace-level INSTRUCTIONS.md."""
        # Create workspace with .kora/INSTRUCTIONS.md
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        kora_dir = workspace / ".kora"
        kora_dir.mkdir()
        instructions_md = kora_dir / "INSTRUCTIONS.md"
        instructions_md.write_text("Workspace-specific rules.", encoding="utf-8")

        user = User(id="user_123")

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=workspace,
            user=user,
        )

        # Should have FRAMEWORK + AGENT.md + workspace INSTRUCTIONS.md
        assert len(sources) == 3
        assert sources[0].scope == InstructionScope.FRAMEWORK
        assert sources[1].scope == InstructionScope.AGENT_PACKAGE
        assert sources[1].content == "Base prompt."
        assert sources[2].scope == InstructionScope.WORKSPACE
        assert sources[2].content == "Workspace-specific rules."

    def test_resolve_without_workspace_instructions(self, tmp_path: Path) -> None:
        """Resolve without workspace instructions (file doesn't exist)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # No .kora directory

        user = User(id="user_123")

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=workspace,
            user=user,
        )

        # Should have FRAMEWORK + AGENT.md
        assert len(sources) == 2
        assert sources[0].scope == InstructionScope.FRAMEWORK
        assert sources[1].scope == InstructionScope.AGENT_PACKAGE

    def test_skill_catalog_not_injected_by_default(self, tmp_path: Path) -> None:
        """Discovered skills stay host-side unless explicitly requested."""
        user = User(id="user_123")
        skill = MagicMock()
        skill.name = "code-review"
        skill.description = "Review code changes."

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=tmp_path,
            user=user,
            discovered_skills=[skill],
            active_skills=[],
        )

        assert all("Available Skills" not in source.content for source in sources)

    def test_skill_catalog_injected_when_enabled(self, tmp_path: Path) -> None:
        """Catalog injection should include routing guidance when enabled."""
        user = User(id="user_123")
        skill = MagicMock()
        skill.name = "code-review"
        skill.description = "Review code changes."

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=tmp_path,
            user=user,
            discovered_skills=[skill],
            active_skills=[],
            include_skill_catalog=True,
        )

        catalog_source = next(s for s in sources if "Available Skills" in s.content)
        assert "request_skill_activation" in catalog_source.content
        assert "code-review" in catalog_source.content


class TestLoadAgentPackage:
    """Tests for load_agent_package."""

    def test_load_agent_package_basic(self, tmp_path: Path) -> None:
        """Load an agent package with only AGENT.md."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text("""---
name: test-agent
version: 1.0.0
description: A test agent
---

You are a test assistant.
""", encoding="utf-8")

        package = load_agent_package(tmp_path)

        assert package.name == "test-agent"
        assert package.version == "1.0.0"
        assert package.description == "A test agent"
        assert package.agent_md == "You are a test assistant."
        assert package.config is None
        assert len(package.instructions) == 0

    def test_load_agent_package_with_config(self, tmp_path: Path) -> None:
        """Load an agent package with config.yaml."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text("""---
name: test-agent
---

Base prompt.
""", encoding="utf-8")

        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("""model:
  provider: openai
  name: gpt-4

instructions:
  include:
    - instructions/coding.md
""", encoding="utf-8")

        # Create instructions directory and file
        instructions_dir = tmp_path / "instructions"
        instructions_dir.mkdir()
        coding_md = instructions_dir / "coding.md"
        coding_md.write_text("Coding guidelines.", encoding="utf-8")

        package = load_agent_package(tmp_path)

        assert package.name == "test-agent"
        assert package.config is not None
        assert package.config.model_provider == "openai"
        assert package.config.model_name == "gpt-4"
        assert len(package.instructions) == 1
        assert package.instructions[0].content == "Coding guidelines."

    def test_load_agent_package_missing_agent_md(self, tmp_path: Path) -> None:
        """Error when AGENT.md is missing."""
        with pytest.raises(FileNotFoundError):
            load_agent_package(tmp_path)

    def test_load_agent_package_defaults_name_from_dir(self, tmp_path: Path) -> None:
        """Agent name defaults to directory name."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text("""---
version: 0.1.0
---

Prompt.
""", encoding="utf-8")

        package = load_agent_package(tmp_path)

        # Name should default to directory name
        assert package.name == tmp_path.name
