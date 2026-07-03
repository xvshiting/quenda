"""
Skill Resource URI - Stable identifiers for skill resources.

The skill:// URI scheme provides a stable, installation-independent way
to reference resources within skills.

Format: skill://<skill-name>/<resource-path>
Examples:
  skill://code-review/checklist.md
  skill://calculate-nums/scripts/add.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillResourceURI:
    """
    Stable identifier for a skill resource.

    The skill:// URI scheme provides:
    - Stable identifiers independent of installation location
    - Clear namespace separation from workspace files
    - Easy validation and parsing

    Attributes:
        skill_name: The skill's unique identifier
        resource_path: Relative path within the skill directory

    Examples:
        >>> uri = SkillResourceURI.parse("skill://code-review/checklist.md")
        >>> uri.skill_name
        'code-review'
        >>> uri.resource_path
        'checklist.md'
    """

    skill_name: str
    resource_path: str

    def __post_init__(self) -> None:
        """Validate the URI components."""
        # Validate skill name: lowercase, alphanumeric, dashes, underscores
        if not re.match(r"^[a-z0-9-_]+$", self.skill_name):
            raise ValueError(
                f"Invalid skill name: {self.skill_name}. "
                "Skill names must be lowercase alphanumeric with dashes and underscores."
            )

        # Validate resource path: no traversal, no absolute paths
        if ".." in self.resource_path:
            raise ValueError(
                f"Invalid resource path: {self.resource_path}. "
                "Path traversal (..) is not allowed."
            )
        if self.resource_path.startswith("/"):
            raise ValueError(
                f"Invalid resource path: {self.resource_path}. "
                "Absolute paths are not allowed."
            )
        if not self.resource_path:
            raise ValueError("Resource path cannot be empty.")

    @classmethod
    def parse(cls, uri: str) -> SkillResourceURI | None:
        """
        Parse a skill:// URI string.

        Args:
            uri: The URI string to parse (e.g., "skill://code-review/checklist.md")

        Returns:
            SkillResourceURI if valid, None if invalid format
        """
        if not uri.startswith("skill://"):
            return None

        # Remove "skill://" prefix and split
        remainder = uri[8:]  # len("skill://") == 8
        if not remainder:
            return None

        # Split into skill_name and resource_path
        parts = remainder.split("/", 1)
        if len(parts) != 2:
            return None

        skill_name, resource_path = parts

        # Basic validation before construction
        if not skill_name or not resource_path:
            return None

        try:
            return cls(skill_name=skill_name, resource_path=resource_path)
        except ValueError:
            return None

    def __str__(self) -> str:
        """Return the URI as a string."""
        return f"skill://{self.skill_name}/{self.resource_path}"


__all__ = ["SkillResourceURI"]
