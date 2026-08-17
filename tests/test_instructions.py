"""
Tests for instruction layer (ADR-007).
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quenda.host.instructions import (
    FRAMEWORK_CONTRACT,
    InstructionScope,
    InstructionSource,
    TemplateContext,
    InstructionComposer,
    resolve_instruction_sources,
    resolve_identity_files,
    resolve_prompt_sources,
)
from quenda.host.loader import AgentConfigYaml, load_agent_package
from quenda.host.identity import User
from quenda.runtime.temporal import TemporalContext


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


def test_framework_contract_is_runtime_guidance_not_embedded_documentation() -> None:
    assert "user-workspace skills" in FRAMEWORK_CONTRACT
    assert "loaded on demand" in FRAMEWORK_CONTRACT
    assert "providers:" in FRAMEWORK_CONTRACT
    assert "type: llama-server" in FRAMEWORK_CONTRACT
    assert "models.default" in FRAMEWORK_CONTRACT
    assert "apply_agent_config_patch" in FRAMEWORK_CONTRACT
    assert "explain_agent_config" in FRAMEWORK_CONTRACT
    assert "exact scheme/host/port" in FRAMEWORK_CONTRACT
    assert "any number of category directories" in FRAMEWORK_CONTRACT
    assert "SKILL.md Schema" not in FRAMEWORK_CONTRACT
    assert len(FRAMEWORK_CONTRACT) < 2_400


def test_prompt_source_resolution_orders_mode_and_deduplicates_extensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_home = tmp_path / "agent"
    instruction_dir = agent_home / "instructions"
    instruction_dir.mkdir(parents=True)
    (instruction_dir / "mode-code.md").write_text(
        "Code mode.", encoding="utf-8"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_instruction = workspace / "QUENDA.md"
    project_instruction.write_text("Project source.", encoding="utf-8")

    sources = resolve_prompt_sources(
        agent_package_path=agent_home,
        agent_name="test-agent",
        agent_md_content="Agent source.",
        agent_instructions=[],
        workspace_path=workspace,
        user=User(id="test-user"),
        workspace_id="ws-test",
        mode="code",
        additional_sources=[
            InstructionSource(
                scope=InstructionScope.WORKSPACE_AGENT,
                content="Duplicate supplied by an extension.",
                path=project_instruction,
            )
        ],
    )

    contents = [source.content for source in sources]
    assert contents.index("Code mode.") < contents.index("Project source.")
    assert "Duplicate supplied by an extension." not in contents
    assert [source.scope for source in sources] == sorted(
        source.scope for source in sources
    )


def test_identity_and_soul_are_independent_sources(
    tmp_path: Path,
) -> None:
    soul = tmp_path / "SOUL.md"
    soul.write_text("legacy", encoding="utf-8")
    assert resolve_identity_files(tmp_path) == (soul,)

    identity = tmp_path / "IDENTITY.md"
    identity.write_text("preferred", encoding="utf-8")
    assert resolve_identity_files(tmp_path) == (identity, soul)


class TestTemplateContext:
    """Tests for TemplateContext."""

    def test_context_creation(self) -> None:
        """Create a template context."""
        context = TemplateContext(
            agent_name="quenda-code",
            agent_version="0.1.0",
            workspace_id="ws_abc123",
            workspace_path="/home/user/project",
            user_id="user_123",
            model_provider="deepseek",
            model_name="deepseek-v4-flash",
            date="2024-01-15",
            session_id="session_xyz",
        )
        assert context.agent_name == "quenda-code"
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
            agent_name="quenda-code",
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
        assert result == "Agent: quenda-code, Workspace: ws_123"

    def test_render_template_all_variables(self) -> None:
        """Render all whitelisted variables."""
        context = TemplateContext(
            agent_name="quenda-code",
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

        assert "Agent: quenda-code v1.0.0" in result
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

    def test_temporal_context_is_injected_at_framework_scope(self, tmp_path: Path) -> None:
        temporal = TemporalContext(
            local_datetime="2026-07-26T00:05:00+08:00",
            local_date="2026-07-26",
            timezone_name="Asia/Shanghai",
            utc_offset="+08:00",
            utc_datetime="2026-07-25T16:05:00+00:00",
        )

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=tmp_path,
            user=User(id="user_123"),
            temporal_context=temporal,
        )

        assert sources[1].scope is InstructionScope.FRAMEWORK
        assert "Current local date: 2026-07-26" in sources[1].content
        assert "Timezone: Asia/Shanghai" in sources[1].content

    def test_resolve_with_workspace_instructions(self, tmp_path: Path) -> None:
        """Resolve workspace-level INSTRUCTIONS.md."""
        # Create workspace with .quenda/INSTRUCTIONS.md
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        quenda_dir = workspace / ".quenda"
        quenda_dir.mkdir()
        instructions_md = quenda_dir / "INSTRUCTIONS.md"
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

        assert [source.scope for source in sources] == [
            InstructionScope.FRAMEWORK,
            InstructionScope.FRAMEWORK,
            InstructionScope.AGENT_PACKAGE,
            InstructionScope.WORKSPACE,
        ]
        assert "Current Agent Identity" in sources[1].content
        assert sources[2].content == "Base prompt."
        assert sources[3].content == "Workspace-specific rules."

    def test_default_quenda_md_loads_from_all_three_user_scopes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """QUENDA.md is discovered at user, project, and user-project scopes."""
        home = tmp_path / "home"
        workspace = tmp_path / "project"
        workspace.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        user_root = home / ".quenda" / "users" / "user_123"
        user_root.mkdir(parents=True)
        (user_root / "QUENDA.md").write_text("User rules.", encoding="utf-8")
        (workspace / "QUENDA.md").write_text("Project rules.", encoding="utf-8")
        project_quenda = workspace / ".quenda"
        project_quenda.mkdir()
        (project_quenda / "QUENDA.md").write_text(
            "Project .quenda rules.", encoding="utf-8"
        )
        user_workspace = user_root / "workspaces" / "ws_123"
        user_workspace.mkdir(parents=True)
        (user_workspace / "QUENDA.md").write_text(
            "User-project rules.", encoding="utf-8"
        )

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=workspace,
            workspace_id="ws_123",
            user=User(id="user_123"),
        )

        scoped_contents = [
            source.content
            for source in sources
            if source.scope
            in {
                InstructionScope.USER_GLOBAL,
                InstructionScope.WORKSPACE,
                InstructionScope.USER_WORKSPACE,
            }
        ]
        assert scoped_contents == [
            "User rules.",
            "Project rules.",
            "Project .quenda rules.",
            "User-project rules.",
        ]
        assert sources[-1].scope is InstructionScope.USER_WORKSPACE

    def test_multiple_configured_instruction_filenames_preserve_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every configured filename is loaded in declaration order."""
        home = tmp_path / "home"
        workspace = tmp_path / "project"
        workspace.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        for name in ("TEAM.md", "AGENTS.md"):
            (workspace / name).write_text(name, encoding="utf-8")

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=workspace,
            workspace_id="ws_123",
            user=User(id="user_123"),
            instruction_files=["TEAM.md", "AGENTS.md"],
        )

        assert [
            source.content
            for source in sources
            if source.scope is InstructionScope.WORKSPACE
        ] == ["TEAM.md", "AGENTS.md"]

    def test_resolve_without_workspace_instructions(self, tmp_path: Path) -> None:
        """Resolve without workspace instructions (file doesn't exist)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # No .quenda directory

        user = User(id="user_123")

        sources = resolve_instruction_sources(
            agent_package_path=tmp_path / "agent",
            agent_name="test-agent",
            agent_md_content="Base prompt.",
            agent_instructions=[],
            workspace_path=workspace,
            user=user,
        )

        assert [source.scope for source in sources] == [
            InstructionScope.FRAMEWORK,
            InstructionScope.FRAMEWORK,
            InstructionScope.AGENT_PACKAGE,
        ]

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

    def test_skill_catalog_is_compact_but_keeps_routing_metadata(
        self, tmp_path: Path
    ) -> None:
        """Long frontmatter descriptions do not become permanent prompt payload."""
        user = User(id="user_123")
        skill = MagicMock()
        skill.name = "develop-presentation"
        skill.description = (
            "Create and revise complete presentation workflows. "
            + "Detailed trigger guidance that belongs in the skill itself. " * 20
        )

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

        catalog = next(s.content for s in sources if "Available Skills" in s.content)
        assert "develop-presentation" in catalog
        assert "Create and revise complete presentation workflows." in catalog
        assert len(catalog) < 700


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

    def test_instruction_files_default_and_configuration(self, tmp_path: Path) -> None:
        """Agent config defaults to QUENDA.md and accepts multiple filenames."""
        default = AgentConfigYaml.from_dict({})
        configured = AgentConfigYaml.from_dict(
            {"instruction_files": ["TEAM.md", "AGENTS.md"]}
        )

        assert default.instruction_files == ["QUENDA.md"]
        assert configured.instruction_files == ["TEAM.md", "AGENTS.md"]

    @pytest.mark.parametrize("filename", ["../QUENDA.md", "docs/QUENDA.md", "/QUENDA.md"])
    def test_instruction_files_reject_paths(self, filename: str) -> None:
        """Configured entries cannot escape or introduce nested search paths."""
        with pytest.raises(ValueError, match="filenames, not paths"):
            AgentConfigYaml.from_dict({"instruction_files": [filename]})

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

instruction_files:
  - QUENDA.md
  - AGENTS.md
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
        assert package.config.instruction_files == ["QUENDA.md", "AGENTS.md"]
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
