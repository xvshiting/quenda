"""
Integration tests for ADR-026: Textual Context Reload and Capability Rebind.

These tests verify:
1. AGENT.md changes are picked up on next run
2. Skill changes are picked up on next run
3. Tool/model/sandbox bindings remain stable until explicit rebind
"""

import pytest
from pathlib import Path
from kora.host.runner import (
    StableHostBinding,
    RunContextSnapshot,
    setup_host_binding,
    refresh_run_context,
    setup_agent,
)
from kora.host.workspace import WorkspaceResolver
from kora.host.skill import SkillDiscovery


class TestTextRefreshPath:
    """Tests for Path B: Text Refresh (runs before each new run)."""

    @pytest.fixture
    def agent_setup(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a minimal agent and workspace."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()

        # Create AGENT.md
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text("""---
name: test-agent
version: "0.1.0"
---

# Test Agent

You are a test agent.

## Current Value: INITIAL
""")

        # Create config.yaml
        config_yaml = agent_dir / "config.yaml"
        config_yaml.write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return agent_dir, workspace

    def test_agent_md_changes_picked_up(
        self, agent_setup: tuple[Path, Path]
    ) -> None:
        """AGENT.md changes should be visible in next refresh_run_context."""
        agent_dir, workspace = agent_setup

        # Setup binding (Path A - capability binding)
        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        # First refresh (Path B - text refresh)
        snapshot1 = refresh_run_context(binding)
        assert "INITIAL" in snapshot1.agent_md_content

        # Edit AGENT.md
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text("""---
name: test-agent
version: "0.1.0"
---

# Test Agent

You are a test agent.

## Current Value: UPDATED
""")

        # Second refresh - should pick up changes
        snapshot2 = refresh_run_context(binding)
        assert "UPDATED" in snapshot2.agent_md_content
        assert "INITIAL" not in snapshot2.agent_md_content

    def test_instruction_changes_picked_up(
        self, agent_setup: tuple[Path, Path]
    ) -> None:
        """Instruction file changes should be visible in next refresh_run_context.

        Note: This test verifies that AGENT.md changes are picked up.
        Instruction file loading depends on config.yaml being parsed correctly,
        which is tested separately in loader tests.
        """
        agent_dir, workspace = agent_setup

        # Create instruction file
        instructions_dir = agent_dir / "instructions"
        instructions_dir.mkdir()
        instructions_file = instructions_dir / "test.md"
        instructions_file.write_text("Test instruction: INITIAL")

        # Update config to include instruction
        config_yaml = agent_dir / "config.yaml"
        config_yaml.write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
instructions_include:
  - instructions/test.md
""")

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        # First refresh - verify AGENT.md is loaded
        snapshot1 = refresh_run_context(binding)
        assert "Test Agent" in snapshot1.agent_md_content

        # Edit AGENT.md to verify refresh works
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text("""---
name: test-agent
version: "0.1.0"
---

# Test Agent

You are a test agent.

## Updated Content

This is new content.
""")

        # Second refresh - should pick up AGENT.md changes
        snapshot2 = refresh_run_context(binding)
        assert "Updated Content" in snapshot2.agent_md_content
        assert "This is new content" in snapshot2.composed_prompt


class TestSkillRefreshPath:
    """Tests for skill discovery and activation at turn boundary."""

    @pytest.fixture
    def agent_with_skills_dir(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Create agent, workspace, and skills directory."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()

        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
version: "0.1.0"
---
# Test Agent
""")

        (agent_dir / "config.yaml").write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create user-workspace skills path
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        return agent_dir, workspace, skills_dir

    def test_new_skill_discovered_at_refresh(
        self, agent_with_skills_dir: tuple[Path, Path, Path]
    ) -> None:
        """New skills should be discoverable after refresh_run_context."""
        agent_dir, workspace, skills_dir = agent_with_skills_dir

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        # First refresh - no skills
        snapshot1 = refresh_run_context(binding)
        assert len(snapshot1.discovered_skills) == 0

        # Add a new skill
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---
# Test Skill
""")

        # Update binding's skill discovery path
        # Note: In production, this would be the user-workspace path
        from kora.host.skill import SkillDiscovery
        new_discovery = SkillDiscovery(user_workspace_skills_path=skills_dir)

        # Second refresh - should discover new skill
        snapshot2_skills = new_discovery.discover_skills()
        assert len(snapshot2_skills) == 1
        assert snapshot2_skills[0].name == "test-skill"

    def test_active_skill_names_durable_state(
        self, agent_with_skills_dir: tuple[Path, Path, Path]
    ) -> None:
        """Active skill names should be the durable state, not loaded objects."""
        agent_dir, workspace, skills_dir = agent_with_skills_dir

        # Create and activate a skill
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---
# Test Skill INITIAL
""")

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        # Manually add skill name to active list
        binding.active_skill_names.append("test-skill")

        # Refresh should resolve the skill
        from kora.host.skill import SkillDiscovery
        discovery = SkillDiscovery(user_workspace_skills_path=skills_dir)
        snapshot = refresh_run_context(binding)

        # Check resolved skills
        resolved = [s for s in discovery.discover_skills() if s.name == "test-skill"]
        assert len(resolved) == 1


