"""
Skill discovery - Finding and loading skills from configured paths.

Skills are discovered in priority order:
1. User-workspace skills: ~/.quenda/users/<user>/workspaces/<ws_id>/skills/ (highest priority)
2. Project skills: <workspace>/.quenda/skills/
3. Project ecosystem skills: <workspace>/.agents/skills/
4. Agent-package bundled: <agent_package>/skills/
5. User-level cross-client: ~/.agents/skills/
6. User-level Quenda: ${QUENDA_HOME:-~/.quenda}/skills/

Resources are auto-discovered from directory structure:
- references/ → reference resources
- resources/ → generic reference resources
- templates/ → template resources
- assets/ → asset resources
- scripts/ → executable Python scripts at any depth under the directory
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

from quenda.host.skill.models import SkillFrontmatter
from quenda.host.skill.package import (
    EXECUTABLE_DIRECTORIES,
    RESOURCE_DIRECTORIES,
    SkillPackage,
    SkillResource,
)

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
    - User: ${QUENDA_HOME:-~/.quenda}/skills/
      (shared across workspaces, lowest priority)
    """

    def __init__(
        self,
        user_workspace_skills_path: Path | None = None,
        workspace_path: Path | None = None,
        agent_package_path: Path | None = None,
    ) -> None:
        """
        Initialize skill discovery.

        Args:
            user_workspace_skills_path: Path to user-workspace skills directory
                (e.g., ~/.quenda/users/<user>/workspaces/<ws_id>/skills/).
            workspace_path: Optional project workspace path. If provided,
                <workspace>/.quenda/skills and <workspace>/.agents/skills
                are discovered as project-level skills.
            agent_package_path: Optional path to agent package for bundled skills.
        """
        self.user_workspace_skills_path = user_workspace_skills_path
        self.workspace_path = workspace_path
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

            for skill_dir, skill_file in self._find_skill_packages(skill_path):
                skill = self._parse_skill(skill_dir, skill_file)
                if skill is not None and skill.name not in skills:
                    # First discovery wins (priority order)
                    skills[skill.name] = skill

        return list(skills.values())

    def _find_skill_packages(self, skills_root: Path) -> Iterator[tuple[Path, Path]]:
        """Yield Skill package directories below a root in stable path order.

        Directories without ``SKILL.md`` are category containers and are walked
        recursively. A directory containing ``SKILL.md`` is a package boundary,
        so its resource directories are never searched for additional Skills.
        Symlinked Skill packages are supported, while symlinked category trees
        are not followed to avoid cycles and unbounded traversal outside the
        configured root.
        """
        try:
            children = sorted(skills_root.iterdir(), key=lambda path: path.name)
        except OSError as error:
            logger.warning("Failed to scan skills directory %s: %s", skills_root, error)
            return

        for child in children:
            try:
                if not child.is_dir():
                    continue
                skill_file = child / "SKILL.md"
                if skill_file.is_file():
                    yield child, skill_file
                    continue
                if child.is_symlink():
                    continue
                yield from self._find_skill_packages(child)
            except OSError as error:
                logger.warning("Failed to inspect skill path %s: %s", child, error)

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

    def load_package(
        self,
        skill_dir: Path,
        *,
        source: Literal["user_workspace", "workspace", "agent_package", "user", "system"]
        | None = None,
    ) -> SkillPackage:
        """Load one explicitly selected package, including immutable snapshots."""
        resolved = skill_dir.expanduser().resolve()
        package = self._parse_skill(resolved, resolved / "SKILL.md")
        if package is None:
            raise ValueError(f"Invalid Skill package: {resolved}")
        if source is not None:
            package.source = source
        return package

    def _skill_directories(self) -> list[Path]:
        """Get skill directories in priority order.

        Priority order (per Agent Skills specification):
        1. User-workspace: ~/.quenda/users/<user>/workspaces/<ws_id>/skills/ (highest)
        2. Project-level .quenda/skills/ (project-specific shared skills)
        3. Project-level .agents/skills/ (cross-client interoperability)
        4. Agent package: <agent_package>/skills/ (bundled skills)
        5. User-level ~/.agents/skills/ (cross-client interoperability)
        6. User-level ${QUENDA_HOME:-~/.quenda}/skills/
           (client-specific, lowest priority)
        """
        dirs: list[Path] = []

        # User-workspace skills (highest priority)
        if self.user_workspace_skills_path:
            dirs.append(self.user_workspace_skills_path)

        project_root = self.workspace_path
        if project_root is None and self.agent_package_path:
            project_root = self._find_project_root(self.agent_package_path)

        # Project-level .quenda/skills/ (project-specific shared skills)
        if project_root:
            quenda_skills = project_root / ".quenda" / "skills"
            if quenda_skills.exists():
                dirs.append(quenda_skills)

            # Project-level .agents/skills/ (cross-client interoperability)
            agents_skills = project_root / ".agents" / "skills"
            if agents_skills.exists():
                dirs.append(agents_skills)

        # Agent package bundled skills
        if self.agent_package_path:
            dirs.append(self.agent_package_path / "skills")

        # User-level ~/.agents/skills/ (cross-client interoperability)
        user_agents_skills = Path.home() / ".agents" / "skills"
        if user_agents_skills.exists():
            dirs.append(user_agents_skills)

        # User-level ${QUENDA_HOME}/skills/ (client-specific, lowest priority)
        quenda_home = Path(os.environ.get("QUENDA_HOME", Path.home() / ".quenda")).expanduser()
        dirs.append(quenda_home / "skills")

        return dirs

    def _find_project_root(self, start_path: Path) -> Path | None:
        """Find project root by looking for .git or other project markers."""
        # Walk up from start_path to find project root
        current = start_path
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def _parse_skill(self, skill_dir: Path, skill_file: Path) -> SkillPackage | None:
        """Parse a skill from its directory.

        Implements progressive disclosure (ADR-002):
        - Only parses frontmatter during discovery
        - Instructions are lazy-loaded when accessed
        - Resources are auto-discovered from directory structure
        """
        try:
            content = skill_file.read_text()
            frontmatter = self._parse_frontmatter(content)

            if frontmatter is None:
                logger.warning(f"Skill {skill_dir} has invalid frontmatter")
                return None

            # Auto-discover resources from directory structure
            resources = self._discover_resources(skill_dir)

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

        frontmatter = parts[1]
        try:
            try:
                fm_data = yaml.safe_load(frontmatter)
            except yaml.YAMLError:
                # Claude Code accepts unquoted argument hints containing ``: ``,
                # even though YAML treats that sequence as a mapping delimiter.
                # Retry with only that optional, presentation-only scalar quoted;
                # all other malformed YAML remains an error.
                compatible_frontmatter = self._quote_plain_argument_hint(frontmatter)
                if compatible_frontmatter == frontmatter:
                    raise
                fm_data = yaml.safe_load(compatible_frontmatter)

            if fm_data is None:
                return None
            return SkillFrontmatter(**fm_data)
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            return None

    @staticmethod
    def _quote_plain_argument_hint(frontmatter: str) -> str:
        """Quote a top-level plain ``argument-hint`` scalar when needed."""
        repaired_lines: list[str] = []
        for line in frontmatter.splitlines(keepends=True):
            stripped = line.rstrip("\r\n")
            newline = line[len(stripped) :]
            prefix = "argument-hint:"
            if stripped.startswith(prefix):
                value = stripped[len(prefix) :].strip()
                if value and not value.startswith(('"', "'", "|", ">")) and ": " in value:
                    line = f"{prefix} {json.dumps(value, ensure_ascii=False)}{newline}"
            repaired_lines.append(line)
        return "".join(repaired_lines)

    def _discover_resources(self, skill_dir: Path) -> list[SkillResource]:
        """
        Auto-discover resources from directory structure.

        Resource directories:
        - references/ → reference resources (read-only)
        - resources/ → generic reference resources (read-only)
        - templates/ → template resources (read-only)
        - assets/ → asset resources (read-only)
        - scripts/ → executable Python scripts at any depth under the directory
        """
        resources: list[SkillResource] = []

        for dir_name, resource_type in RESOURCE_DIRECTORIES.items():
            resource_dir = skill_dir / dir_name
            if not resource_dir.exists() or not resource_dir.is_dir():
                continue

            is_executable_dir = dir_name in EXECUTABLE_DIRECTORIES

            for file_path in sorted(resource_dir.rglob("*")):
                if not file_path.is_file():
                    continue

                # Every .py file anywhere under the top-level scripts/ tree is executable.
                executable = is_executable_dir and file_path.suffix == ".py"

                resources.append(
                    SkillResource(
                        path=file_path,
                        type=resource_type,  # type: ignore
                        executable=executable,
                    )
                )

        return resources

    def _determine_source(
        self, skill_dir: Path
    ) -> Literal["user_workspace", "workspace", "agent_package", "user", "system"]:
        """Determine the source level of a skill.

        Priority order matches discovery order:
        - user_workspace: user-specific skills for this workspace (highest)
        - workspace: project-shared skills under .quenda/skills or .agents/skills
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

        # Check project workspace skills
        if self.workspace_path:
            try:
                skill_dir.relative_to(self.workspace_path / ".quenda" / "skills")
                return "workspace"
            except ValueError:
                pass
            try:
                skill_dir.relative_to(self.workspace_path / ".agents" / "skills")
                return "workspace"
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
            skill_dir.relative_to(Path.home() / ".agents" / "skills")
            return "user"
        except ValueError:
            pass
        try:
            skill_dir.relative_to(Path.home() / ".quenda")
            return "user"
        except ValueError:
            pass

        return "system"


__all__ = ["SkillDiscovery"]
