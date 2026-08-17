"""
Session data models.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionMessage(BaseModel):
    """A message in a session."""

    id: str
    session_id: str
    role: str  # "user", "assistant", "tool"
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None
    created_at: datetime
    tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    run_id: str | None = None
    attachments: list["SessionAttachment"] = Field(default_factory=list)


class SessionAttachment(BaseModel):
    """A file attached to one user message."""

    id: str
    name: str
    media_type: str
    size: int
    path: str


class SessionActivity(BaseModel):
    """A compact, inspectable Runtime event recorded for the Web UI."""

    id: str
    run_id: str = ""
    type: str
    title: str
    summary: str = ""
    status: str = "completed"
    created_at: datetime
    duration_ms: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class SessionInteraction(BaseModel):
    """A durable human-input request associated with a paused turn."""

    id: str
    session_id: str
    run_id: str = ""
    kind: str
    title: str
    message: str = ""
    options: list[dict[str, Any]] = Field(default_factory=list)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    default_option_id: str | None = None
    multiple: bool = False
    required: bool = True
    status: str = "pending"
    created_at: datetime
    answered_at: datetime | None = None
    response: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[SessionAttachment] = Field(default_factory=list)


class SessionInfo(BaseModel):
    """Session information."""
    id: str
    agent_id: str
    workspace_id: str | None = None
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0
    status: str = "active"  # "active", "archived"
    agent_name: str | None = None
    workspace_name: str | None = None
    workspace_path: str | None = None
    provider: str | None = None
    model: str | None = None


class SessionUsage(BaseModel):
    """Token usage for a session."""
    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    message_count: int = 0
