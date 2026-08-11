"""
Agent data models.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class AgentSummary(BaseModel):
    """Summary of an agent (for listing)."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model: Optional[str] = None
    tool_count: int = 0


class AgentConfig(BaseModel):
    """Full agent configuration."""
    id: str
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: List[str] = []
    model: Optional[str] = None
    config_yaml: Optional[str] = None  # Raw YAML config
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}


class AgentTemplate(BaseModel):
    """Agent template for quick creation."""
    id: str
    name: str
    description: str
    category: str  # "coding", "chat", "analysis", etc.
    config: Dict[str, Any]
