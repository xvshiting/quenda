"""
Pydantic models for SKILL.md parsing.

Simplified skill schema:
- name: Required skill identifier
- description: Required human-readable description
- version: Optional semantic version

Resources are auto-discovered from directory structure:
- references/ → reference resources
- templates/ → template resources
- assets/ → asset resources
- scripts/ → executable scripts

See docs/skills.md for the full specification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillFrontmatter(BaseModel):
    """
    SKILL.md frontmatter schema.

    Minimal schema:
    - name: Required, unique identifier
    - description: Required, primary triggering mechanism
    - version: Optional, defaults to "0.1.0"

    Resources are auto-discovered from directory structure, not declared here.

    Example:
        ---
        name: code-review
        description: Apply when reviewing code or providing feedback on code changes.
        version: "1.0.0"
        ---
    """

    name: str = Field(..., pattern=r"^[a-z0-9-_]+$")
    description: str
    version: str = Field(default="0.1.0")


__all__ = ["SkillFrontmatter"]
