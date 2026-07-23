"""
Runtime state models for Quenda.

This module defines state objects that belong to the Runtime layer:
- RunState: Persistable state for a single agent execution
- These are pure data structures with no persistence logic.

Architecture:
- Runtime owns the state definitions (what needs to be persisted)
- Host provides Storage implementations (how to persist)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RunState:
    """
    Persistable run state.

    A run represents a single execution of an agent within a session.
    This data class captures the essential information for persistence.

    This belongs to Runtime layer because:
    - Runtime creates and owns run execution
    - Runtime decides what needs to be persisted
    - Host only provides the persistence mechanism
    """

    id: str
    session_id: str
    agent_name: str
    status: str  # "completed", "failed", "interrupted", "terminated"
    user_message: str
    final_content: str | None
    step_count: int
    created_at: datetime
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for persistence."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "user_message": self.user_message,
            "final_content": self.final_content,
            "step_count": self.step_count,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RunState:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            agent_name=data["agent_name"],
            status=data["status"],
            user_message=data["user_message"],
            final_content=data.get("final_content"),
            step_count=data["step_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )


__all__ = ["RunState"]