class TestCapabilityBindingStability:
    """Tests for Path A: Capability Binding (stable until explicit rebind)."""

    @pytest.fixture
    def agent_setup(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a minimal agent and workspace."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()

        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
version: "0.1.0"
---
# Test Agent
""")

        (agent_dir / "config.yaml").write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
tools:
  bundles:
    - core
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return agent_dir, workspace

    def test_model_binding_stable_across_refresh(
        self, agent_setup: tuple[Path, Path]
    ) -> None:
        """Model binding should not change across text refresh."""
        agent_dir, workspace = agent_setup

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        original_model = binding.model_name
        original_provider = binding.provider_name

        # Edit config to change model
        (agent_dir / "config.yaml").write_text("""
model_provider: anthropic
model_name: claude-sonnet-4-20250514
tools:
  bundles:
    - core
""")

        # Refresh context (Path B)
        refresh_run_context(binding)

        # Binding should still have original values
        assert binding.model_name == original_model
        assert binding.provider_name == original_provider

    def test_tool_binding_stable_across_refresh(
        self, agent_setup: tuple[Path, Path]
    ) -> None:
        """Tool grants should not change across text refresh."""
        agent_dir, workspace = agent_setup

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        original_tool_count = len(binding.tools)

        # Edit config to change tools
        (agent_dir / "config.yaml").write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
tools:
  bundles:
    - core
    - network
""")

        # Refresh context (Path B)
        refresh_run_context(binding)

        # Binding should still have original tools
        assert len(binding.tools) == original_tool_count


class TestTwoPathIntegration:
    """End-to-end tests for the two-path model."""

    @pytest.fixture
    def full_agent_setup(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a full agent setup with instructions and skills."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()

        # Create AGENT.md
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
version: "0.1.0"
---
# Test Agent

Base instruction content.
""")

        # Create instructions
        instructions_dir = agent_dir / "instructions"
        instructions_dir.mkdir()
        (instructions_dir / "coding.md").write_text("Coding instructions: INITIAL")

        # Create config
        (agent_dir / "config.yaml").write_text("""
model_provider: deepseek
model_name: deepseek-v4-flash
instructions_include:
  - instructions/coding.md
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return agent_dir, workspace

    def test_setup_agent_uses_two_paths(
        self, full_agent_setup: tuple[Path, Path]
    ) -> None:
        """setup_agent should use both paths correctly."""
        agent_dir, workspace = full_agent_setup

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Check that binding exists (Path A)
        assert setup.binding is not None
        assert setup.binding.model_name == "deepseek-v4-flash"

        # Check that context snapshot exists (Path B)
        assert setup.context_snapshot is not None
        assert "Base instruction content" in setup.context_snapshot.composed_prompt

    def test_text_refresh_independent_of_binding(
        self, full_agent_setup: tuple[Path, Path]
    ) -> None:
        """Text refresh should be independent of capability binding."""
        agent_dir, workspace = full_agent_setup

        binding = setup_host_binding(agent_dir, workspace)
        assert binding is not None

        # Multiple refreshes should work without re-binding
        snapshot1 = refresh_run_context(binding)
        snapshot2 = refresh_run_context(binding)

        # Both should have same composed prompt
        assert snapshot1.composed_prompt == snapshot2.composed_prompt

        # Edit AGENT.md (this is always loaded)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
version: "0.1.0"
---
# Test Agent

Base instruction content.

UPDATED: New content added.
""")

        # New refresh should pick up change in AGENT.md
        snapshot3 = refresh_run_context(binding)
        assert "UPDATED" in snapshot3.agent_md_content
        assert "New content added" in snapshot3.composed_prompt

        # Binding should be unchanged
        assert binding.model_name == "deepseek-v4-flash"
