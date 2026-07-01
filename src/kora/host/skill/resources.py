"""
Skill resource management - Loading and resolving skill resources.

ResourceResolver provides:
- Loading resource content on demand
- Listing available resources
- Template rendering for template assets
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kora.host.skill.package import SkillPackage, SkillResource


logger = logging.getLogger(__name__)


@dataclass
class ResourceInfo:
    """
    Information about a skill resource.

    Used for listing resources without loading content.
    """

    skill_name: str
    resource_name: str
    resource_type: str  # "reference" or "asset"
    path: Path
    description: str = ""
    exists: bool = True


@dataclass
class LoadedResource:
    """
    A resource with its content loaded.

    Includes context about which skill it belongs to.
    """

    skill_name: str
    resource_name: str
    resource_type: str
    content: str
    path: Path
    description: str = ""


class ResourceResolver:
    """
    Resolves and loads resources from active skills.

    Resources are loaded on demand (progressive disclosure).
    The resolver provides methods to:
    - List all resources from active skills
    - Load specific resource content
    - Render template assets with context

    Usage:
        resolver = ResourceResolver(active_skills)
        resources = resolver.list_resources()
        content = resolver.load_resource("code-review", "checklist.md")
    """

    def __init__(self, skills: list[SkillPackage]) -> None:
        """
        Initialize resolver with active skills.

        Args:
            skills: List of active skill packages.
        """
        self.skills = skills

    def list_resources(self) -> list[ResourceInfo]:
        """
        List all resources from active skills.

        Returns:
            List of ResourceInfo objects for all resources.
        """
        resources: list[ResourceInfo] = []

        for skill in self.skills:
            for resource in skill.resources:
                resources.append(ResourceInfo(
                    skill_name=skill.name,
                    resource_name=resource.path.name,
                    resource_type=resource.type,
                    path=resource.path,
                    description=resource.description,
                    exists=resource.path.exists(),
                ))

        return resources

    def list_references(self) -> list[ResourceInfo]:
        """List only reference resources from active skills."""
        return [r for r in self.list_resources() if r.resource_type == "reference"]

    def list_assets(self) -> list[ResourceInfo]:
        """List only asset resources from active skills."""
        return [r for r in self.list_resources() if r.resource_type == "asset"]

    def load_resource(
        self,
        skill_name: str,
        resource_name: str,
    ) -> LoadedResource | None:
        """
        Load a specific resource by skill name and resource name.

        Args:
            skill_name: Name of the skill containing the resource.
            resource_name: Name of the resource file.

        Returns:
            LoadedResource with content, or None if not found.
        """
        skill = self._get_skill(skill_name)
        if skill is None:
            logger.warning(f"Skill '{skill_name}' not found in active skills")
            return None

        resource = self._find_resource(skill, resource_name)
        if resource is None:
            logger.warning(f"Resource '{resource_name}' not found in skill '{skill_name}'")
            return None

        if not resource.path.exists():
            logger.warning(f"Resource path does not exist: {resource.path}")
            return None

        content = skill.load_resource_content(resource)

        return LoadedResource(
            skill_name=skill.name,
            resource_name=resource.path.name,
            resource_type=resource.type,
            content=content,
            path=resource.path,
            description=resource.description,
        )

    def render_template(
        self,
        skill_name: str,
        template_name: str,
        context: dict[str, Any],
    ) -> str | None:
        """
        Render a template asset with context.

        Simple string substitution using {{variable}} syntax.

        Args:
            skill_name: Name of the skill containing the template.
            template_name: Name of the template file.
            context: Dictionary of variables for substitution.

        Returns:
            Rendered template string, or None if not found.
        """
        loaded = self.load_resource(skill_name, template_name)
        if loaded is None:
            return None

        # Simple template rendering with {{variable}} syntax
        content = loaded.content
        for key, value in context.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))

        return content

    def get_resource_path(
        self,
        skill_name: str,
        resource_name: str,
    ) -> Path | None:
        """
        Get the file path for a resource without loading it.

        Args:
            skill_name: Name of the skill containing the resource.
            resource_name: Name of the resource file.

        Returns:
            Path to the resource file, or None if not found.
        """
        skill = self._get_skill(skill_name)
        if skill is None:
            return None

        resource = self._find_resource(skill, resource_name)
        if resource is None:
            return None

        return resource.path

    def _get_skill(self, name: str) -> SkillPackage | None:
        """Find a skill by name in active skills."""
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def _find_resource(
        self,
        skill: SkillPackage,
        name: str,
    ) -> SkillResource | None:
        """Find a resource in a skill by name."""
        # Try exact match first
        for resource in skill.resources:
            if resource.path.name == name:
                return resource

        # Try partial match (e.g., "guide.md" matches "docs/guide.md")
        for resource in skill.resources:
            if resource.path.name == name:
                return resource
            if str(resource.path).endswith(name):
                return resource

        return None


__all__ = [
    "ResourceInfo",
    "LoadedResource",
    "ResourceResolver",
]
