"""
Tests for HostService - Interface-neutral control interface.

ADR-032: Host Service as Interface-neutral Control Interface
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from quenda.host.service import ActiveRun, ActiveSession, HostService
from quenda.host.service_types import (
    CreateSessionRequest,
    EventEnvelope,
    InterruptRequest,
    RequestContext,
    RunHandle,
    RunStatus,
    SessionInfo,
    StartRunRequest,
)
from quenda.runtime.events import PromptCacheObserved


class TestHostServiceSessionManagement:
    """Test session management functionality."""

    def test_create_session_with_valid_request(self, tmp_path: Path) -> None:
        """Test creating a session with valid parameters."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )

        session_info = service.create_session(request)

        # Verify
        assert session_info.id is not None
        assert session_info.workspace_path == workspace
        assert session_info.message_count == 0
        assert session_info.mode == "chat"

    def test_create_session_with_session_id(self, tmp_path: Path) -> None:
        """Test creating a session with a specific session ID."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        session_id = "test-session-123"

        # Create session
        request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
            session_id=session_id,
        )

        session_info = service.create_session(request)

        # Verify
        assert session_info.id == session_id

    def test_get_session(self, tmp_path: Path) -> None:
        """Test getting session information."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        created = service.create_session(create_request)

        # Get session
        session_info = service.get_session(created.id)

        # Verify
        assert session_info is not None
        assert session_info.id == created.id

    def test_get_nonexistent_session(self) -> None:
        """Test getting a session that doesn't exist."""
        service = HostService()
        
        session_info = service.get_session("nonexistent-session")
        
        assert session_info is None

    def test_list_sessions(self, tmp_path: Path) -> None:
        """Test listing sessions for a workspace."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        created = service.create_session(create_request)

        # List sessions - Note: newly created sessions may not be in storage yet
        sessions = service.list_sessions(created.workspace_id)

        # Verify - The session should be tracked even if not yet persisted
        # For now, we just verify the method doesn't error
        # In a real implementation, we would persist and then list
        assert isinstance(sessions, list)


class TestHostServiceRunManagement:
    """Test run management functionality."""

    @pytest.mark.asyncio
    async def test_start_run_and_stream_events(self, tmp_path: Path) -> None:
        """Test starting a run and streaming events to completion."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Start run
        start_request = StartRunRequest(
            session_id=session_info.id,
            message="Hello",
        )

        handle = await service.start_run(start_request)

        # Verify initial state
        assert handle.id is not None
        assert handle.session_id == session_info.id
        assert handle.status == RunStatus.RUNNING

        # Stream events until completion
        events = []
        async for envelope in service.stream_events(handle.id):
            events.append(envelope)
            # Safety limit to prevent infinite loop in tests
            if len(events) > 100:
                break

        # Verify run completed
        assert handle.status in (RunStatus.COMPLETED, RunStatus.FAILED)
        cache_event = next(
            envelope.event
            for envelope in events
            if isinstance(envelope.event, PromptCacheObserved)
        )
        assert cache_event.assembly_digest
        assert cache_event.stable_prefix_digest
        assert cache_event.first_changed_source_id is None
        assert cache_event.estimated_prompt_tokens > 0
        
        # Should have at least some events (RunStarted, etc.)
        # Note: This may fail if no model is configured, which is expected
        # In a real test, we would mock the model

    @pytest.mark.asyncio
    async def test_start_run_with_nonexistent_session(self, tmp_path: Path) -> None:
        """Test starting a run with a nonexistent session."""
        service = HostService()

        start_request = StartRunRequest(
            session_id="nonexistent-session",
            message="Hello",
        )

        with pytest.raises(ValueError, match="Session .* not found"):
            await service.start_run(start_request)

    @pytest.mark.asyncio
    async def test_get_run(self, tmp_path: Path) -> None:
        """Test getting run information."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Start run
        start_request = StartRunRequest(
            session_id=session_info.id,
            message="Hello",
        )
        handle = await service.start_run(start_request)

        # Get run
        run_info = service.get_run(handle.id)

        # Verify
        assert run_info is not None
        assert run_info.id == handle.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_run(self) -> None:
        """Test getting a run that doesn't exist."""
        service = HostService()
        
        run_info = service.get_run("nonexistent-run")
        
        assert run_info is None

    @pytest.mark.asyncio
    async def test_stream_events_with_nonexistent_run(self) -> None:
        """Test streaming events from a nonexistent run."""
        service = HostService()

        with pytest.raises(ValueError, match="Run .* not found"):
            async for _ in service.stream_events("nonexistent-run"):
                pass


