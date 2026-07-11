"""
Tests for skill discovery and parsing.

Resources are auto-discovered from directory structure:
- references/ → reference resources
- templates/ → template resources
- assets/ → asset resources
- scripts/ → executable scripts (.py files only)
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from quenda.host.skill import SkillDiscovery, SkillPackage


class TestSkillDiscovery:
    """Tests for SkillDiscovery class."""

    @pytest.fixture
    def user_workspace_skills(self, tmp_path: Path) -> Path:
        """Create a user-workspace skills directory with test skills."""
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A test skill
version: "1.0.0"
---
# Test Skill Instructions
This is a test skill.
""")

        # Create resources in references/ directory
        references = skill_dir / "references"
        references.mkdir()
        (references / "guide.md").write_text("# Guide Content")

        return tmp_path / "skills"

    def test_discover_skill(self, user_workspace_skills: Path) -> None:
        """Test basic skill discovery."""
        discovery = SkillDiscovery(user_workspace_skills_path=user_workspace_skills)
        skills = discovery.discover_skills()

        assert len(skills) == 1
        assert skills[0].name == "test-skill"
        assert skills[0].description == "A test skill"

    def test_skill_resources_resolved(self, user_workspace_skills: Path) -> None:
        """Test that resources are auto-discovered from directory structure."""
        discovery = SkillDiscovery(user_workspace_skills_path=user_workspace_skills)
        skills = discovery.discover_skills()

        skill = skills[0]
        assert len(skill.resources) == 1
        assert skill.resources[0].type == "reference"
        assert skill.resources[0].path.name == "guide.md"
        assert skill.resources[0].executable is False

    def test_get_skill_by_name(self, user_workspace_skills: Path) -> None:
        """Test getting a specific skill by name."""
        discovery = SkillDiscovery(user_workspace_skills_path=user_workspace_skills)
        skill = discovery.get_skill("test-skill")

        assert skill is not None
        assert skill.name == "test-skill"

    def test_get_nonexistent_skill(self, user_workspace_skills: Path) -> None:
        """Test getting a non-existent skill."""
        discovery = SkillDiscovery(user_workspace_skills_path=user_workspace_skills)
        skill = discovery.get_skill("nonexistent")

        assert skill is None

    def test_skill_without_frontmatter(self, tmp_path: Path) -> None:
        """Test handling skill without valid frontmatter."""
        skill_dir = tmp_path / "skills" / "invalid-skill"
        skill_dir.mkdir(parents=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# No frontmatter here")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skills = discovery.discover_skills()

        # Should skip invalid skill
        assert len(skills) == 0

    def test_skill_minimal_frontmatter(self, tmp_path: Path) -> None:
        """Test skill with minimal frontmatter."""
        skill_dir = tmp_path / "skills" / "minimal-skill"
        skill_dir.mkdir(parents=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: minimal
description: Minimal skill
---
# Instructions
""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skills = discovery.discover_skills()

        assert len(skills) == 1
        assert skills[0].name == "minimal"
        assert skills[0].version == "0.1.0"  # Default version
        assert len(skills[0].resources) == 0

    def test_multiple_skills(self, tmp_path: Path) -> None:
        """Test discovering multiple skills."""
        for i in range(3):
            skill_dir = tmp_path / "skills" / f"skill-{i}"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: skill-{i}
description: Skill {i}
---
# Instructions {i}
""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skills = discovery.discover_skills()

        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"skill-0", "skill-1", "skill-2"}

    def test_discovers_project_quenda_skills(self, tmp_path: Path) -> None:
        """Project-level .quenda/skills are discovered from workspace_path."""
        workspace = tmp_path / "workspace"
        skill_dir = workspace / ".quenda" / "skills" / "project-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: project-skill
description: Project skill
---
# Project Skill
""")

        discovery = SkillDiscovery(workspace_path=workspace)
        skills = discovery.discover_skills()

        assert len(skills) == 1
        assert skills[0].name == "project-skill"
        assert skills[0].source == "workspace"

    def test_project_quenda_skill_overrides_agents_and_bundled(self, tmp_path: Path) -> None:
        """Project .quenda/skills take priority over .agents and bundled skills."""
        workspace = tmp_path / "workspace"
        agent_dir = workspace / "agents" / "dev-agent"

        for base, title in [
            (workspace / ".quenda" / "skills", "Project Quenda"),
            (workspace / ".agents" / "skills", "Project Agents"),
            (agent_dir / "skills", "Bundled"),
        ]:
            skill_dir = base / "shared-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: shared-skill
description: {title}
---
# {title}
""")

        discovery = SkillDiscovery(
            workspace_path=workspace,
            agent_package_path=agent_dir,
        )
        skills = discovery.discover_skills()

        assert len([skill for skill in skills if skill.name == "shared-skill"]) == 1
        skill = discovery.get_skill("shared-skill")
        assert skill is not None
        assert skill.source == "workspace"
        assert "Project Quenda" in skill.instructions

    def test_user_workspace_skill_overrides_project_quenda_skill(self, tmp_path: Path) -> None:
        """User-workspace skills remain the highest-priority override."""
        workspace = tmp_path / "workspace"
        user_skills = tmp_path / "user-workspace-skills"

        for base, title in [
            (user_skills, "User Workspace"),
            (workspace / ".quenda" / "skills", "Project Quenda"),
        ]:
            skill_dir = base / "shared-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: shared-skill
