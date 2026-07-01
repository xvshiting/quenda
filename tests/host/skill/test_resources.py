"""
Tests for skill resource management.
"""

import pytest
from pathlib import Path

from kora.host.skill import (
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
        """Create skills with resources."""
        # Create skill with references and assets
        skill_dir = tmp_path / "skills" / "code-review"
        skill_dir.mkdir(parents=True)

        (skill_dir / "SKILL.md").write_text("""---
name: code-review
description: Code review skill
kora:
  resources:
    references:
      - path: "guides/style-guide.md"
        description: "Code style guidelines"
      - path: "docs/checklist.md"
        description: "Review checklist"
    assets:
      - path: "templates/report.md"
        type: template
        description: "Review report template"
---
# Code Review

Perform code review.
""")

        # Create resource files
        guides = skill_dir / "guides"
        guides.mkdir()
        (guides / "style-guide.md").write_text("# Style Guide\n\n- Use 4 spaces\n- Max line length 100")

        docs = skill_dir / "docs"
        docs.mkdir()
        (docs / "checklist.md").write_text("# Checklist\n\n- [ ] Style check\n- [ ] Test check")

        templates = skill_dir / "templates"
        templates.mkdir()
        (templates / "report.md").write_text("# Review Report\n\nAuthor: {{author}}\nDate: {{date}}")

        # Create another skill
        skill_dir2 = tmp_path / "skills" / "testing"
        skill_dir2.mkdir(parents=True)
        (skill_dir2 / "SKILL.md").write_text("""---
name: testing
description: Testing skill
kora:
  resources:
    references:
      - path: "test-guide.md"
---
# Testing
""")
        (skill_dir2 / "test-guide.md").write_text("# Test Guide")

        return tmp_path / "skills"

    def test_list_resources(self, skill_with_resources: Path) -> None:
        """Test listing all resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")
        activator.activate_skill("testing")

        resolver = ResourceResolver(activator.active_skills)
        resources = resolver.list_resources()

        assert len(resources) == 4  # 3 from code-review, 1 from testing
        resource_names = [r.resource_name for r in resources]
        assert "style-guide.md" in resource_names
        assert "checklist.md" in resource_names
        assert "report.md" in resource_names
        assert "test-guide.md" in resource_names

    def test_list_references(self, skill_with_resources: Path) -> None:
        """Test listing only reference resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        refs = resolver.list_references()

        assert len(refs) == 2
        for r in refs:
            assert r.resource_type == "reference"

    def test_list_assets(self, skill_with_resources: Path) -> None:
        """Test listing only asset resources."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        assets = resolver.list_assets()

        assert len(assets) == 1
        assert assets[0].resource_name == "report.md"
        assert assets[0].resource_type == "asset"

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

    def test_resource_info_contains_description(
        self, skill_with_resources: Path
    ) -> None:
        """Test that ResourceInfo includes description."""
        discovery = SkillDiscovery(user_workspace_skills_path=skill_with_resources)
        activator = SkillActivator(discovery)
        activator.activate_skill("code-review")

        resolver = ResourceResolver(activator.active_skills)
        resources = resolver.list_resources()

        style_guide = next(
            r for r in resources if r.resource_name == "style-guide.md"
        )
        assert style_guide.description == "Code style guidelines"

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
            path=tmp_path / "guide.md",
            description="Test guide",
            exists=True,
        )

        assert info.skill_name == "test-skill"
        assert info.resource_name == "guide.md"
        assert info.resource_type == "reference"
        assert info.description == "Test guide"
        assert info.exists is True


class TestLoadedResource:
    """Tests for LoadedResource dataclass."""

    def test_loaded_resource_creation(self, tmp_path: Path) -> None:
        """Test creating a LoadedResource."""
        resource = LoadedResource(
            skill_name="test-skill",
            resource_name="guide.md",
            resource_type="reference",
            content="# Guide\n\nContent here.",
            path=tmp_path / "guide.md",
            description="Test guide",
        )

        assert resource.skill_name == "test-skill"
        assert resource.content == "# Guide\n\nContent here."