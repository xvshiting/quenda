"""
Skill resource management - Loading and resolving skill resources.

ResourceResolver provides:
- Loading resource content on demand
- Listing available resources
- Template rendering for template assets
- URI-based resource access (skill://<skill-name>/<resource-path>)

Resources are auto-discovered from directory structure:
- references/ → reference resources (read-only)
- templates/ → template resources (read-only)
- assets/ → asset resources (read-only)
- scripts/ → executable scripts (.py files only)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quenda.host.skill.uri import SkillResourceURI

if TYPE_CHECKING:
    from quenda.host.skill.activation import SkillActivator
    from quenda.host.skill.package import SkillPackage, SkillResource


logger = logging.getLogger(__name__)


@dataclass
class ResourceInfo:
    """
    Information about a skill resource.

    Used for listing resources without loading content.
    """

    skill_name: str
    resource_name: str  # Filename only (e.g., "checklist.md")
    resource_type: str  # "reference", "template", "asset", or "script"
    executable: bool  # True only for scripts/*.py files
    path: Path  # Absolute filesystem path
    resource_path: str = ""  # Relative path within skill (e.g., "references/checklist.md")
    description: str = ""
    exists: bool = True

    def __post_init__(self) -> None:
        """Derive resource_path from path if not provided."""
        if not self.resource_path:
            self.resource_path = self.path.name

    def uri(self) -> str:
        """Return the skill:// URI for this resource."""
        return f"skill://{self.skill_name}/{self.resource_path}"


@dataclass
class LoadedResource:
    """
    A resource with its content loaded.

    Includes context about which skill it belongs to.
    """

    skill_name: str
    resource_name: str  # Filename only
    resource_type: str
    executable: bool  # True only for scripts/*.py files
    content: str
    path: Path
    resource_path: str = ""  # Relative path within skill
    description: str = ""

    def __post_init__(self) -> None:
        """Derive resource_path from path if not provided."""
        if not self.resource_path:
            self.resource_path = self.path.name

    def uri(self) -> str:
        """Return the skill:// URI for this resource."""
        return f"skill://{self.skill_name}/{self.resource_path}"