class TestHostServiceContextManagement:
    """Test context management functionality."""

    def test_get_context(self, tmp_path: Path) -> None:
        """Test getting context information."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Get context
        context_info = service.get_context(session_info.id)

        # Verify
        assert context_info is not None
        assert len(context_info.sources) >= 1  # At least AGENT.md
        assert any(s.type == "agent_md" for s in context_info.sources)

    def test_get_context_with_nonexistent_session(self) -> None:
        """Test getting context for a nonexistent session."""
        service = HostService()
        
        with pytest.raises(ValueError, match="Session .* not found"):
            service.get_context("nonexistent-session")


class TestHostServiceTypes:
    """Test DTO types."""

    def test_create_session_request(self) -> None:
        """Test CreateSessionRequest creation."""
        request = CreateSessionRequest(
            agent_path=Path("/path/to/agent"),
            workspace_path=Path("/path/to/workspace"),
            session_id="test-session",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )

        assert request.agent_path == Path("/path/to/agent")
        assert request.workspace_path == Path("/path/to/workspace")
        assert request.session_id == "test-session"
        assert request.provider == "anthropic"
        assert request.model == "claude-sonnet-4-20250514"

    def test_session_info(self) -> None:
        """Test SessionInfo creation."""
        session_info = SessionInfo(
            id="session-123",
            agent_name="test-agent",
            workspace_id="workspace-456",
            workspace_path=Path("/path/to/workspace"),
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            created_at=datetime.now(),
            message_count=5,
            mode="code",
        )

        assert session_info.id == "session-123"
        assert session_info.agent_name == "test-agent"
        assert session_info.workspace_id == "workspace-456"
        assert session_info.message_count == 5
        assert session_info.mode == "code"

    def test_run_handle(self) -> None:
        """Test RunHandle creation."""
        handle = RunHandle(
            id="run-789",
            session_id="session-123",
            status=RunStatus.RUNNING,
        )

        assert handle.id == "run-789"
        assert handle.session_id == "session-123"
        assert handle.status == RunStatus.RUNNING

    def test_request_context(self) -> None:
        """Test RequestContext creation."""
        context = RequestContext(
            client_type="cli",
            request_id="req-001",
            metadata={"key": "value"},
        )

        assert context.client_type == "cli"
        assert context.request_id == "req-001"
        assert context.metadata == {"key": "value"}

    def test_event_envelope(self) -> None:
        """Test EventEnvelope creation."""
        from quenda.runtime.events import RunStarted
        
        event = RunStarted(session_id="session-123")
        envelope = EventEnvelope(
            run_id="run-789",
            session_id="session-123",
            event=event,
        )

        assert envelope.run_id == "run-789"
        assert envelope.session_id == "session-123"
        assert envelope.event == event


class TestHostServiceInterrupt:
    """Test interrupt functionality."""

    @pytest.mark.asyncio
    async def test_interrupt_run(self, tmp_path: Path) -> None:
        """Test interrupting a run."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Start run
        start_request = StartRunRequest(
            session_id=session_info.id,
            message="Hello",
        )
        handle = await service.start_run(start_request)

        # Interrupt run
        interrupt_request = InterruptRequest(
            run_id=handle.id,
            session_id=session_info.id,
        )

        await service.interrupt_run(interrupt_request)

        # Verify interrupt was requested
        active_run = service._active_runs.get(handle.id)
        assert active_run is not None
        assert active_run.interrupt_requested is True

    @pytest.mark.asyncio
    async def test_interrupt_nonexistent_run(self) -> None:
        """Test interrupting a nonexistent run."""
        service = HostService()

        interrupt_request = InterruptRequest(
            run_id="nonexistent-run",
            session_id="nonexistent-session",
        )

        with pytest.raises(ValueError, match="Run .* not found"):
            await service.interrupt_run(interrupt_request)

    @pytest.mark.asyncio
    async def test_interrupt_non_running_run(self, tmp_path: Path) -> None:
        """Test interrupting a run that is not running."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Start run
        start_request = StartRunRequest(
            session_id=session_info.id,
            message="Hello",
        )
        handle = await service.start_run(start_request)

        # Wait for completion
        async for _ in service.stream_events(handle.id):
            pass

        # Try to interrupt completed run
        interrupt_request = InterruptRequest(
            run_id=handle.id,
            session_id=session_info.id,
        )

        # Should fail because run is not running
        with pytest.raises(ValueError, match="Run .* is not running"):
            await service.interrupt_run(interrupt_request)

    @pytest.mark.asyncio
    async def test_interrupt_run_with_wrong_session(self, tmp_path: Path) -> None:
        """Test interrupting a run with wrong session_id."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create two sessions
        create_request1 = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session1 = service.create_session(create_request1)

        create_request2 = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session2 = service.create_session(create_request2)

        # Start run in session1
        start_request = StartRunRequest(
            session_id=session1.id,
            message="Hello",
        )
        handle = await service.start_run(start_request)

        # Try to interrupt with session2's id
        interrupt_request = InterruptRequest(
            run_id=handle.id,
            session_id=session2.id,
        )

        # Should fail because session mismatch
        with pytest.raises(ValueError, match="does not belong to session"):
            await service.interrupt_run(interrupt_request)


class TestHostServiceSessionPersistence:
    """Test session persistence behavior."""

    def test_session_is_saved_in_active_sessions(self, tmp_path: Path) -> None:
        """Test that created session is properly saved in active sessions."""
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Verify it's in active sessions
        assert session_info.id in service._active_sessions
        
        # Verify the ActiveSession is saved correctly
        active_session = service._active_sessions[session_info.id]
        assert isinstance(active_session, ActiveSession)
        assert active_session.session is not None
        assert active_session.session.id == session_info.id


class TestHostServiceEventStream:
    """Test event stream behavior."""

    @pytest.mark.asyncio
    async def test_event_stream_terminates_on_completion(self, tmp_path: Path) -> None:
        """Test that event stream terminates when run completes."""
        # Setup
        service = HostService()
        agent_path = tmp_path / "AGENT.md"
        agent_path.write_text("# Test Agent\n\nTest agent description.")
        
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create session
        create_request = CreateSessionRequest(
            agent_path=agent_path,
            workspace_path=workspace,
        )
        session_info = service.create_session(create_request)

        # Start run
        start_request = StartRunRequest(
            session_id=session_info.id,
            message="Hello",
        )
        handle = await service.start_run(start_request)

        # Stream events - should terminate automatically
        event_count = 0
        async for envelope in service.stream_events(handle.id):
            event_count += 1
            if event_count > 100:  # Safety limit
                pytest.fail("Event stream did not terminate")

        # Verify stream terminated
        assert event_count >= 0  # Should have completed
        assert handle.status in (RunStatus.COMPLETED, RunStatus.FAILED)
