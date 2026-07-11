"""
Tests for skill activation.
"""

import pytest
from pathlib import Path

from quenda.host.skill import SkillDiscovery, SkillActivator, SkillPackage


class TestSkillActivator:
    """Tests for SkillActivator class."""

    @pytest.fixture
    def activator(self, tmp_path: Path) -> SkillActivator:
        """Create an activator with test skills."""
        # Create multiple skills
        for i in range(2):
            skill_dir = tmp_path / "skills" / f"skill-{i}"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: skill-{i}
description: Skill {i}
---
# Instructions {i}
Content for skill {i}.
""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        return SkillActivator(discovery)

    def test_activate_skill(self, activator: SkillActivator) -> None:
        """Test basic skill activation."""
        skill = activator.activate_skill("skill-0")

        assert skill is not None
        assert skill.active
        assert skill in activator.active_skills
        assert activator.is_active("skill-0")

    def test_activate_nonexistent_skill(self, activator: SkillActivator) -> None:
        """Test activating a non-existent skill."""
        skill = activator.activate_skill("nonexistent")

        assert skill is None
        assert len(activator.active_skills) == 0

    def test_activate_same_skill_twice(self, activator: SkillActivator) -> None:
        """Test that activating same skill twice doesn't duplicate."""
        activator.activate_skill("skill-0")
        activator.activate_skill("skill-0")

        assert len(activator.active_skills) == 1

    def test_deactivate_skill(self, activator: SkillActivator) -> None:
        """Test skill deactivation."""
        activator.activate_skill("skill-0")
        result = activator.deactivate_skill("skill-0")

        assert result is True
        assert len(activator.active_skills) == 0
        assert not activator.is_active("skill-0")

    def test_deactivate_nonexistent_skill(self, activator: SkillActivator) -> None:
        """Test deactivating a non-active skill."""
        result = activator.deactivate_skill("skill-0")

        assert result is False

    def test_multiple_active_skills(self, activator: SkillActivator) -> None:
        """Test having multiple skills active."""
        activator.activate_skill("skill-0")
        activator.activate_skill("skill-1")

        assert len(activator.active_skills) == 2
        assert activator.is_active("skill-0")
        assert activator.is_active("skill-1")

    def test_get_active_instructions_empty(self, activator: SkillActivator) -> None:
        """Test instruction composition with no active skills."""
        instructions = activator.get_active_instructions()

        assert instructions == ""

    def test_get_active_instructions_single(self, activator: SkillActivator) -> None:
        """Test instruction composition with one skill."""
        activator.activate_skill("skill-0")
        instructions = activator.get_active_instructions()

        assert "skill-0" in instructions
        assert "Content for skill 0" in instructions
        assert "<Skill:skill-0>" in instructions

    def test_get_active_instructions_multiple(self, activator: SkillActivator) -> None:
        """Test instruction composition with multiple skills."""
        activator.activate_skill("skill-0")
        activator.activate_skill("skill-1")
        instructions = activator.get_active_instructions()

        assert "skill-0" in instructions
        assert "skill-1" in instructions
        assert "Content for skill 0" in instructions
        assert "Content for skill 1" in instructions

    def test_instruction_order_matches_activation_order(self, activator: SkillActivator) -> None:
        """Test that instructions appear in activation order."""
        activator.activate_skill("skill-1")
        activator.activate_skill("skill-0")
        instructions = activator.get_active_instructions()

        # skill-1 should appear before skill-0
        pos_1 = instructions.find("skill-1")
        pos_0 = instructions.find("skill-0")
        assert pos_1 < pos_0

    def test_list_active(self, activator: SkillActivator) -> None:
        """Test listing active skills."""
        assert activator.list_active() == []

        activator.activate_skill("skill-0")
        assert activator.list_active() == ["skill-0"]

        activator.activate_skill("skill-1")
        assert activator.list_active() == ["skill-0", "skill-1"]

    def test_clear(self, activator: SkillActivator) -> None:
        """Test clearing all active skills."""
        activator.activate_skill("skill-0")
        activator.activate_skill("skill-1")

        activator.clear()

        assert len(activator.active_skills) == 0
        assert not activator.is_active("skill-0")
        assert not activator.is_active("skill-1")

    def test_transient_activation_is_tracked_separately(self, activator: SkillActivator) -> None:
        """Model-selected skills should be transient by default."""
        activator.activate_skill("skill-0", transient=True)

        assert activator.is_active("skill-0")
        assert activator.list_transient() == ["skill-0"]
        assert activator.list_persistent() == []
        assert activator.list_active() == ["skill-0"]

    def test_clear_transient_keeps_persistent_skills(self, activator: SkillActivator) -> None:
        """Clearing transient skills should not affect persistent ones."""
        activator.activate_skill("skill-0")
        activator.activate_skill("skill-1", transient=True)

        activator.clear_transient()

        assert activator.list_persistent() == ["skill-0"]
        assert activator.list_transient() == []
        assert activator.list_active() == ["skill-0"]
        assert activator.is_active("skill-0")
        assert not activator.is_active("skill-1")

    def test_skill_active_flag_synced(self, activator: SkillActivator) -> None:
        """Test that skill.active flag is set during activation.

        Note (ADR-025): skill.active is a convenience flag, not the source of truth.
        The authoritative state is active_skill_names. Discovery may cache skill
        objects, so the active flag on a cached object may persist across
        deactivation. Use is_active() to check authoritative state.
        """
        skill = activator.activate_skill("skill-0")
        assert skill is not None
        assert skill.active is True

        # Verify authoritative state
        assert activator.is_active("skill-0")
        assert "skill-0" in activator.active_skill_names

        activator.deactivate_skill("skill-0")

        # Authoritative state is updated
        assert not activator.is_active("skill-0")
        assert "skill-0" not in activator.active_skill_names

        # Note: The cached skill object may still have active=True due to caching.
        # This is acceptable because is_active() is the authoritative check.


