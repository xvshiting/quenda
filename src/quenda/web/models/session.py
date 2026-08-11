"""
Session data models.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class SessionMessage(BaseModel):
    """A message in a session."""
    id: str
    session_id: str
    role: str  # "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    tokens: Optional[int] = None


class SessionInfo(BaseModel):
    """Session information."""
    id: str
    agent_id: str
    workspace_id: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0
    status: str = "active"  # "active", "archived"


class SessionUsage(BaseModel):
    """Token usage for a session."""
    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    message_count: int = 0
