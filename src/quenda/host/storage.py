"""
Storage interface and implementations for Kora Host layer.

Provides pluggable persistence for Session and Run state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from quenda.kernel.types import Message
    from quenda.runtime.session import SessionState


@dataclass
class RunState:
    """
    Persistable run state.

    A run represents a single execution of an agent within a session.
    This data class captures the essential information for persistence.
    """

    id: str
    session_id: str
    agent_name: str
    status: str  # "completed", "failed"
    user_message: str
    final_content: str | None
    step_count: int
    created_at: datetime
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
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


class Storage(Protocol):
    """
    Pluggable storage interface for Host layer.

    This protocol defines the persistence operations for Session and Run state.
    Implementations can use different backends (file system, database, etc.).

    Usage:
        storage = FileStorage()
        storage.save_session(session_state)
        loaded = storage.load_session(session_id)
    """

    # Session operations

    def save_session(self, state: SessionState) -> None:
        """
        Persist session state.

        Args:
            state: The session state to persist.
        """
        ...

    def load_session(self, session_id: str) -> SessionState | None:
        """
        Load a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            The session state, or None if not found.
        """
        ...

    def list_sessions(
        self,
        agent_name: str | None = None,
        user_id: str | None = None,
    ) -> list[SessionState]:
        """
        List sessions, optionally filtered.

        Args:
            agent_name: Filter by agent name.
            user_id: Filter by user ID (for multi-tenant scenarios).

        Returns:
            List of matching session states.
        """
        ...

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: The session identifier.

        Returns:
            True if the session existed and was deleted.
        """
        ...

    # Run operations

    def save_run(self, run: RunState) -> None:
        """
        Persist run state.

        Args:
            run: The run state to persist.
        """
        ...

    def load_run(self, run_id: str) -> RunState | None:
        """
        Load a run by ID.

        Args:
            run_id: The run identifier.

        Returns:
            The run state, or None if not found.
        """
        ...

    def list_runs(self, session_id: str) -> list[RunState]:
        """
        List runs for a session.

        Args:
            session_id: The session identifier.

        Returns:
            List of run states for the session.
        """
        ...

    # Archive operations (ADR-015)

    def save_archive(
        self,
        session_id: str,
        messages: list[Message],
        archive_id: str | None = None,
    ) -> str:
        """
        Archive raw messages before compression.

        Args:
            session_id: The session ID.
            messages: The messages to archive.
            archive_id: Optional archive ID (auto-generated if None).

        Returns:
            The archive ID.
        """
        ...

    def load_archive(self, session_id: str, archive_id: str) -> list[Message] | None:
        """
        Load archived messages.

        Args:
            session_id: The session ID.
            archive_id: The archive ID.

        Returns:
            The archived messages, or None if not found.
        """
        ...


@dataclass
class FileStorageConfig:
    """Configuration for FileStorage."""

    base_dir: Path = field(default_factory=lambda: Path(".quenda"))


