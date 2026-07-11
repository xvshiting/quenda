"""
SkillPackage dataclass - A loaded skill package.

Analogous to AgentPackage, a SkillPackage represents a fully loaded
skill with all its resources and metadata.

Resources are auto-discovered from directory structure:
- references/ → reference resources (read-only)
- templates/ → template resources (read-only)
- assets/ → asset resources (read-only)
- scripts/ → executable scripts (.py files only)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from quenda.host.skill.models import SkillFrontmatter


# Resource directories and their types
RESOURCE_DIRECTORIES: dict[str, str] = {
    "references": "reference",
    "templates": "template",
    "assets": "asset",
    "scripts": "script",
}

# Directories that contain executable scripts
EXECUTABLE_DIRECTORIES = {"scripts"}


@dataclass
class SkillResource:
    """
    A resolved resource within a skill.

    Resources are lazily loaded - content is None until explicitly loaded.

    Attributes:
        path: Absolute path to the resource file
        type: Resource type (reference, template, asset, script)
        executable: Whether this resource can be executed (scripts/*.py only)
        description: Optional description (currently unused, for future use)
        content: Lazy-loaded content
    """

    path: Path
    type: Literal["reference", "template", "asset", "script"]
    executable: bool = False
    description: str = ""
    content: str | None = None  # Lazy-loaded


@dataclass
class SkillPackage:
    """
    A loaded skill package, analogous to AgentPackage.

    Skills are composable instruction packages that can be activated
    to modify agent behavior.

    Progressive disclosure (ADR-002):
    - Discovery: Only frontmatter is loaded
    - Activation: Instructions are parsed
    - Usage: Resources are loaded on demand

    Resources are auto-discovered from directory structure:
    - references/ → reference resources
    - templates/ → template resources
    - assets/ → asset resources
    - scripts/ → executable scripts (.py files)

    Attributes:
        path: Directory containing the skill
        name: Unique skill identifier
        version: Semantic version
        description: Human-readable description
        frontmatter: Parsed frontmatter
        skill_md_path: Path to SKILL.md
        skill_md: Cached SKILL.md content, loaded lazily
        instructions: Body content (after frontmatter) - lazy loaded
        resources: Auto-discovered resource files
        source: Where the skill was discovered
        active: Whether the skill is currently active
    """

    # Core metadata
    path: Path
    name: str
    version: str
    description: str

    # Parsed content
    frontmatter: SkillFrontmatter  # Parsed frontmatter
    skill_md_path: Path
    skill_md: str | None = None  # Lazy-loaded raw SKILL.md content
    _instructions: str | None = field(default=None, repr=False)  # Lazy-loaded

    # Auto-discovered resources
    resources: list[SkillResource] = field(default_factory=list)

    # Discovery metadata
    source: Literal["user_workspace", "workspace", "agent_package", "user", "system"] = "user_workspace"

    # Runtime state
    active: bool = False

    @property
    def instructions(self) -> str:
        """
        Get instructions, parsing from SKILL.md if not already done.

        This implements progressive disclosure - instructions are only
        parsed when actually accessed.
        """
        if self._instructions is None:
            raw = self._load_skill_md()
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    self._instructions = parts[2].strip()
                else:
                    self._instructions = raw
            else:
                self._instructions = raw
        return self._instructions

    @instructions.setter
    def instructions(self, value: str) -> None:
        """Set instructions directly."""
        self._instructions = value

    def _load_skill_md(self) -> str:
        """Load the raw SKILL.md text on demand."""
        if self.skill_md is None:
            self.skill_md = self.skill_md_path.read_text(encoding="utf-8")
        return self.skill_md

    def get_reference(self, name: str) -> SkillResource | None:
        """Get a reference resource by filename."""
        for r in self.resources:
            if r.type == "reference" and r.path.name == name:
                return r
        return None

    def get_template(self, name: str) -> SkillResource | None:
        """Get a template resource by filename."""
        for r in self.resources:
            if r.type == "template" and r.path.name == name:
                return r
        return None

    def get_asset(self, name: str) -> SkillResource | None:
        """Get an asset resource by filename."""
        for r in self.resources:
            if r.type == "asset" and r.path.name == name:
                return r
        return None

    def get_script(self, name: str) -> SkillResource | None:
        """Get an executable script by filename."""
        for r in self.resources:
            if r.executable and r.path.name == name:
                return r
        return None

    def load_resource_content(self, resource: SkillResource) -> str:
        """Lazily load resource content."""
        if resource.content is None:
            resource.content = resource.path.read_text()
        return resource.content


__all__ = [
    "SkillResource",
    "SkillPackage",
    "RESOURCE_DIRECTORIES",
    "EXECUTABLE_DIRECTORIES",
]