class TestSkillActivationWithDiscovery:
    """Tests for activation with real discovery scenarios."""

    @pytest.fixture
    def workspace_with_skills(self, tmp_path: Path) -> Path:
        """Create workspace with various skill configurations."""
        # Skill with resources in references/ directory
        skill_dir = tmp_path / "skills" / "code-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: code-review
description: Code review skill
---
# Code Review

When reviewing code:
1. Check style
2. Check tests
3. Check documentation
""")
        references = skill_dir / "references"
        references.mkdir()
        (references / "checklist.md").write_text("- [ ] Style check\n- [ ] Test check")

        # Skill without resources
        skill_dir2 = tmp_path / "skills" / "testing"
        skill_dir2.mkdir(parents=True)
        (skill_dir2 / "SKILL.md").write_text("""---
name: testing
description: Testing skill
---
# Testing

Focus on test coverage and quality.
""")

        return tmp_path

    def test_skill_with_resources(
        self, workspace_with_skills: Path
    ) -> None:
        """Test skill that has resources auto-discovered from references/."""
        discovery = SkillDiscovery(user_workspace_skills_path=workspace_with_skills / "skills")
        skill = discovery.get_skill("code-review")

        assert skill is not None
        assert len(skill.resources) == 1
        assert skill.resources[0].path.name == "checklist.md"
        assert skill.resources[0].type == "reference"

    def test_skill_without_resources(
        self, workspace_with_skills: Path
    ) -> None:
        """Test skill without resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=workspace_with_skills / "skills")
        skill = discovery.get_skill("testing")

        assert skill is not None
        assert len(skill.resources) == 0

    def test_activation_loads_instructions_lazily(
        self, workspace_with_skills: Path
    ) -> None:
        """Test that activation triggers instruction loading."""
        discovery = SkillDiscovery(user_workspace_skills_path=workspace_with_skills / "skills")
        activator = SkillActivator(discovery)

        skill = activator.activate_skill("code-review")
        assert skill is not None

        # Instructions should be loaded when we access them
        instructions = activator.get_active_instructions()
        assert "Code Review" in instructions
        assert "Check style" in instructions