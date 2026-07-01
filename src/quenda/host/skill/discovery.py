"""
Skill discovery - Finding and loading skills from configured paths.

Skills are discovered in priority order:
1. User-workspace skills: ~/.quenda/users/<user>/workspaces/<ws_id>/skills/ (highest priority)
2. Agent-package bundled: <agent_package>/skills/
3. User-level: ~/.quenda/skills/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from quenda.host.skill.models import SkillFrontmatter
from quenda.host.skill.package import SkillPackage, SkillResource

if TYPE_CHECKING:
    from typing import Literal

logger = logging.getLogger(__name__)


class SkillDiscovery:
    """
    Discovers and loads skills from configured paths.

    Discovery is lazy - only frontmatter is parsed during discovery.
    Full instructions and resources are loaded when a skill is activated.

    Skills can come from:
    - User-workspace: ~/.quenda/users/<user>/workspaces/<ws_id>/skills/
      (user-specific skills for a workspace, highest priority)
    - Agent package: <agent_package>/skills/ (bundled with agent)
    - User: ~/.quenda/skills/ (shared across workspaces, lowest priority)
    """

    def __init__(
        self,
        user_workspace_skills_path: Path | None = None,
        agent_package_path: Path | None = None,
    ) -> None:
        """
        Initialize skill discovery.

        Args:
            user_workspace_skills_path: Path to user-workspace skills directory
                (e.g., ~/.quenda/users/<user>/workspaces/<ws_id>/skills/).
            agent_package_path: Optional path to agent package for bundled skills.
        """
        self.user_workspace_skills_path = user_workspace_skills_path
        self.agent_package_path = agent_package_path

    def discover_skills(self) -> list[SkillPackage]:
        """
        Discover all available skills.

        Returns a list of discovered skills with minimal parsing
        (frontmatter only, instructions loaded on activation).
        """
        skills: dict[str, SkillPackage] = {}

        for skill_path in self._skill_directories():
            if not skill_path.exists():
                continue

            for skill_dir in sorted(skill_path.iterdir(), key=lambda p: p.name):
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                skill = self._parse_skill(skill_dir, skill_file)
                if skill is not None and skill.name not in skills:
                    # First discovery wins (priority order)
                    skills[skill.name] = skill

        return list(skills.values())

    def get_skill(self, name: str) -> SkillPackage | None:
        """
        Get a specific skill by name.

        Args:
            name: The skill name to look up.

        Returns:
            The SkillPackage if found, None otherwise.
        """
        for skill in self.discover_skills():
            if skill.name == name:
                return skill

        return None

    def _skill_directories(self) -> list[Path]:
        """Get skill directories in priority order.

        Priority order:
        1. User-workspace: ~/.quenda/users/<user>/workspaces/<ws_id>/skills/ (highest)
        2. Agent package: <agent_package>/skills/ (bundled skills)
        3. User: ~/.quenda/skills/ (shared, lowest priority)
        """
        dirs: list[Path] = []

        # User-workspace skills (highest priority)
        if self.user_workspace_skills_path:
            dirs.append(self.user_workspace_skills_path)

        # Agent package bundled skills
        if self.agent_package_path:
            dirs.append(self.agent_package_path / "skills")

        # User-level skills (lowest priority)
        dirs.append(Path.home() / ".quenda" / "skills")

        return dirs

    def _parse_skill(self, skill_dir: Path, skill_file: Path) -> SkillPackage | None:
        """Parse a skill from its directory.

        Implements progressive disclosure (ADR-002):
        - Only parses frontmatter during discovery
        - Instructions are lazy-loaded when accessed
        """
        try:
            content = skill_file.read_text()
            frontmatter = self._parse_frontmatter(content)

            if frontmatter is None:
                logger.warning(f"Skill {skill_dir} has invalid frontmatter")
                return None

            # Resolve resources
            resources = self._resolve_resources(skill_dir, frontmatter)

            # Extract commands
            commands: list[str] = []
            if frontmatter.quenda:
                for trigger in frontmatter.quenda.activates_on:
                    if trigger.command:
                        commands.append(trigger.command)

            # Determine source
            source = self._determine_source(skill_dir)

            return SkillPackage(
                path=skill_dir,
                name=frontmatter.name,
                version=frontmatter.version,
                description=frontmatter.description,
                skill_md_path=skill_file,
                frontmatter=frontmatter,
                resources=resources,
                commands=commands,
                source=source,
            )
        except Exception as e:
            logger.warning(f"Failed to parse skill {skill_dir}: {e}")
            return None

    def _parse_frontmatter(self, content: str) -> SkillFrontmatter | None:
        """Parse YAML frontmatter from skill content.

        Only parses the frontmatter section, not the instructions.
        """
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            fm_data = yaml.safe_load(parts[1])
            if fm_data is None:
                return None
            return SkillFrontmatter(**fm_data)
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            return None

    def _resolve_resources(
        self,
        skill_dir: Path,
        frontmatter: SkillFrontmatter,
    ) -> list[SkillResource]:
        """Resolve resource references from skill directory."""
        resources: list[SkillResource] = []

        if frontmatter.quenda is None:
            return resources

        catalog = frontmatter.quenda.resources

        for ref in catalog.references:
            ref_path = skill_dir / ref.path
            if ref_path.exists():
                resources.append(SkillResource(
                    path=ref_path,
                    type="reference",
                    description=ref.description,
                ))

        for asset in catalog.assets:
            asset_path = skill_dir / asset.path
            if asset_path.exists():
                resources.append(SkillResource(
                    path=asset_path,
                    type="asset",
                    description=asset.description,
                    safe_to_execute=asset.safe,
                ))

        return resources

    def _determine_source(self, skill_dir: Path) -> Literal["user_workspace", "agent_package", "user", "system"]:
        """Determine the source level of a skill.

        Priority order matches discovery order:
        - user_workspace: user-specific skills for this workspace (highest)
        - agent_package: bundled with agent
        - user: shared across workspaces (lowest)
        - system: fallback for any other location
        """
        # Check user-workspace first
        if self.user_workspace_skills_path:
            try:
                skill_dir.relative_to(self.user_workspace_skills_path)
                return "user_workspace"
            except ValueError:
                pass

        # Check agent package
        if self.agent_package_path:
            try:
                skill_dir.relative_to(self.agent_package_path)
                return "agent_package"
            except ValueError:
                pass

        # Check user level
        try:
            skill_dir.relative_to(Path.home() / ".quenda")
            return "user"
        except ValueError:
            pass

        return "system"


__all__ = ["SkillDiscovery"]
