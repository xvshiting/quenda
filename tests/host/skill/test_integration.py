"""
Tests for skill integration with runner and instruction composition.
"""

import pytest
from pathlib import Path

from quenda.host.runner import setup_agent, AgentSetup
from quenda.host.skill import SkillDiscovery, SkillActivator


class TestSkillIntegrationWithRunner:
    """Tests for skill integration in the agent setup flow."""

    @pytest.fixture
    def agent_with_skills(self, tmp_path: Path) -> Path:
        """Create an agent package with skills configured."""
        # Create agent package
        agent_dir = tmp_path / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)

        # Create AGENT.md
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
version: "1.0.0"
description: Test agent with skills
---

You are a test agent.
""")

        # Create config.yaml with skills
        (agent_dir / "config.yaml").write_text("""
model:
  provider: deepseek
  name: deepseek-v4-flash

skills:
  - test-skill
  - another-skill
""")

        # Create bundled skills in agent package
        for skill_name in ["test-skill", "another-skill"]:
            skill_dir = agent_dir / "skills" / skill_name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: {skill_name}
description: {skill_name} description
---
# {skill_name} Instructions

This is the {skill_name} instruction content.
""")

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return tmp_path

    def test_setup_agent_initializes_skill_activator(
        self, agent_with_skills: Path
    ) -> None:
        """Test that setup_agent creates a SkillActivator."""
        agent_dir = agent_with_skills / "agents" / "test-agent"
        workspace = agent_with_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)

        assert setup is not None
        assert setup.skill_activator is not None

    def test_default_skills_activated_from_config(
        self, agent_with_skills: Path
    ) -> None:
        """Test that skills from config.yaml are activated."""
        agent_dir = agent_with_skills / "agents" / "test-agent"
        workspace = agent_with_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)

        assert setup is not None
        assert setup.skill_activator is not None

        # Check both skills are activated
        active_names = setup.skill_activator.list_active()
        assert "test-skill" in active_names
        assert "another-skill" in active_names

    def test_skill_instructions_in_composed(
        self, agent_with_skills: Path
    ) -> None:
        """Test that skill instructions appear in composed instructions."""
        agent_dir = agent_with_skills / "agents" / "test-agent"
        workspace = agent_with_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)

        assert setup is not None

        # Check agent system prompt contains skill instructions
        system_prompt = setup.agent.system_prompt
        assert "test-skill" in system_prompt
        assert "another-skill" in system_prompt
        assert "test-skill instruction content" in system_prompt.lower()

    def test_instruction_sources_include_skills(
        self, agent_with_skills: Path
    ) -> None:
        """Test that instruction sources include only active skill instructions."""
        from quenda.host.instructions import InstructionScope

        agent_dir = agent_with_skills / "agents" / "test-agent"
        workspace = agent_with_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)

        assert setup is not None

        # Check skill scope in instruction sources
        skill_sources = [
            s for s in setup.instruction_sources
            if s.scope == InstructionScope.SKILL
        ]
        assert len(skill_sources) == 2
        # Updated for Agent Skills spec structured format
        assert any('<skill_content name="test-skill">' in s.content for s in skill_sources)
        assert any('<skill_content name="another-skill">' in s.content for s in skill_sources)
        assert all("Available Skills" not in s.content for s in skill_sources)

    def test_agent_without_skills_config(self, tmp_path: Path) -> None:
        """Test that agents without skills config work correctly."""
        agent_dir = tmp_path / "agents" / "no-skill-agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: no-skill-agent
---
You are an agent without skills.
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        setup = setup_agent(agent_dir, workspace)

        assert setup is not None
        assert setup.skill_activator is not None
        assert len(setup.skill_activator.active_skills) == 0

    def test_missing_skill_does_not_fail_setup(
        self, tmp_path: Path
    ) -> None:
        """Test that missing skills don't cause setup to fail."""
        agent_dir = tmp_path / "agents" / "missing-skill-agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: missing-skill-agent
---
You are an agent.
""")

        (agent_dir / "config.yaml").write_text("""
skills:
  - nonexistent-skill
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Should not fail, just log warning
        setup = setup_agent(agent_dir, workspace)

        assert setup is not None
        assert len(setup.skill_activator.active_skills) == 0

    def test_catalog_injected_when_config_enabled(self, tmp_path: Path) -> None:
        """Available skill catalog should be injected when enabled in config."""
        agent_dir = tmp_path / "agents" / "catalog-agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: catalog-agent
---
Catalog agent.
""")

        (agent_dir / "config.yaml").write_text("""
skills:
  include_catalog: true
""")

        skill_dir = agent_dir / "skills" / "code-review"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: code-review
description: Review code changes carefully.
---
# Code Review
""")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None
        assert "Available Skills" in (setup.agent.system_prompt or "")
        assert "request_skill_activation" in (setup.agent.system_prompt or "")


class TestSkillConfigParsing:
    """Tests for skill configuration parsing."""

    def test_skills_list_format(self, tmp_path: Path) -> None:
        """Test simple list format for skills config."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "skills": ["skill-1", "skill-2"]
        })

        assert config.skills == ["skill-1", "skill-2"]

    def test_skills_structured_format(self, tmp_path: Path) -> None:
        """Test structured format for skills config."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "skills": {
                "activate": ["skill-1", "skill-2"],
                "include_catalog": True,
            }
        })

        assert config.skills == ["skill-1", "skill-2"]
        assert config.include_skill_catalog is True

    def test_no_skills_config(self, tmp_path: Path) -> None:
        """Test config without skills."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({})

        assert config.skills == []
        assert config.include_skill_catalog is False

    def test_catalog_can_be_enabled(self, tmp_path: Path) -> None:
        """Structured skills config can expose the catalog to the model."""
        from quenda.host.loader import AgentConfigYaml

        config = AgentConfigYaml.from_dict({
            "skills": {
                "include_catalog": True,
            }
        })

        assert config.skills == []
        assert config.include_skill_catalog is True
