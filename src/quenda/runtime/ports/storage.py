"""
Storage capability protocol for Runtime layer.

Runtime needs to persist session and run state. This module defines
the interface (port) that Runtime uses, while Host provides implementations
like FileStorage, DatabaseStorage, etc.

Architecture:
    Runtime (needs storage)
        ↓ uses Storage protocol
    Host (provides FileStorage implementation)

Key principle: Runtime owns the interface, Host owns the implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from quenda.kernel.types import Message
    from quenda.runtime.session import SessionState
    from quenda.runtime.state import RunState


class Storage(Protocol):
    """
    Storage capability that Runtime needs.

    This protocol defines the persistence operations for Session and Run state.
    Runtime calls these methods without knowing the implementation details.

    Implementations:
    - Host layer: FileStorage (JSON files), DatabaseStorage (future)
    - Test layer: InMemoryStorage for testing

    Usage:
        storage: Storage = FileStorage()
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


__all__ = ["Storage"]
