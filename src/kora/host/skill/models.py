"""
Pydantic models for SKILL.md parsing.

These models define the schema for skill frontmatter and metadata.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActivationTrigger(BaseModel):
    """
    Activation conditions for a skill.

    Skills can be activated by:
    - Command: A slash command like "/review"
    - File pattern: A glob pattern for contextual activation (deferred)
    """

    command: str | None = None
    file_pattern: str | None = None


class ResourceReference(BaseModel):
    """A reference document within a skill."""

    path: str
    description: str = ""


class AssetReference(BaseModel):
    """An asset (template, script, etc.) within a skill."""

    path: str
    type: Literal["template", "script", "data", "other"] = "other"
    description: str = ""
    safe: bool = False  # Must be explicitly true for script execution


class ResourceCatalog(BaseModel):
    """Declared resources for a skill."""

    references: list[ResourceReference] = Field(default_factory=list)
    assets: list[AssetReference] = Field(default_factory=list)


class ToolRequirements(BaseModel):
    """Tool dependencies and provisions (deferred to post-MVP)."""

    requires: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)


class TrustMetadata(BaseModel):
    """Trust and permission metadata (deferred to post-MVP)."""

    sources: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class SkillKoraMetadata(BaseModel):
    """Kora-specific skill configuration."""

    activates_on: list[ActivationTrigger] = Field(default_factory=list)
    resources: ResourceCatalog = Field(default_factory=ResourceCatalog)
    tools: ToolRequirements = Field(default_factory=ToolRequirements)
    trust: TrustMetadata = Field(default_factory=TrustMetadata)


class SkillFrontmatter(BaseModel):
    """
    SKILL.md frontmatter schema.

    Required fields:
    - name: Unique skill identifier (lowercase, alphanumeric, dashes, underscores)
    - description: Human-readable description

    Optional fields:
    - version: Semantic version (default: "0.1.0")
    - kora: Kora-specific metadata
    """

    name: str = Field(..., pattern=r"^[a-z0-9-_]+$")
    description: str
    version: str = Field(default="0.1.0")
    kora: SkillKoraMetadata | None = None


__all__ = [
    "ActivationTrigger",
    "ResourceReference",
    "AssetReference",
    "ResourceCatalog",
    "ToolRequirements",
    "TrustMetadata",
    "SkillKoraMetadata",
    "SkillFrontmatter",
]