description: {title}
---
# {title}
""")

        discovery = SkillDiscovery(
            user_workspace_skills_path=user_skills,
            workspace_path=workspace,
        )
        skill = discovery.get_skill("shared-skill")

        assert skill is not None
        assert skill.source == "user_workspace"
        assert "User Workspace" in skill.instructions

    def test_priority_order_user_workspace_over_user(self, tmp_path: Path) -> None:
        """Test that user-workspace skills override user skills."""
        # Create user-workspace skill
        ws_skill_dir = tmp_path / "ws-skills" / "override-test"
        ws_skill_dir.mkdir(parents=True)
        (ws_skill_dir / "SKILL.md").write_text("""---
name: override-test
description: User-workspace version
---""")

        # Create user skill with same name
        user_skill_dir = Path.home() / ".quenda" / "skills" / "override-test"
        user_skill_dir.mkdir(parents=True, exist_ok=True)
        user_skill = user_skill_dir / "SKILL.md"
        user_skill.write_text("""---
name: override-test
description: User version
---""")

        try:
            discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "ws-skills")
            skills = discovery.discover_skills()

            skill = next(s for s in skills if s.name == "override-test")
            assert skill.description == "User-workspace version"
            assert skill.source == "user_workspace"
        finally:
            # Cleanup user skill
            if user_skill.exists():
                user_skill.unlink()
            if user_skill_dir.exists():
                user_skill_dir.rmdir()

    def test_skill_source_determination(self, tmp_path: Path) -> None:
        """Test skill source determination."""
        # User-workspace skill
        ws_skill_dir = tmp_path / "ws-skills" / "ws-skill"
        ws_skill_dir.mkdir(parents=True)
        (ws_skill_dir / "SKILL.md").write_text("""---
name: ws-skill
description: User-workspace
---""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "ws-skills")
        skills = discovery.discover_skills()

        ws = next(s for s in skills if s.name == "ws-skill")
        assert ws.source == "user_workspace"

    def test_agent_package_skills_discovered(self, tmp_path: Path) -> None:
        """Test that skills from agent package are discovered."""
        # Create agent package skills
        agent_skill_dir = tmp_path / "agent" / "skills" / "bundled-skill"
        agent_skill_dir.mkdir(parents=True)
        (agent_skill_dir / "SKILL.md").write_text("""---
name: bundled-skill
description: Bundled
---""")

        # No user-workspace skills
        discovery = SkillDiscovery(
            user_workspace_skills_path=None,
            agent_package_path=tmp_path / "agent",
        )
        skills = discovery.discover_skills()

        assert len(skills) == 1
        assert skills[0].name == "bundled-skill"
        assert skills[0].source == "agent_package"