class ResourceResolver:
    """
    Resolves and loads resources from active skills.

    Resources are loaded on demand (progressive disclosure).
    The resolver provides methods to:
    - List all resources from active skills
    - Load specific resource content
    - Render template assets with context

    The resolver can be constructed with either:
    - A static list of skills (for simple use cases)
    - A SkillActivator for dynamic skill access (recommended)

    When using a SkillActivator, the resolver always sees the current
    active skills, even if skills are activated/deactivated after
    the resolver is created.

    Usage:
        # Static mode:
        resolver = ResourceResolver(active_skills)
        resources = resolver.list_resources()

        # Dynamic mode (recommended):
        resolver = ResourceResolver.from_activator(skill_activator)
        content = resolver.load_resource("code-review", "checklist.md")
    """

    def __init__(self, skills: list[SkillPackage]) -> None:
        """
        Initialize resolver with active skills.

        Args:
            skills: List of active skill packages.
        """
        self._skills = skills
        self._activator: SkillActivator | None = None

    @classmethod
    def from_activator(cls, activator: SkillActivator) -> "ResourceResolver":
        """
        Create a resolver that dynamically accesses active skills.

        This is the recommended way to create a resolver when skills
        may be activated or deactivated during the session.

        Args:
            activator: The SkillActivator managing active skills.

        Returns:
            A ResourceResolver that always sees current active skills.
        """
        resolver = cls([])
        resolver._activator = activator
        return resolver

    @property
    def skills(self) -> list[SkillPackage]:
        """
        Get the current list of active skills.

        If using dynamic mode with an activator, this returns the
        current active skills. Otherwise, returns the static list.
        """
        if self._activator is not None:
            return self._activator.active_skills
        return self._skills

    @skills.setter
    def skills(self, value: list[SkillPackage]) -> None:
        """Set the list of active skills (for static mode)."""
        self._skills = value

    def list_resources(self) -> list[ResourceInfo]:
        """
        List all resources from active skills.

        Returns:
            List of ResourceInfo objects for all resources.
        """
        resources: list[ResourceInfo] = []

        for skill in self.skills:
            for resource in skill.resources:
                # Compute relative path within skill
                try:
                    relative_path = str(resource.path.relative_to(skill.path))
                except ValueError:
                    # Fallback if path is not under skill.path
                    relative_path = resource.path.name

                resources.append(ResourceInfo(
                    skill_name=skill.name,
                    resource_name=resource.path.name,
                    resource_path=relative_path,
                    resource_type=resource.type,
                    executable=resource.executable,
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

        try:
            relative_path = str(resource.path.relative_to(skill.path))
        except ValueError:
            relative_path = resource.path.name

        return LoadedResource(
            skill_name=skill.name,
            resource_name=resource.path.name,
            resource_path=relative_path,
            resource_type=resource.type,
            executable=resource.executable,
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

    def resolve_uri(self, uri: str) -> LoadedResource | None:
        """
        Resolve a skill:// URI to loaded content.

        This is the primary method for accessing resources by URI.

        Args:
            uri: A skill:// URI (e.g., "skill://code-review/checklist.md")

        Returns:
            LoadedResource with content, or None if not found.
        """
        parsed = SkillResourceURI.parse(uri)
        if parsed is None:
            logger.warning(f"Invalid skill URI: {uri}")
            return None

        return self._resolve_parsed_uri(parsed)

    def resolve_uri_to_info(self, uri: str) -> ResourceInfo | None:
        """
        Resolve a skill:// URI to ResourceInfo (without loading content).

        Args:
            uri: A skill:// URI

        Returns:
            ResourceInfo, or None if not found.
        """
        parsed = SkillResourceURI.parse(uri)
        if parsed is None:
            return None

        skill = self._get_skill(parsed.skill_name)
        if skill is None:
            return None

        resource = self._find_resource_by_path(skill, parsed.resource_path)
        if resource is None:
            return None

        try:
            relative_path = str(resource.path.relative_to(skill.path))
        except ValueError:
            relative_path = resource.path.name

        return ResourceInfo(
            skill_name=skill.name,
            resource_name=resource.path.name,
            resource_path=relative_path,
            resource_type=resource.type,
            executable=resource.executable,
            path=resource.path,
            description=resource.description,
            exists=resource.path.exists(),
        )

    def list_resource_uris(self, skill_name: str | None = None) -> list[str]:
        """
        List available resources as skill:// URIs.

        Args:
            skill_name: Optional filter to a specific skill.

        Returns:
            List of skill:// URI strings.
        """
        resources = self.list_resources()
        if skill_name is not None:
            resources = [r for r in resources if r.skill_name == skill_name]
        return [r.uri() for r in resources]

    def _resolve_parsed_uri(self, parsed: SkillResourceURI) -> LoadedResource | None:
        """Resolve a parsed URI to loaded content."""
        skill = self._get_skill(parsed.skill_name)
        if skill is None:
            logger.warning(f"Skill '{parsed.skill_name}' not found in active skills")
            return None

        resource = self._find_resource_by_path(skill, parsed.resource_path)
        if resource is None:
            logger.warning(f"Resource '{parsed.resource_path}' not found in skill '{parsed.skill_name}'")
            return None

        if not resource.path.exists():
            logger.warning(f"Resource path does not exist: {resource.path}")
            return None

        content = skill.load_resource_content(resource)

        try:
            relative_path = str(resource.path.relative_to(skill.path))
        except ValueError:
            relative_path = resource.path.name

        return LoadedResource(
            skill_name=skill.name,
            resource_name=resource.path.name,
            resource_path=relative_path,
            resource_type=resource.type,
            executable=resource.executable,
            content=content,
            path=resource.path,
            description=resource.description,
        )

    def _find_resource_by_path(
        self,
        skill: SkillPackage,
        relative_path: str,
    ) -> SkillResource | None:
        """Find a resource by its relative path within the skill."""
        # Normalize the path
        normalized = relative_path.lstrip("/")

        for resource in skill.resources:
            # Try exact relative path match
            try:
                resource_relative = str(resource.path.relative_to(skill.path))
                if resource_relative == normalized:
                    return resource
            except ValueError:
                pass

            # Try filename match for simple cases
            if resource.path.name == normalized or resource.path.name == Path(normalized).name:
                return resource

        return None

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