class FileStorage:
    """
    JSON file-based storage implementation.

    Stores sessions and runs as JSON files in a directory structure:
    ```
    .quenda/
    ├── sessions/
    │   ├── <session_id>.json
    │   └── ...
    └── runs/
        ├── <run_id>.json
        └── ...
    ```

    Usage:
        storage = FileStorage()
        storage.save_session(session_state)
    """

    def __init__(self, config: FileStorageConfig | None = None) -> None:
        self.config = config or FileStorageConfig()
        self._sessions_dir = self.config.base_dir / "sessions"
        self._runs_dir = self.config.base_dir / "runs"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    # Session operations

    def save_session(self, state: SessionState) -> None:
        """Persist session state to JSON file."""
        from quenda.kernel.types import Message, ToolCall, ToolResult

        path = self._sessions_dir / f"{state.id}.json"

        # Serialize messages
        messages_data = []
        for msg in state.messages:
            if isinstance(msg.content, str):
                messages_data.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            else:
                # Handle ToolCall and ToolResult lists
                items = list(msg.content)
                if items and isinstance(items[0], ToolCall):
                    messages_data.append({
                        "role": msg.role,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                            for tc in items
                        ],
                    })
                elif items and isinstance(items[0], ToolResult):
                    messages_data.append({
                        "role": msg.role,
                        "tool_results": [
                            {
                                "call_id": tr.call_id,
                                "name": tr.name,
                                "content": tr.content,
                                "is_error": tr.is_error,
                            }
                            for tr in items
                        ],
                    })

        # Serialize usage
        usage_data = {
            "total_input_tokens": state.usage.total_input_tokens,
            "total_output_tokens": state.usage.total_output_tokens,
            "total_tokens": state.usage.total_tokens,
            "total_cached_input_tokens": state.usage.total_cached_input_tokens,
            "total_reasoning_tokens": state.usage.total_reasoning_tokens,
            "compression_count": state.usage.compression_count,
            "last_compressed_at": state.usage.last_compressed_at.isoformat() if state.usage.last_compressed_at else None,
        }

        # Serialize summary blocks
        summary_blocks_data = [
            {
                "content": block.content,
                "message_range": list(block.message_range),
                "created_at": block.created_at.isoformat(),
                "token_count": block.token_count,
            }
            for block in state.summary_blocks
        ]

        data = {
            "id": state.id,
            "agent_name": state.agent_name,
            "messages": messages_data,
            "metadata": state.metadata,
            "created_at": state.created_at.isoformat(),
            "usage": usage_data,
            "summary_blocks": summary_blocks_data,
            "archive_refs": state.archive_refs,
        }

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_session(self, session_id: str) -> SessionState | None:
        """Load session state from JSON file."""
        from quenda.kernel.types import Message, ToolCall, ToolResult
        from quenda.runtime.session import SessionState, SessionUsage, SummaryBlock

        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))

        # Deserialize messages
        messages = []
        for msg_data in data.get("messages", []):
            role = msg_data["role"]

            if "content" in msg_data:
                messages.append(Message(role=role, content=msg_data["content"]))
            elif "tool_calls" in msg_data:
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                    for tc in msg_data["tool_calls"]
                ]
                messages.append(Message(role=role, content=tool_calls))
            elif "tool_results" in msg_data:
                tool_results = [
                    ToolResult(
                        call_id=tr["call_id"],
                        name=tr["name"],
                        content=tr["content"],
                        is_error=tr.get("is_error", False),
                    )
                    for tr in msg_data["tool_results"]
                ]
                messages.append(Message(role=role, content=tool_results))

        # Deserialize usage
        usage_data = data.get("usage", {})
        usage = SessionUsage(
            total_input_tokens=usage_data.get("total_input_tokens", 0),
            total_output_tokens=usage_data.get("total_output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            total_cached_input_tokens=usage_data.get("total_cached_input_tokens"),
            total_reasoning_tokens=usage_data.get("total_reasoning_tokens"),
            compression_count=usage_data.get("compression_count", 0),
            last_compressed_at=datetime.fromisoformat(usage_data["last_compressed_at"])
                if usage_data.get("last_compressed_at") else None,
        )

        # Deserialize summary blocks
        summary_blocks = [
            SummaryBlock(
                content=block_data["content"],
                message_range=tuple(block_data["message_range"]),
                created_at=datetime.fromisoformat(block_data["created_at"]),
                token_count=block_data["token_count"],
            )
            for block_data in data.get("summary_blocks", [])
        ]

        state = SessionState(
            id=data["id"],
            agent_name=data["agent_name"],
            messages=messages,
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

        # Set new fields
        state.usage = usage
        state.summary_blocks = summary_blocks
        state.archive_refs = data.get("archive_refs", [])

        return state

    def list_sessions(
        self,
        agent_name: str | None = None,
        user_id: str | None = None,
    ) -> list[SessionState]:
        """List sessions, optionally filtered."""
        # Note: user_id is ignored in this simple implementation
        # Multi-tenant support would need to store user_id in session metadata
        sessions = []
        for path in self._sessions_dir.glob("*.json"):
            state = self.load_session(path.stem)
            if state is not None:
                if agent_name is None or state.agent_name == agent_name:
                    sessions.append(state)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        path = self._sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # Run operations

    def save_run(self, run: RunState) -> None:
        """Persist run state to JSON file."""
        path = self._runs_dir / f"{run.id}.json"
        path.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")

    def load_run(self, run_id: str) -> RunState | None:
        """Load run state from JSON file."""
        path = self._runs_dir / f"{run_id}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        return RunState.from_dict(data)

    def list_runs(self, session_id: str) -> list[RunState]:
        """List runs for a session."""
        runs = []
        for path in self._runs_dir.glob("*.json"):
            run = self.load_run(path.stem)
            if run is not None and run.session_id == session_id:
                runs.append(run)
        return runs

    # Archive operations (ADR-015)

    def save_archive(
        self,
        session_id: str,
        messages: list[Message],
        archive_id: str | None = None,
    ) -> str:
        """
        Archive raw messages before compression.

        Args:
            session_id: The session ID.
            messages: The messages to archive.
            archive_id: Optional archive ID (auto-generated if None).

        Returns:
            The archive ID.
        """
        from uuid import uuid4

        from quenda.kernel.types import ToolCall, ToolResult

        archive_id = archive_id or str(uuid4())
        archive_dir = self.config.base_dir / "archives" / session_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{archive_id}.json"

        # Serialize messages
        messages_data = []
        for msg in messages:
            if isinstance(msg.content, str):
                messages_data.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            else:
                items = list(msg.content)
                if items and isinstance(items[0], ToolCall):
                    messages_data.append({
                        "role": msg.role,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                            for tc in items
                        ],
                    })
                elif items and isinstance(items[0], ToolResult):
                    messages_data.append({
                        "role": msg.role,
                        "tool_results": [
                            {
                                "call_id": tr.call_id,
                                "name": tr.name,
                                "content": tr.content,
                                "is_error": tr.is_error,
                            }
                            for tr in items
                        ],
                    })

        archive_data = {
            "id": archive_id,
            "session_id": session_id,
            "messages": messages_data,
            "archived_at": datetime.now().isoformat(),
        }

        archive_path.write_text(
            json.dumps(archive_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return archive_id

    def load_archive(self, session_id: str, archive_id: str) -> list[Message] | None:
        """
        Load archived messages.

        Args:
            session_id: The session ID.
            archive_id: The archive ID.

        Returns:
            The archived messages, or None if not found.
        """
        from quenda.kernel.types import Message, ToolCall, ToolResult

        archive_path = self.config.base_dir / "archives" / session_id / f"{archive_id}.json"
        if not archive_path.exists():
            return None

        data = json.loads(archive_path.read_text(encoding="utf-8"))

        # Deserialize messages
        messages = []
        for msg_data in data.get("messages", []):
            role = msg_data["role"]

            if "content" in msg_data:
                messages.append(Message(role=role, content=msg_data["content"]))
            elif "tool_calls" in msg_data:
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                    for tc in msg_data["tool_calls"]
                ]
                messages.append(Message(role=role, content=tool_calls))
            elif "tool_results" in msg_data:
                tool_results = [
                    ToolResult(
                        call_id=tr["call_id"],
                        name=tr["name"],
                        content=tr["content"],
                        is_error=tr.get("is_error", False),
                    )
                    for tr in msg_data["tool_results"]
                ]
                messages.append(Message(role=role, content=tool_results))

        return messages


__all__ = [
    "RunState",
    "Storage",
    "FileStorageConfig",
    "FileStorage",
]
