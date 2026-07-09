"""
End-to-end tests for Skills framework.

Tests the complete flow from skill discovery to instruction composition.
"""

import pytest
from pathlib import Path

from quenda.host.runner import setup_agent, AgentSetup
from quenda.host.skill import (
    SkillDiscovery,
    SkillActivator,
    ResourceResolver,
)
from quenda.host.instructions import InstructionScope, FRAMEWORK_CONTRACT


class TestSkillsE2E:
    """End-to-end tests for Skills framework."""

    @pytest.fixture
    def complete_workspace(self, tmp_path: Path) -> Path:
        """Create a complete workspace with agent and skills."""
        # Create agent package
        agent_dir = tmp_path / "agents" / "dev-agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: dev-agent
version: "1.0.0"
description: Development assistant
---

You are a development assistant.
""")

        (agent_dir / "config.yaml").write_text("""
model:
  provider: deepseek
  name: deepseek-v4-flash

skills:
  - code-review
  - testing
""")

        # Create bundled skills in agent package
        cr_skill = agent_dir / "skills" / "code-review"
        cr_skill.mkdir(parents=True)

        (cr_skill / "SKILL.md").write_text("""---
name: code-review
description: Code review capability
version: "1.0.0"
resources:
  references:
    - path: "guides/style.md"
      description: "Style guide"
  assets:
    - path: "templates/report.md"
      type: template
---
# Code Review

When reviewing code:
1. Check style compliance
2. Verify tests
3. Check documentation
""")

        guides = cr_skill / "guides"
        guides.mkdir()
        (guides / "style.md").write_text("# Style Guide\n\nUse 4 spaces for indentation.")

        templates = cr_skill / "templates"
        templates.mkdir()
        (templates / "report.md").write_text("# Review Report\nAuthor: {{author}}")

        # Create testing skill
        test_skill = agent_dir / "skills" / "testing"
        test_skill.mkdir(parents=True)

        (test_skill / "SKILL.md").write_text("""---
name: testing
description: Testing capability
---
# Testing

Focus on test quality and coverage.
""")

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return tmp_path

    def test_complete_skill_flow(self, complete_workspace: Path) -> None:
        """Test the complete flow from discovery to activation."""
        agent_dir = complete_workspace / "agents" / "dev-agent"
        workspace = complete_workspace / "workspace"

        # 1. Setup agent (includes skill discovery and activation)
        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # 2. Verify skill system initialized
        assert setup.skill_discovery is not None
        assert setup.skill_activator is not None

        # 3. Verify skills discovered
        all_skills = setup.skill_discovery.discover_skills()
        skill_names = {s.name for s in all_skills}
        assert "code-review" in skill_names
        assert "testing" in skill_names

        # 4. Verify default skills activated from config
        active_names = setup.skill_activator.list_active()
        assert "code-review" in active_names
        assert "testing" in active_names

        # 5. Verify instructions composed (skill instructions are included)
        system_prompt = setup.agent.system_prompt
        assert "Code Review" in system_prompt
        assert "Testing" in system_prompt

    def test_skill_resources_e2e(self, complete_workspace: Path) -> None:
        """Test resource access in the complete flow."""
        agent_dir = complete_workspace / "agents" / "dev-agent"
        workspace = complete_workspace / "workspace"

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Access resources
        resolver = ResourceResolver(setup.skill_activator.active_skills)

        # List resources
        resources = resolver.list_resources()
        assert len(resources) >= 1

        # Load a resource
        style_guide = resolver.load_resource("code-review", "style.md")
        assert style_guide is not None
        assert "Style Guide" in style_guide.content

        # Render a template
        report = resolver.render_template(
            "code-review",
            "report.md",
            {"author": "Alice"}
        )
        assert report is not None
        assert "Author: Alice" in report

    def test_manual_skill_activation(self, complete_workspace: Path) -> None:
        """Test manually activating additional skills."""
        agent_dir = complete_workspace / "agents" / "dev-agent"
        workspace = complete_workspace / "workspace"

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Initially 2 skills active
        assert len(setup.skill_activator.active_skills) == 2

        # Deactivate one
        setup.skill_activator.deactivate_skill("testing")
        assert len(setup.skill_activator.active_skills) == 1
        assert not setup.skill_activator.is_active("testing")

        # Reactivate
        skill = setup.skill_activator.activate_skill("testing")
        assert skill is not None
        assert len(setup.skill_activator.active_skills) == 2

    def test_instruction_sources_include_skills(
        self, complete_workspace: Path
    ) -> None:
        """Test that instruction sources include only active skill instructions."""
        agent_dir = complete_workspace / "agents" / "dev-agent"
        workspace = complete_workspace / "workspace"

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Check for skill scope in instruction sources
        skill_sources = [
            s for s in setup.instruction_sources
            if s.scope == InstructionScope.SKILL
        ]
        assert len(skill_sources) == 2
        # Updated for Agent Skills spec structured format
        # Skills are 'code-review' and 'testing' (from config.yaml)
        assert any('<skill_content name="code-review">' in s.content for s in skill_sources)
        assert any('<skill_content name="testing">' in s.content for s in skill_sources)
        assert all("Available Skills" not in s.content for s in skill_sources)

    def test_skill_with_missing_resource(self, tmp_path: Path) -> None:
        """Test skill with a missing resource file."""
        # Create agent with skill activated by default
        agent_dir = tmp_path / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")
        (agent_dir / "config.yaml").write_text("""