class TestSkillPackage:
    """Tests for SkillPackage."""

    @pytest.fixture
    def skill_with_resources(self, tmp_path: Path) -> SkillPackage:
        """Create a skill with resources in standard directories."""
        skill_dir = tmp_path / "skills" / "resource-skill"
        skill_dir.mkdir(parents=True)

        (skill_dir / "SKILL.md").write_text("""---
name: resource-skill
description: Skill with resources
---
# Instructions
""")

        # Create resources in standard directories
        references = skill_dir / "references"
        references.mkdir()
        (references / "guide.md").write_text("# Guide\nContent here.")

        templates = skill_dir / "templates"
        templates.mkdir()
        (templates / "report.md").write_text("# Report\n{{content}}")

        assets = skill_dir / "assets"
        assets.mkdir()
        (assets / "data.json").write_text('{"key": "value"}')

        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "calc.py").write_text("print('hello')")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skills = discovery.discover_skills()
        return skills[0]

    def test_get_reference(self, skill_with_resources: SkillPackage) -> None:
        """Test getting a reference resource."""
        resource = skill_with_resources.get_reference("guide.md")

        assert resource is not None
        assert resource.type == "reference"
        assert resource.executable is False

    def test_get_template(self, skill_with_resources: SkillPackage) -> None:
        """Test getting a template resource."""
        resource = skill_with_resources.get_template("report.md")

        assert resource is not None
        assert resource.type == "template"
        assert resource.executable is False

    def test_get_asset(self, skill_with_resources: SkillPackage) -> None:
        """Test getting an asset resource."""
        resource = skill_with_resources.get_asset("data.json")

        assert resource is not None
        assert resource.type == "asset"

    def test_get_script(self, skill_with_resources: SkillPackage) -> None:
        """Test getting an executable script."""
        resource = skill_with_resources.get_script("calc.py")

        assert resource is not None
        assert resource.type == "script"
        assert resource.executable is True

    def test_get_nonexistent_resource(self, skill_with_resources: SkillPackage) -> None:
        """Test getting a non-existent resource."""
        resource = skill_with_resources.get_reference("nonexistent.md")
        assert resource is None

    def test_load_resource_content(self, skill_with_resources: SkillPackage) -> None:
        """Test lazy loading of resource content."""
        resource = skill_with_resources.get_reference("guide.md")
        assert resource is not None

        # Content should be None initially
        assert resource.content is None

        # Load content
        content = skill_with_resources.load_resource_content(resource)
        assert "# Guide" in content
        assert resource.content is not None


class TestProgressiveDisclosure:
    """Tests for progressive disclosure (ADR-002)."""

    def test_instructions_lazy_loaded(self, tmp_path: Path) -> None:
        """Test that instructions are not parsed during discovery."""
        skill_dir = tmp_path / "skills" / "lazy-skill"
        skill_dir.mkdir(parents=True)

        (skill_dir / "SKILL.md").write_text("""---
name: lazy-skill
description: Lazy loaded skill
---
# Instructions
These are the instructions.
""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skills = discovery.discover_skills()

        skill = skills[0]

        # _instructions should be None initially (not parsed)
        assert skill._instructions is None

        # Accessing instructions triggers parsing
        instructions = skill.instructions
        assert "These are the instructions" in instructions

        # Now _instructions is cached
        assert skill._instructions is not None

    def test_instructions_cached_after_first_access(self, tmp_path: Path) -> None:
        """Test that instructions are cached after first access."""
        skill_dir = tmp_path / "skills" / "cached-skill"
        skill_dir.mkdir(parents=True)

        (skill_dir / "SKILL.md").write_text("""---
name: cached-skill
description: Cached skill
---
# Content
""")

        discovery = SkillDiscovery(user_workspace_skills_path=tmp_path / "skills")
        skill = discovery.get_skill("cached-skill")
        assert skill is not None

        # First access parses
        first = skill.instructions
        # Second access returns cached
        second = skill.instructions

        assert first is second  # Same object (cached)