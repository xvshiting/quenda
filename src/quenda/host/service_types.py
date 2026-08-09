"""
Host Service types for Interface-neutral agent control.

These types are used by HostService and should NOT include:
- HTTP status codes
- Cookie
- WebSocket
- Browser Origin
- ASGI Request
- JSON Response

They belong to the Host layer, not to any specific interface (CLI, Web, etc.).

ADR-032: Host Service as Interface-neutral Control Interface
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from quenda.host.identity import User
    from quenda.kernel.types import ImageContent, TextContent
    from quenda.runtime.events import AnyEvent


# =============================================================================
# Session Types
# =============================================================================


@dataclass
class CreateSessionRequest:
    """Request to create or resume a session."""

    agent_path: Path
    workspace_path: Path
    session_id: str | None = None
    provider: str | None = None
    model: str | None = None


@dataclass
class SessionInfo:
    """Information about a session."""

    id: str
    agent_name: str
    workspace_id: str
    workspace_path: Path | None
    provider: str
    model: str
    created_at: datetime
    message_count: int = 0
    mode: str = "chat"
    user: User | None = None


@dataclass
class SessionList:
    """List of sessions for a workspace."""

    workspace_id: str
    sessions: list[SessionInfo] = field(default_factory=list)


# =============================================================================
# Run Types
# =============================================================================


class RunStatus(StrEnum):
    """Status of a run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class StartRunRequest:
    """Request to start a new run."""

    session_id: str
    message: str | Sequence[TextContent | ImageContent]


@dataclass
class RunHandle:
    """Handle to a running or completed run."""

    id: str
    session_id: str
    status: RunStatus
    created_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# Event Types
# =============================================================================


@dataclass
class EventEnvelope:
    """
    Envelope for events sent to interfaces.

    Wraps AnyEvent with additional metadata for transport.
    """

    run_id: str
    session_id: str
    event: AnyEvent
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# Interaction Types
# =============================================================================


@dataclass
class InteractionResponseRequest:
    """Request to respond to an interaction."""

    request_id: str
    session_id: str
    response: Any  # The response depends on interaction kind


# =============================================================================
# Permission Types
# =============================================================================


@dataclass
class PermissionDecisionRequest:
    """Request to make a permission decision."""

    request_id: str
    session_id: str
    decision: str  # "allow" or "deny"
    remember: bool = False


# =============================================================================
# Interrupt Types
# =============================================================================


@dataclass
class InterruptRequest:
    """Request to interrupt a running run."""

    run_id: str
    session_id: str


# =============================================================================
# Context Types
# =============================================================================


@dataclass
class ContextSource:
    """A source of context for the agent."""

    name: str
    type: str  # "agent_md", "user_md", "memory_md", "skill", etc.
    path: Path | None = None
    description: str | None = None


@dataclass
class ContextInfo:
    """Information about the current context."""

    sources: list[ContextSource] = field(default_factory=list)
    active_skills: list[str] = field(default_factory=list)
    transient_skills: list[str] = field(default_factory=list)
    mode: str = "chat"


# =============================================================================
# Memory Types
# =============================================================================


@dataclass
class MemorySearchRequest:
    """Request to search memory."""

    query: str
    limit: int = 10
    session_id: str | None = None


@dataclass
class MemorySearchResult:
    """Result of a memory search."""

    query: str
    results: list[MemoryFile] = field(default_factory=list)


@dataclass
class MemoryFile:
    """A memory file."""

    path: str
    title: str | None = None
    snippet: str | None = None
    content: str | None = None
    modified_at: datetime | None = None


# =============================================================================
# RequestContext (for future multi-user scenarios)
# =============================================================================


@dataclass
class RequestContext:
    """
    Context for a request (for future multi-user scenarios).

    Currently used to pass request metadata through the service layer.
    In local CLI mode, this is minimal.
    """

    user: User | None = None
    client_type: str = "cli"  # "cli", "web", "api", etc.
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    # Session
    "CreateSessionRequest",
    "SessionInfo",
    "SessionList",
    # Run
    "RunStatus",
    "StartRunRequest",
    "RunHandle",
    # Event
    "EventEnvelope",
    # Interaction
    "InteractionResponseRequest",
    # Permission
    "PermissionDecisionRequest",
    # Interrupt
    "InterruptRequest",
    # Context
    "ContextSource",
    "ContextInfo",
    # Memory
    "MemorySearchRequest",
    "MemorySearchResult",
    "MemoryFile",
    # Request
    "RequestContext",
]