skills:
  - broken-skill
""")

        # Create skill referencing missing file
        skill_dir = agent_dir / "skills" / "broken-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: broken-skill
description: Skill with missing resource
resources:
  references:
    - path: "missing.md"
---
# Instructions
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Setup should still succeed
        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Skill should be activated
        assert setup.skill_activator.is_active("broken-skill")

        # Resources are not listed if files don't exist (by design)
        resolver = ResourceResolver(setup.skill_activator.active_skills)
        resources = resolver.list_resources()
        assert len(resources) == 0  # No resources because file doesn't exist

        # Loading should return None
        loaded = resolver.load_resource("broken-skill", "missing.md")
        assert loaded is None

    def test_multiple_workspaces_isolation(self, tmp_path: Path) -> None:
        """Test that skills from different user-workspaces are isolated."""
        # Create agent package
        agent_dir = tmp_path / "agents" / "shared-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: shared-agent
---
Shared agent.
""")

        # Create workspace bindings
        ws1 = tmp_path / "workspace1"
        ws2 = tmp_path / "workspace2"
        ws1.mkdir()
        ws2.mkdir()

        # Each workspace will have its own user-workspace skills path
        # This is determined by workspace_id which is different for each

        # Setup agent for ws1
        setup1 = setup_agent(agent_dir, ws1)
        assert setup1 is not None

        # Setup agent for ws2
        setup2 = setup_agent(agent_dir, ws2)
        assert setup2 is not None

        # They should have different workspace_ids
        assert setup1.workspace_id != setup2.workspace_id

        # Skills paths would be different (user-workspace path)
        # Each user-workspace has its own skills directory

    def test_skill_resources_discovered(self, complete_workspace: Path) -> None:
        """Test that skill resources are properly discovered."""
        agent_dir = complete_workspace / "agents" / "dev-agent"

        # Create empty user-workspace skills path
        user_ws_skills = complete_workspace / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )
        skill = discovery.get_skill("code-review")

        assert skill is not None
        assert len(skill.resources) == 2  # style.md and report.md

    def test_progressive_disclosure_e2e(self, complete_workspace: Path) -> None:
        """Test progressive disclosure in the complete flow."""
        agent_dir = complete_workspace / "agents" / "dev-agent"

        user_ws_skills = complete_workspace / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )

        # 1. Discovery: only frontmatter loaded
        skill = discovery.get_skill("code-review")
        assert skill is not None
        assert skill._instructions is None  # Not yet parsed

        # 2. Access instructions triggers parsing
        instructions = skill.instructions
        assert skill._instructions is not None  # Now parsed
        assert "Code Review" in instructions

        # 3. Usage: resources loaded on demand
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")
        resolver = ResourceResolver([skill])
        guide = resolver.load_resource("code-review", "style.md")
        assert guide is not None
        assert "Style Guide" in guide.content


class TestFrameworkContract:
    """Tests for framework contract inclusion."""

    def test_framework_contract_in_instruction_sources(self, tmp_path: Path) -> None:
        """Test that framework contract is included in instruction sources."""
        # Create minimal agent
        agent_dir = tmp_path / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Framework contract should be first
        assert len(setup.instruction_sources) >= 1
        first_source = setup.instruction_sources[0]
        assert first_source.scope == InstructionScope.FRAMEWORK

    def test_framework_contract_contains_skills_conventions(
        self, tmp_path: Path
    ) -> None:
        """Test that framework contract contains skills path conventions."""
        agent_dir = tmp_path / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Framework contract should contain skills conventions
        system_prompt = setup.agent.system_prompt
        assert "skills/" in system_prompt
        assert "SKILL.md" in system_prompt
        assert "User-workspace skills" in system_prompt

    def test_framework_contract_available_as_constant(self) -> None:
        """Test that FRAMEWORK_CONTRACT constant is accessible."""
        assert FRAMEWORK_CONTRACT is not None
        assert "skills/" in FRAMEWORK_CONTRACT
        assert "SKILL.md" in FRAMEWORK_CONTRACT


class TestSkillsWithUserInstructions:
    """Test skills combined with user instructions."""

    def test_skill_plus_workspace_instructions(self, tmp_path: Path) -> None:
        """Test that skills combine with workspace instructions."""
        # Create agent with skill in config
        agent_dir = tmp_path / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Base instructions.
""")
        (agent_dir / "config.yaml").write_text("""
skills:
  - test-skill
""")

        # Create bundled skill
        skill_dir = agent_dir / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
---
# Skill Instructions
""")

        # Create workspace with instructions
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Workspace instructions (in physical workspace)
        quenda_dir = workspace / ".quenda"
        quenda_dir.mkdir(parents=True)  # Create .quenda directory first
        (quenda_dir / "INSTRUCTIONS.md").write_text("# Workspace Instructions")

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Skill is activated by default from config
        assert setup.skill_activator.is_active("test-skill")

        # Verify all layers present
        prompt = setup.agent.system_prompt
        assert "Base instructions" in prompt
        assert "Skill Instructions" in prompt
        assert "Workspace Instructions" in prompt