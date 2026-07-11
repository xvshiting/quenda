"""
Tests for agent package bundled skills.
"""

import pytest
from pathlib import Path

from quenda.host.skill import SkillDiscovery, SkillActivator
from quenda.host.runner import setup_agent


class TestAgentPackageBundledSkills:
    """Tests for skills bundled with agent packages."""

    @pytest.fixture
    def agent_with_bundled_skills(self, tmp_path: Path) -> Path:
        """Create an agent package with bundled skills."""
        # Create agent package
        agent_dir = tmp_path / "agents" / "dev-agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: dev-agent
version: "1.0.0"
description: Development agent with bundled skills
---

You are a development assistant.
""")

        (agent_dir / "config.yaml").write_text("""
model:
  provider: deepseek
  name: deepseek-v4-flash

skills:
  - code-review
  - repo-navigation
""")

        # Create bundled skills in agent package
        cr_skill = agent_dir / "skills" / "code-review"
        cr_skill.mkdir(parents=True)
        (cr_skill / "SKILL.md").write_text("""---
name: code-review
description: Bundled code review skill
version: "1.0.0"
---
# Code Review (Bundled)

This is a bundled skill from the agent package.
""")

        nav_skill = agent_dir / "skills" / "repo-navigation"
        nav_skill.mkdir(parents=True)
        (nav_skill / "SKILL.md").write_text("""---
name: repo-navigation
description: Bundled repo navigation skill
---
# Repo Navigation (Bundled)

Navigate code repositories efficiently.
""")

        # Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        return tmp_path

    def test_discover_bundled_skills(self, agent_with_bundled_skills: Path) -> None:
        """Test that bundled skills are discovered."""
        agent_dir = agent_with_bundled_skills / "agents" / "dev-agent"

        # Simulate user-workspace skills path (empty in this test)
        user_ws_skills = agent_with_bundled_skills / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )
        skills = discovery.discover_skills()

        skill_names = {s.name for s in skills}
        assert "code-review" in skill_names
        assert "repo-navigation" in skill_names

    def test_bundled_skill_source(
        self, agent_with_bundled_skills: Path
    ) -> None:
        """Test that bundled skills have correct source."""
        agent_dir = agent_with_bundled_skills / "agents" / "dev-agent"
        user_ws_skills = agent_with_bundled_skills / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )
        skills = discovery.discover_skills()

        cr_skill = next(s for s in skills if s.name == "code-review")
        assert cr_skill.source == "agent_package"

    def test_bundled_skills_activated_from_config(
        self, agent_with_bundled_skills: Path
    ) -> None:
        """Test that bundled skills are activated via config.yaml."""
        agent_dir = agent_with_bundled_skills / "agents" / "dev-agent"
        workspace = agent_with_bundled_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        active_names = setup.skill_activator.list_active()
        assert "code-review" in active_names
        assert "repo-navigation" in active_names

    def test_bundled_skill_instructions_in_prompt(
        self, agent_with_bundled_skills: Path
    ) -> None:
        """Test that bundled skill instructions appear in system prompt."""
        agent_dir = agent_with_bundled_skills / "agents" / "dev-agent"
        workspace = agent_with_bundled_skills / "workspace"

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        prompt = setup.agent.system_prompt
        assert "Code Review (Bundled)" in prompt
        assert "Repo Navigation (Bundled)" in prompt

    def test_user_workspace_skill_overrides_bundled(
        self, agent_with_bundled_skills: Path
    ) -> None:
        """Test that user-workspace skill can override bundled skill."""
        agent_dir = agent_with_bundled_skills / "agents" / "dev-agent"

        # Create user-workspace skills directory with override
        user_ws_skills = agent_with_bundled_skills / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        ws_skill = user_ws_skills / "code-review"
        ws_skill.mkdir(parents=True)
        (ws_skill / "SKILL.md").write_text("""---
name: code-review
description: User-workspace override
---
# Code Review (User Workspace Override)

This user-workspace skill overrides the bundled one.
""")

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )
        skills = discovery.discover_skills()

        # Should only have one code-review skill
        cr_skills = [s for s in skills if s.name == "code-review"]
        assert len(cr_skills) == 1

        # Should be user-workspace version (higher priority)
        assert cr_skills[0].source == "user_workspace"
        assert "User Workspace Override" in cr_skills[0].instructions

    def test_discovery_without_agent_package(
        self, agent_with_bundled_skills: Path
    ) -> None:
        """Test discovery still works without agent package path."""
        user_ws_skills = agent_with_bundled_skills / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(user_workspace_skills_path=user_ws_skills)
        skills = discovery.discover_skills()

        # No skills found (empty user-workspace)
        assert len(skills) == 0

    def test_agent_package_skill_with_resources(
        self, tmp_path: Path
    ) -> None:
        """Test bundled skill with resources auto-discovered from directory."""
        # Create agent package with skill that has resources
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True)

        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")

        skill_dir = agent_dir / "skills" / "docs-gen"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: docs-gen
description: Documentation generator
---
# Docs Generator
""")
        # Create resources in templates/ directory
        templates = skill_dir / "templates"
        templates.mkdir()
        (templates / "api.md").write_text("# API Template")

        # Create scripts for executable resources
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "generate.py").write_text("print('generating...')")

        user_ws_skills = tmp_path / "user-ws-skills"
        user_ws_skills.mkdir(parents=True)

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_ws_skills,
            agent_package_path=agent_dir,
        )
        skills = discovery.discover_skills()

        skill = next(s for s in skills if s.name == "docs-gen")
        assert skill.source == "agent_package"
        assert len(skill.resources) == 2  # 1 template + 1 script

        # Check resource types and executable flags
        template = next((r for r in skill.resources if r.type == "template"), None)
        assert template is not None
        assert template.executable is False

        script = next((r for r in skill.resources if r.type == "script"), None)
        assert script is not None
        assert script.executable is True

    def test_mixed_skill_sources(self, tmp_path: Path) -> None:
        """Test skills from multiple sources."""
        # Create agent with bundled skill
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("""---
name: test-agent
---
Test agent.
""")
        (agent_dir / "config.yaml").write_text("""
skills:
  - bundled-skill
  - user-workspace-skill
""")

        bundled_skill = agent_dir / "skills" / "bundled-skill"
        bundled_skill.mkdir(parents=True)
        (bundled_skill / "SKILL.md").write_text("""---
name: bundled-skill
description: Bundled skill
---
# Bundled
""")

        # Create workspace - the runner will create user-workspace skills path
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        setup = setup_agent(agent_dir, workspace)
        assert setup is not None

        # Bundled skill should be activated
        active = setup.skill_activator.list_active()
        assert "bundled-skill" in active

        # user-workspace-skill doesn't exist, so it won't be activated
        # but that's expected behavior - missing skills are skipped

        # Check sources for bundled skill
        bundled = next(
            s for s in setup.skill_discovery.discover_skills()
            if s.name == "bundled-skill"
        )
        assert bundled.source == "agent_package"