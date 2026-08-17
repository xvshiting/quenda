"""
Agent data models.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentSummary(BaseModel):
    """Summary of an agent (for listing)."""
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    model: str | None = None
    provider: str | None = None
    tool_count: int = 0
    home_path: str | None = None
    workspace_path: str | None = None
    created_from: str | None = None


class AgentConfig(BaseModel):
    """Full agent configuration."""
    id: str
    name: str
    description: str | None = None
    system_prompt: str | None = None
    tools: list[str] = []
    model: str | None = None
    provider: str | None = None
    home_path: str | None = None
    workspace_path: str | None = None
    created_from: str | None = None
    config_yaml: str | None = None  # Raw YAML config
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = {}


class AgentTemplate(BaseModel):
    """Agent template for quick creation."""
    id: str
    name: str
    description: str
    category: str  # "coding", "chat", "analysis", etc.
    config: dict[str, Any]
