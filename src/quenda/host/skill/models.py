"""
Pydantic models for SKILL.md parsing.

Simplified skill schema focusing on what's actually used:
- name: Required skill identifier
- description: Required human-readable description
- version: Optional semantic version
- resources: Optional references and assets

See docs/skills.md for the full specification.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResourceReference(BaseModel):
    """A reference document within a skill."""

    path: str
    description: str = ""


class AssetReference(BaseModel):
    """An asset (template, script, etc.) within a skill."""

    path: str
    type: Literal["template", "script", "data", "other"] = "other"
    description: str = ""


class ResourceCatalog(BaseModel):
    """Declared resources for a skill."""

    references: list[ResourceReference] = Field(default_factory=list)
    assets: list[AssetReference] = Field(default_factory=list)


class SkillFrontmatter(BaseModel):
    """
    SKILL.md frontmatter schema.

    Minimal schema that works:
    - name: Required, unique identifier
    - description: Required, primary triggering mechanism
    - version: Optional, defaults to "0.1.0"
    - resources: Optional, references and assets

    Example:
        ---
        name: code-review
        description: Apply when reviewing code or providing feedback on code changes.
        version: "1.0.0"
        resources:
          references:
            - path: "guides/style-guide.md"
              description: "Style guidelines"
          assets:
            - path: "templates/report.md"
              type: template
        ---
    """

    name: str = Field(..., pattern=r"^[a-z0-9-_]+$")
    description: str
    version: str = Field(default="0.1.0")
    resources: ResourceCatalog | None = None


__all__ = [
    "ResourceReference",
    "AssetReference",
    "ResourceCatalog",
    "SkillFrontmatter",
]
