"""
Host Service - Interface-neutral agent control interface.

This module provides the HostService, which is the interface-neutral
control interface for agents. Both CLI and Server should use this
same interface to control agent execution.

ADR-032: Host Service as Interface-neutral Control Interface
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence
from uuid import uuid4

from quenda.host.service_types import (
    ContextInfo,
    ContextSource,
    CreateSessionRequest,
    EventEnvelope,
    InterruptRequest,
    InteractionResponseRequest,
    MemoryFile,
    MemorySearchRequest,
    MemorySearchResult,
    PermissionDecisionRequest,
    RequestContext,
    RunHandle,
    RunStatus,
    SessionInfo,
    StartRunRequest,
)
from quenda.host.runner import (
    AgentSetup,
    create_skill_activation_handler,
    setup_agent,
)
from quenda.runtime.events import AnyEvent, InteractionRequested, PermissionRequested
from quenda.kernel.types import ImageContent, TextContent

if TYPE_CHECKING:
    from quenda.host.identity import User
    from quenda.runtime.agent import Agent
    from quenda.runtime.session import Session


@dataclass
class ActiveRun:
    """Tracks an active run and its control handles."""

    handle: RunHandle
    session: Session
    agent: Agent
    setup: AgentSetup
    task: asyncio.Task | None = None
    event_queue: asyncio.Queue[AnyEvent | None] = field(default_factory=asyncio.Queue)
    interaction_futures: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    permission_futures: dict[str, asyncio.Future[str]] = field(default_factory=dict)
    interrupt_requested: bool = False


class HostService:
    """
    Interface-neutral agent control service.

    This service provides the control interface for agents that is
    independent of any specific interface (CLI, Web, etc.).

    Responsibilities:
    - Session lifecycle management
    - Run execution and control
    - Event streaming
    - Interaction handling
    - Permission handling
    - Interrupt handling

    NOT responsible for:
    - HTTP routing
    - Authentication
    - WebSocket management
    - UI rendering
    """

    def __init__(self) -> None:
        """Initialize the HostService."""
        # session_id -> (Agent, AgentSetup, Session)
        self._active_sessions: dict[str, tuple[Agent, AgentSetup, Session]] = {}
        # run_id -> ActiveRun
        self._active_runs: dict[str, ActiveRun] = {}

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        request: CreateSessionRequest,
        context: RequestContext | None = None,
    ) -> SessionInfo:
        """
        Create or resume a session.

        Args:
            request: The session creation request.
            context: Optional request context (for future multi-user).

        Returns:
            SessionInfo with session details.

        Raises:
            ValueError: If agent setup fails.
        """
        # Setup agent
        setup = setup_agent(
            request.agent_path,
            request.workspace_path,
            provider=request.provider,
            model=request.model,
        )

        if setup is None:
            raise ValueError(f"Failed to setup agent from {request.agent_path}")

        agent = setup.agent

        # Create or resume session
        if request.session_id:
            session = agent.load_session(request.session_id)
            if session is None:
                session = agent.open_session(session_id=request.session_id)
        else:
            session = agent.open_session()

        # Track the session (save the triple: agent, setup, session)
        self._active_sessions[session.id] = (agent, setup, session)

        return SessionInfo(
            id=session.id,
            agent_name=setup.agent_package.name if setup.agent_package else "agent",
            workspace_id=setup.workspace_id,
            workspace_path=request.workspace_path,
            provider=setup.provider_name,
            model=setup.model_name,
            created_at=datetime.now(),
            message_count=len(session.messages),
            mode=session.mode,
            user=setup.user if hasattr(setup, 'user') else None,
        )

    def get_session(self, session_id: str) -> SessionInfo | None:
        """
        Get information about a session.

        Args:
            session_id: The session ID.

        Returns:
            SessionInfo if found, None otherwise.
        """
        if session_id not in self._active_sessions:
            return None

        agent, setup, session = self._active_sessions[session_id]

        return SessionInfo(
            id=session.id,
            agent_name=setup.agent_package.name if setup.agent_package else "agent",
            workspace_id=setup.workspace_id,
            workspace_path=setup.workspace_path,
            provider=setup.provider_name,
            model=setup.model_name,
            created_at=datetime.now(),
            message_count=len(session.messages),
            mode=session.mode,
            user=setup.user if hasattr(setup, 'user') else None,
        )

    def list_sessions(self, workspace_id: str) -> list[SessionInfo]:
        """
        List sessions for a workspace.

        Args:
            workspace_id: The workspace ID.

        Returns:
            List of SessionInfo objects.
        """
        # TODO: Implement session listing from storage
        # For now, return only active sessions
        result = []
        for session_id, (agent, setup, session) in self._active_sessions.items():
            if setup.workspace_id == workspace_id:
                result.append(SessionInfo(
                    id=session.id,
                    agent_name=setup.agent_package.name if setup.agent_package else "agent",
                    workspace_id=setup.workspace_id,
                    workspace_path=setup.workspace_path,
                    provider=setup.provider_name,
                    model=setup.model_name,
                    created_at=datetime.now(),
                    message_count=len(session.messages),
                    mode=session.mode,
                    user=setup.user if hasattr(setup, 'user') else None,
                ))
        return result

    # =========================================================================
    # Run Management
    # =========================================================================

    async def start_run(
        self,
        request: StartRunRequest,
        context: RequestContext | None = None,
    ) -> RunHandle:
        """
        Start a new run asynchronously.

        Args:
            request: The run start request.
            context: Optional request context.

        Returns:
            RunHandle for tracking the run.

        Raises:
            ValueError: If session not found.
        """
        if request.session_id not in self._active_sessions:
            raise ValueError(f"Session {request.session_id} not found")

        agent, setup, session = self._active_sessions[request.session_id]

        # Create run handle
        run_id = f"run_{uuid4().hex[:8]}"
        handle = RunHandle(
            id=run_id,
            session_id=request.session_id,
            status=RunStatus.RUNNING,
            created_at=datetime.now(),
        )

        # Create active run tracking
        active_run = ActiveRun(
            handle=handle,
            session=session,
            agent=agent,
            setup=setup,
        )

        self._active_runs[run_id] = active_run

        # Start the run task
        active_run.task = asyncio.create_task(
            self._execute_run(
                active_run,
                request.message,
            )
        )

        return handle

    async def stream_events(
        self,
        run_id: str,
    ) -> AsyncIterator[EventEnvelope]:
        """
        Stream events from a run.

        Args:
            run_id: The run ID.

        Yields:
            EventEnvelope objects.

        Raises:
            ValueError: If run not found.
        """
        if run_id not in self._active_runs:
            raise ValueError(f"Run {run_id} not found")

        active_run = self._active_runs[run_id]

        while True:
            event = await active_run.event_queue.get()

            # Check for termination sentinel (None)
            if event is None:
                break

            # Wrap in envelope
            envelope = EventEnvelope(
                run_id=run_id,
                session_id=active_run.session.id,
                event=event,
            )

            yield envelope

    def get_run(self, run_id: str) -> RunHandle | None:
        """
        Get information about a run.

        Args:
            run_id: The run ID.

        Returns:
            RunHandle if found, None otherwise.
        """
        if run_id not in self._active_runs:
            return None
        return self._active_runs[run_id].handle

    # =========================================================================
    # Interaction Handling
    # =========================================================================

    async def respond_to_interaction(
        self,
        request: InteractionResponseRequest,
        context: RequestContext | None = None,
    ) -> None:
        """
        Respond to an interaction request.

        Args:
            request: The interaction response request.
            context: Optional request context.

        Raises:
            ValueError: If run not found or not paused.
        """
        if request.session_id not in self._active_sessions:
            raise ValueError(f"Session {request.session_id} not found")

        # Find the active run for this session
        active_run = None
        for run in self._active_runs.values():
            if run.session.id == request.session_id:
                active_run = run
                break

        if active_run is None:
            raise ValueError(f"No active run for session {request.session_id}")

        if active_run.handle.status != RunStatus.PAUSED:
            raise ValueError(f"Run {active_run.handle.id} is not paused")

        # Set the response on the future
        future = active_run.interaction_futures.get(request.request_id)
        if future is None:
            raise ValueError(f"No pending interaction request {request.request_id}")

        if not future.done():
            future.set_result(request.response)

    # =========================================================================
    # Permission Handling
    # =========================================================================

    async def decide_permission(
        self,
        request: PermissionDecisionRequest,
        context: RequestContext | None = None,
    ) -> None:
        """
        Make a permission decision.

        Args:
            request: The permission decision request.
            context: Optional request context.

        Raises:
            ValueError: If run not found or not paused.
        """
        if request.session_id not in self._active_sessions:
            raise ValueError(f"Session {request.session_id} not found")

        # Find the active run for this session
        active_run = None
        for run in self._active_runs.values():
            if run.session.id == request.session_id:
                active_run = run
                break

        if active_run is None:
            raise ValueError(f"No active run for session {request.session_id}")

        if active_run.handle.status != RunStatus.PAUSED:
            raise ValueError(f"Run {active_run.handle.id} is not paused")

        # Set the decision on the future
        future = active_run.permission_futures.get(request.request_id)
        if future is None:
            raise ValueError(f"No pending permission request {request.request_id}")

        if not future.done():
            future.set_result(request.decision)

    # =========================================================================
    # Interrupt Handling
    # =========================================================================

    async def interrupt_run(
        self,
        request: InterruptRequest,
        context: RequestContext | None = None,
    ) -> None:
        """
        Interrupt a running run.

        Args:
            request: The interrupt request.
            context: Optional request context.

        Raises:
            ValueError: If run not found or not running.
        """
        if request.run_id not in self._active_runs:
            raise ValueError(f"Run {request.run_id} not found")

        active_run = self._active_runs[request.run_id]

        if active_run.handle.status != RunStatus.RUNNING:
            raise ValueError(f"Run {request.run_id} is not running")

        # Set interrupt flag
        active_run.interrupt_requested = True

        # Cancel the task if it exists
        if active_run.task:
            active_run.task.cancel()

    # =========================================================================
    # Context Management
    # =========================================================================

    def get_context(self, session_id: str) -> ContextInfo:
        """
        Get context information for a session.

        Args:
            session_id: The session ID.

        Returns:
            ContextInfo with context details.

        Raises:
            ValueError: If session not found.
        """
        if session_id not in self._active_sessions:
            raise ValueError(f"Session {session_id} not found")

        agent, setup, session = self._active_sessions[session_id]

        # Build context sources
        sources: list[ContextSource] = []

        # Agent MD
        if setup.agent_package:
            sources.append(ContextSource(
                name="AGENT.md",
                type="agent_md",
                path=setup.agent_package.path / "AGENT.md",
                description="Agent definition and instructions",
            ))

        # User MD
        user_md = setup.workspace_path / "USER.md"
        if user_md.exists():
            sources.append(ContextSource(
                name="USER.md",
                type="user_md",
                path=user_md,
                description="User preferences",
            ))

        # Memory MD
        memory_md = setup.workspace_path / "MEMORY.md"
        if memory_md.exists():
            sources.append(ContextSource(
                name="MEMORY.md",
                type="memory_md",
                path=memory_md,
                description="Cross-project context",
            ))

        # Active skills
        active_skills = []
        transient_skills = []
        if setup.skill_activator:
            active_skills = setup.skill_activator.list_persistent()
            transient_skills = setup.skill_activator.list_transient()

            for skill_name in active_skills:
                sources.append(ContextSource(
                    name=f"Skill: {skill_name}",
                    type="skill",
                    description=f"Active skill: {skill_name}",
                ))

        return ContextInfo(
            sources=sources,
            active_skills=active_skills,
            transient_skills=transient_skills,
            mode=setup.agent.mode if hasattr(setup.agent, 'mode') else "chat",
        )

    # =========================================================================
    # Memory Management
    # =========================================================================

    async def search_memory(
        self,
        request: MemorySearchRequest,
        context: RequestContext | None = None,
    ) -> MemorySearchResult:
        """
        Search the memory library.

        Args:
            request: The memory search request.
            context: Optional request context.

        Returns:
            MemorySearchResult with matching files.
        """
        # TODO: Implement memory search using memory_search tool
        # For now, return empty result
        return MemorySearchResult(
            query=request.query,
            results=[],
        )

    async def get_memory_file(
        self,
        path: str,
        context: RequestContext | None = None,
    ) -> MemoryFile | None:
        """
        Get a memory file.

        Args:
            path: The memory file path.
            context: Optional request context.

        Returns:
            MemoryFile if found, None otherwise.
        """
        # TODO: Implement memory file reading using memory_get tool
        return None

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _execute_run(
        self,
        active_run: ActiveRun,
        message: str | Sequence[TextContent | ImageContent],
    ) -> None:
        """
        Execute a run and stream events.

        This is the internal implementation that runs in a task.
        """
        try:
            # Create skill activation handler
            skill_handler = create_skill_activation_handler(
                active_run.setup,
                active_run.session,
            )

            # Callback to handle events
            def on_event(event: AnyEvent) -> None:
                """Handle events from the run."""
                # Put event in queue (synchronously)
                # The queue will be consumed by stream_events()
                active_run.event_queue.put_nowait(event)

            # Execute the run using Session.send() - it's async!
            await active_run.session.send(
                message,
                on_event=on_event,
                skill_activation_handler=skill_handler,
            )

            # Mark as completed
            if active_run.handle.status == RunStatus.RUNNING:
                active_run.handle.status = RunStatus.COMPLETED

        except asyncio.CancelledError:
            active_run.handle.status = RunStatus.INTERRUPTED

        except Exception as e:
            active_run.handle.status = RunStatus.FAILED
            # Put error event in queue
            from quenda.runtime.events import ErrorOccurred
            active_run.event_queue.put_nowait(ErrorOccurred(
                error_message=str(e),
                error_type=type(e).__name__,
            ))

        finally:
            # Always send termination sentinel
            active_run.event_queue.put_nowait(None)


__all__ = [
    "HostService",
    "ActiveRun",
]
