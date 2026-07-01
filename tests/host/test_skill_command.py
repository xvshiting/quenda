"""
Tests for SkillCommand in the slash command system.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from kora.host.commands import (
    CommandContext,
    CommandResult,
    SkillCommand,
)
from kora.host.skill import SkillDiscovery, SkillActivator


class TestSkillCommand:
    """Tests for SkillCommand class."""

    @pytest.fixture
    def skill_workspace(self, tmp_path: Path) -> Path:
        """Create a user-workspace skills directory with test skills."""
        skill_dir = tmp_path / "skills" / "code-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: code-review
description: Code review skill
kora:
  resources:
    references:
      - path: "checklist.md"
---
# Code Review
Perform code review.
""")
        (skill_dir / "checklist.md").write_text("# Checklist")

        skill_dir2 = tmp_path / "skills" / "testing"
        skill_dir2.mkdir(parents=True)
        (skill_dir2 / "SKILL.md").write_text("""---
name: testing
description: Testing skill
---
# Testing
Focus on tests.
""")

        return tmp_path

    @pytest.fixture
    def command_context(
        self,
        skill_workspace: Path,
    ) -> CommandContext:
        """Create a CommandContext with skill support."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_workspace / "skills")
        activator = SkillActivator(discovery)

        # Mock session
        session = MagicMock()
        session.state.metadata = {}

        return CommandContext(
            session=session,
            skill_discovery=discovery,
            skill_activator=activator,
            workspace_path=skill_workspace,
        )

    def test_list_skills(self, command_context: CommandContext) -> None:
        """Test listing available skills."""
        cmd = SkillCommand()
        result = cmd.execute("list", command_context)

        assert result.status == "ok"
        assert "code-review" in result.message
        assert "testing" in result.message

    def test_list_skills_empty(self, tmp_path: Path) -> None:
        """Test listing skills when none available."""
        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        activator = SkillActivator(discovery)

        session = MagicMock()
        session.state.metadata = {}

        context = CommandContext(
            session=session,
            skill_discovery=discovery,
            skill_activator=activator,
            workspace_path=tmp_path,
        )

        cmd = SkillCommand()
        result = cmd.execute("list", context)

        assert result.status == "ok"
        assert "No skills found" in result.message

    def test_activate_skill(self, command_context: CommandContext) -> None:
        """Test activating a skill."""
        cmd = SkillCommand()

        # Initially not active
        assert not command_context.skill_activator.is_active("code-review")

        result = cmd.execute("activate code-review", command_context)

        assert result.status == "ok"
        assert "Activated" in result.message
        assert "code-review" in result.message
        assert command_context.skill_activator.is_active("code-review")
        assert result.rebuild_context is True

    def test_activate_already_active_skill(
        self, command_context: CommandContext
    ) -> None:
        """Test activating a skill that's already active."""
        cmd = SkillCommand()

        # Activate first
        cmd.execute("activate code-review", command_context)

        # Activate again
        result = cmd.execute("activate code-review", command_context)

        assert result.status == "ok"
        assert "already active" in result.message

    def test_activate_skill_state_patch_ignores_transient_skills(
        self, command_context: CommandContext
    ) -> None:
        """Persistent state patches should not accidentally persist transient skills."""
        cmd = SkillCommand()
        command_context.skill_activator.activate_skill("testing", transient=True)

        result = cmd.execute("activate code-review", command_context)

        assert result.state_patch is not None
        assert result.state_patch["skills"] == ["code-review"]

    def test_activate_nonexistent_skill(
        self, command_context: CommandContext
    ) -> None:
        """Test activating a skill that doesn't exist."""
        cmd = SkillCommand()
        result = cmd.execute("activate nonexistent", command_context)

        assert result.status == "error"
        assert "not found" in result.message

    def test_deactivate_skill(self, command_context: CommandContext) -> None:
        """Test deactivating a skill."""
        cmd = SkillCommand()

        # Activate first
        cmd.execute("activate code-review", command_context)
        assert command_context.skill_activator.is_active("code-review")

        # Deactivate
        result = cmd.execute("deactivate code-review", command_context)

        assert result.status == "ok"
        assert "Deactivated" in result.message
        assert not command_context.skill_activator.is_active("code-review")
        assert result.rebuild_context is True

    def test_deactivate_skill_state_patch_ignores_remaining_transient_skills(
        self, command_context: CommandContext
    ) -> None:
        """Persistent state patches should remain persistent-only after deactivation."""
        cmd = SkillCommand()
        cmd.execute("activate code-review", command_context)
        command_context.skill_activator.activate_skill("testing", transient=True)

        result = cmd.execute("deactivate code-review", command_context)

        assert result.state_patch is not None
        assert result.state_patch["skills"] == []

    def test_deactivate_non_active_skill(
        self, command_context: CommandContext
    ) -> None:
        """Test deactivating a skill that's not active."""
        cmd = SkillCommand()
        result = cmd.execute("deactivate code-review", command_context)

        assert result.status == "error"
        assert "not active" in result.message

    def test_list_resources(self, command_context: CommandContext) -> None:
        """Test listing resources from active skills."""
        cmd = SkillCommand()

        # Activate skill with resources
        cmd.execute("activate code-review", command_context)

        result = cmd.execute("resources", command_context)

        assert result.status == "ok"
        assert "checklist.md" in result.message
        assert "code-review" in result.message

    def test_list_resources_no_skills_active(
        self, command_context: CommandContext
    ) -> None:
        """Test listing resources when no skills active."""
        cmd = SkillCommand()
        result = cmd.execute("resources", command_context)

        assert result.status == "ok"
        assert "No skills active" in result.message

    def test_get_candidates_subcommands(
        self, command_context: CommandContext
    ) -> None:
        """Test getting subcommand candidates."""
        cmd = SkillCommand()
        candidates = cmd.get_candidates("", command_context)

        subcommands = [c.value for c in candidates]
        assert "list" in subcommands
        assert "activate" in subcommands
        assert "deactivate" in subcommands
        assert "resources" in subcommands

    def test_get_candidates_skill_names(
        self, command_context: CommandContext
    ) -> None:
        """Test getting skill name candidates for activate."""
        cmd = SkillCommand()
        candidates = cmd.get_candidates("activate ", command_context)

        names = [c.value for c in candidates]
        assert "code-review" in names
        assert "testing" in names

    def test_get_candidates_active_skills_only(
        self, command_context: CommandContext
    ) -> None:
        """Test that deactivate only shows active skills."""
        cmd = SkillCommand()

        # Activate one skill
        cmd.execute("activate code-review", command_context)

        candidates = cmd.get_candidates("deactivate ", command_context)

        names = [c.value for c in candidates]
        assert "code-review" in names
        assert "testing" not in names  # Not active

    def test_resolve_empty_args(self, command_context: CommandContext) -> None:
        """Test resolving empty args."""
        cmd = SkillCommand()
        resolution = cmd.resolve("", command_context)

        assert resolution.status == "needs_input"
        assert len(resolution.candidates) > 0

    def test_resolve_valid_subcommand(
        self, command_context: CommandContext
    ) -> None:
        """Test resolving valid subcommand."""
        cmd = SkillCommand()
        resolution = cmd.resolve("list", command_context)

        assert resolution.status == "ready"
        assert resolution.normalized_args == "list"

    def test_resolve_activate_needs_skill(
        self, command_context: CommandContext
    ) -> None:
        """Test resolve shows candidates when activate needs skill name."""
        cmd = SkillCommand()
        resolution = cmd.resolve("activate", command_context)

        assert resolution.status == "needs_input"
        assert len(resolution.candidates) > 0

    def test_resolve_activate_with_skill(
        self, command_context: CommandContext
    ) -> None:
        """Test resolve with complete activate command."""
        cmd = SkillCommand()
        resolution = cmd.resolve("activate code-review", command_context)

        assert resolution.status == "ready"
        assert "code-review" in resolution.normalized_args

    def test_unknown_subcommand(self, command_context: CommandContext) -> None:
        """Test unknown subcommand."""
        cmd = SkillCommand()
        result = cmd.execute("unknown", command_context)

        assert result.status == "error"
        assert "Unknown subcommand" in result.message

    def test_no_skill_system(self, tmp_path: Path) -> None:
        """Test command when skill system not initialized."""
        session = MagicMock()
        session.state.metadata = {}

        context = CommandContext(
            session=session,
            skill_discovery=None,
            skill_activator=None,
            workspace_path=tmp_path,
        )

        cmd = SkillCommand()
        result = cmd.execute("list", context)

        assert result.status == "ok"
        assert "No skills configured" in result.message
