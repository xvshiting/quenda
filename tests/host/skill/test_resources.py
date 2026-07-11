"""
Tests for skill resource management.

Resources are auto-discovered from directory structure:
- references/ → reference resources
- templates/ → template resources
- assets/ → asset resources
- scripts/ → executable scripts (.py files only)
"""

import pytest
from pathlib import Path

from quenda.host.skill import (
    SkillDiscovery,
    SkillActivator,
    ResourceResolver,
    ResourceInfo,
    LoadedResource,
)


class TestResourceResolver:
    """Tests for ResourceResolver class."""

    @pytest.fixture
    def skill_with_resources(self, tmp_path: Path) -> Path:
        """Create skills with resources in standard directories."""
        # Create skill with references, templates, and scripts
        skill_dir = tmp_path / "skills" / "code-review"
        skill_dir.mkdir(parents=True)

        (skill_dir / "SKILL.md").write_text("""---
name: code-review
description: Code review skill
---
# Code Review

Perform code review.
""")

        # Create references
        guides = skill_dir / "references"
        guides.mkdir()
        (guides / "style-guide.md").write_text("# Style Guide\n\n- Use 4 spaces\n- Max line length 100")

        docs = skill_dir / "references"
        # Already created, add another file
        (docs / "checklist.md").write_text("# Checklist\n\n- [ ] Style check\n- [ ] Test check")

        # Create templates
        templates = skill_dir / "templates"
        templates.mkdir()
        (templates / "report.md").write_text("# Review Report\n\nAuthor: {{author}}\nDate: {{date}}")

        # Create scripts
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "analyze.py").write_text("print('analyzing...')")

        # Create another skill
        skill_dir2 = tmp_path / "skills" / "testing"
        skill_dir2.mkdir(parents=True)
        (skill_dir2 / "SKILL.md").write_text("""---
name: testing
description: Testing skill
---
# Testing
""")
        references2 = skill_dir2 / "references"
        references2.mkdir()
        (references2 / "test-guide.md").write_text("# Test Guide")

        return tmp_path / "skills"

    def test_list_resources(self, skill_with_resources: Path) -> None:
        """Test listing all resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")
        activator.activate_skill("testing")

        resolver = ResourceResolver(activator.active_skills)
        resources = resolver.list_resources()

        # code-review: 2 references + 1 template + 1 script = 4
        # testing: 1 reference = 1
        assert len(resources) == 5
        resource_names = [r.resource_name for r in resources]
        assert "style-guide.md" in resource_names
        assert "checklist.md" in resource_names
        assert "report.md" in resource_names
        assert "analyze.py" in resource_names
        assert "test-guide.md" in resource_names

    def test_list_references(self, skill_with_resources: Path) -> None:
        """Test listing only reference resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        refs = resolver.list_references()

        assert len(refs) == 2  # style-guide.md and checklist.md
        for r in refs:
            assert r.resource_type == "reference"

    def test_list_assets(self, skill_with_resources: Path) -> None:
        """Test listing only asset (template) resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        # Filter by template type
        all_resources = resolver.list_resources()
        templates = [r for r in all_resources if r.resource_type == "template"]

        assert len(templates) == 1
        assert templates[0].resource_name == "report.md"
        assert templates[0].resource_type == "template"

    def test_executable_scripts(self, skill_with_resources: Path) -> None:
        """Test that scripts/*.py are marked as executable."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        resources = resolver.list_resources()

        scripts = [r for r in resources if r.resource_type == "script"]
        assert len(scripts) == 1
        assert scripts[0].resource_name == "analyze.py"
        assert scripts[0].executable is True

        # Non-script resources should not be executable
        refs = [r for r in resources if r.resource_type == "reference"]
        for ref in refs:
            assert ref.executable is False

    def test_load_resource(self, skill_with_resources: Path) -> None:
        """Test loading a specific resource."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        loaded = resolver.load_resource("code-review", "style-guide.md")

        assert loaded is not None
        assert loaded.skill_name == "code-review"
        assert loaded.resource_name == "style-guide.md"
        assert "Style Guide" in loaded.content
        assert "4 spaces" in loaded.content

    def test_load_nonexistent_resource(self, skill_with_resources: Path) -> None:
        """Test loading a resource that doesn't exist."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        loaded = resolver.load_resource("code-review", "nonexistent.md")

        assert loaded is None

    def test_load_resource_from_nonexistent_skill(
        self, skill_with_resources: Path
    ) -> None:
        """Test loading a resource from a skill that's not active."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        # Don't activate any skills

        resolver = ResourceResolver(activator.active_skills)
        loaded = resolver.load_resource("code-review", "style-guide.md")

        assert loaded is None

    def test_render_template(self, skill_with_resources: Path) -> None:
        """Test rendering a template asset."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        rendered = resolver.render_template(
            "code-review",
            "report.md",
            {"author": "John Doe", "date": "2024-01-15"},
        )

        assert rendered is not None
        assert "Author: John Doe" in rendered
        assert "Date: 2024-01-15" in rendered

    def test_render_non_template(self, skill_with_resources: Path) -> None:
        """Test rendering a non-template resource (still works)."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        # Even references can be "rendered" (just string substitution)
        rendered = resolver.render_template(
            "code-review",
            "style-guide.md",
            {"placeholder": "value"},
        )

        assert rendered is not None
        assert "Style Guide" in rendered

    def test_get_resource_path(self, skill_with_resources: Path) -> None:
        """Test getting the path to a resource."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        path = resolver.get_resource_path("code-review", "style-guide.md")

        assert path is not None
        assert path.exists()
        assert path.name == "style-guide.md"

    def test_empty_resolver(self, tmp_path: Path) -> None:
        """Test resolver with no active skills."""
        resolver = ResourceResolver([])

        assert resolver.list_resources() == []
        assert resolver.load_resource("any", "resource.md") is None

    def test_multiple_skills_same_resource_name(
        self, skill_with_resources: Path
    ) -> None:
        """Test that resources with same name from different skills are distinct."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")
        activator.activate_skill("testing")

        resolver = ResourceResolver(activator.active_skills)

        # Load from each skill
        cr_resource = resolver.load_resource("code-review", "style-guide.md")
        testing_resource = resolver.load_resource("testing", "test-guide.md")

        # Both should be found
        assert cr_resource is not None
        assert testing_resource is not None

        # But they're different
        assert cr_resource.skill_name != testing_resource.skill_name


class TestResourceInfo:
    """Tests for ResourceInfo dataclass."""

    def test_resource_info_creation(self, tmp_path: Path) -> None:
        """Test creating a ResourceInfo."""
        info = ResourceInfo(
            skill_name="test-skill",
            resource_name="guide.md",
            resource_type="reference",
            executable=False,
            path=tmp_path / "guide.md",
            exists=True,
        )

        assert info.skill_name == "test-skill"
        assert info.resource_name == "guide.md"
        assert info.resource_type == "reference"
        assert info.executable is False
        assert info.exists is True

    def test_executable_resource_info(self, tmp_path: Path) -> None:
        """Test creating an executable ResourceInfo."""
        info = ResourceInfo(
            skill_name="test-skill",
            resource_name="calc.py",
            resource_type="script",
            executable=True,
            path=tmp_path / "calc.py",
        )

        assert info.resource_type == "script"
        assert info.executable is True


class TestLoadedResource:
    """Tests for LoadedResource dataclass."""

    def test_loaded_resource_creation(self, tmp_path: Path) -> None:
        """Test creating a LoadedResource."""
        resource = LoadedResource(
            skill_name="test-skill",
            resource_name="guide.md",
            resource_type="reference",
            executable=False,
            content="# Guide\n\nContent here.",
            path=tmp_path / "guide.md",
        )

        assert resource.skill_name == "test-skill"
        assert resource.content == "# Guide\n\nContent here."
        assert resource.executable is False

    def test_loaded_script_resource(self, tmp_path: Path) -> None:
        """Test creating a LoadedResource for a script."""
        resource = LoadedResource(
            skill_name="test-skill",
            resource_name="calc.py",
            resource_type="script",
            executable=True,
            content="print('hello')",
            path=tmp_path / "calc.py",
        )

        assert resource.resource_type == "script"
        assert resource.executable is True