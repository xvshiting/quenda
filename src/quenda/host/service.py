"""
Host Service - Interface-neutral agent control interface.

This module provides the HostService, which is the interface-neutral
control interface for agents. Both CLI and Server should use this
same interface to control agent execution.

ADR-032: Host Service as Interface-neutral Control Interface
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from concurrent.futures import Future as ThreadFuture
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from quenda.host.permission_manager import PermissionManager
from quenda.host.prompt import build_prompt_cache_event
from quenda.host.runner import (
    AgentSetup,
    create_skill_activation_handler,
    refresh_run_context,
    setup_agent,
)
from quenda.host.service_types import (
    ContextInfo,
    ContextSource,
    CreateSessionRequest,
    EventEnvelope,
    InteractionResponseRequest,
    InterruptRequest,
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
from quenda.kernel.types import ImageContent, TextContent
from quenda.runtime.cancellation import CancellationToken
from quenda.runtime.events import (
    AnyEvent,
    InteractionRequested,
    PermissionRequested,
)

if TYPE_CHECKING:
    from quenda.host.prompt import PromptAssembly
    from quenda.runtime.agent import Agent
    from quenda.runtime.session import Session


@dataclass
class ActiveRun:
    """Tracks an active run and its control handles."""

    handle: RunHandle
    session: Session
    agent: Agent
    setup: AgentSetup
    task: asyncio.Task[None] | None = None
    event_queue: asyncio.Queue[AnyEvent | None] = field(default_factory=asyncio.Queue)
    interaction_futures: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    permission_futures: dict[str, asyncio.Future[str]] = field(default_factory=dict)
    interrupt_requested: bool = False
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)


@dataclass
class ActiveSession:
    """Internal state for an active session."""

    agent: Agent
    setup: AgentSetup
    session: Session
    permission_manager: PermissionManager
    last_prompt_assembly: PromptAssembly | None = None


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
        # session_id -> ActiveSession
        self._active_sessions: dict[str, ActiveSession] = {}
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

        Note:
            Sessions are currently tracked in-memory only.
            TODO: Implement storage persistence for session recovery after service restart.
            The context parameter will be used for user identity and resource isolation
            in multi-tenant deployments (ADR-XXX: Multi-tenancy Support).
        """
        permission_manager = PermissionManager()

        # Setup agent
        setup = setup_agent(
            request.agent_path,
            request.workspace_path,
            provider=request.provider,
            model=request.model,
            permission_policy=permission_manager,
        )

        if setup is None:
            raise ValueError(f"Failed to setup agent from {request.agent_path}")

        agent = setup.agent

        if context and context.user and context.user.id != setup.user.id:
            raise PermissionError(
                f"Request user {context.user.id!r} does not match "
                f"session user {setup.user.id!r}"
            )

        # Create or resume session
        if request.session_id:
            session = agent.load_session(request.session_id)
            if session is None:
                session = agent.open_session(session_id=request.session_id)
        else:
            session = agent.open_session()

        # Track the session (save the triple: agent, setup, session)
        self._active_sessions[session.id] = ActiveSession(
            agent=agent,
            setup=setup,
            session=session,
            permission_manager=permission_manager,
            last_prompt_assembly=getattr(
                setup.context_snapshot,
                "prompt_assembly",
                None,
            ),
        )

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

        active_session = self._active_sessions[session_id]

        return SessionInfo(
            id=active_session.session.id,
            agent_name=active_session.setup.agent_package.name if active_session.setup.agent_package else "agent",
            workspace_id=active_session.setup.workspace_id,
            workspace_path=active_session.setup.workspace_path,
            provider=active_session.setup.provider_name,
            model=active_session.setup.model_name,
            created_at=datetime.now(),
            message_count=len(active_session.session.messages),
            mode=active_session.session.mode,
            user=active_session.setup.user if hasattr(active_session.setup, 'user') else None,
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
        seen: set[str] = set()
        for _session_id, active_session in self._active_sessions.items():
            if active_session.setup.workspace_id == workspace_id:
                seen.add(active_session.session.id)
                result.append(SessionInfo(
                    id=active_session.session.id,
                    agent_name=active_session.setup.agent_package.name if active_session.setup.agent_package else "agent",
                    workspace_id=active_session.setup.workspace_id,
                    workspace_path=active_session.setup.workspace_path,
                    provider=active_session.setup.provider_name,
                    model=active_session.setup.model_name,
                    created_at=datetime.now(),
                    message_count=len(active_session.session.messages),
                    mode=active_session.session.mode,
                    user=active_session.setup.user if hasattr(active_session.setup, 'user') else None,
                ))

        for active_session in self._active_sessions.values():
            if active_session.setup.workspace_id != workspace_id:
                continue
            list_sessions = getattr(active_session.agent, "list_sessions", None)
            if not callable(list_sessions):
                continue
            for stored in list_sessions():
                if stored.id in seen:
                    continue
                seen.add(stored.id)
                result.append(SessionInfo(
                    id=stored.id,
                    agent_name=stored.agent_name,
                    workspace_id=workspace_id,
                    workspace_path=active_session.setup.workspace_path,
                    provider=active_session.setup.provider_name,
                    model=active_session.setup.model_name,
                    created_at=stored.created_at,
                    message_count=len(stored.messages),
                    mode=stored.metadata.get("mode", "chat"),
                    user=active_session.setup.user,
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

        active_statuses = {
            RunStatus.PENDING,
            RunStatus.RUNNING,
            RunStatus.PAUSED,
        }
        conflicting_run = next(
            (
                run
                for run in self._active_runs.values()
                if run.handle.session_id == request.session_id
                and run.handle.status in active_statuses
            ),
            None,
        )
        if conflicting_run is not None:
            raise ValueError(
                f"Session {request.session_id} already has active run "
                f"{conflicting_run.handle.id}"
            )

        active_session = self._active_sessions[request.session_id]

        snapshot = refresh_run_context(
            active_session.setup.binding,
            session_id=active_session.session.id,
            mode=active_session.session.mode,
        )
        active_session.setup.context_snapshot = snapshot
        active_session.setup.instruction_sources = snapshot.instruction_sources
        active_session.session.set_system_prompt(snapshot.composed_prompt)
        set_agent_prompt = getattr(active_session.agent, "set_system_prompt", None)
        if callable(set_agent_prompt):
            set_agent_prompt(snapshot.composed_prompt)

        prompt_assembly = getattr(snapshot, "prompt_assembly", None)
        prompt_observation = (
            prompt_assembly.observe(active_session.last_prompt_assembly)
            if prompt_assembly is not None
            else None
        )
        active_session.last_prompt_assembly = prompt_assembly

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
            session=active_session.session,
            agent=active_session.agent,
            setup=active_session.setup,
        )

        self._active_runs[run_id] = active_run

        if prompt_observation is not None:
            active_run.event_queue.put_nowait(
                build_prompt_cache_event(prompt_observation, run_id=run_id)
            )

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

        active_run = next(
            (
                run for run in reversed(list(self._active_runs.values()))
                if run.session.id == request.session_id
                and request.request_id in run.interaction_futures
            ),
            None,
        )

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

        active_run = next(
            (
                run for run in reversed(list(self._active_runs.values()))
                if run.session.id == request.session_id
                and request.request_id in run.permission_futures
            ),
            None,
        )

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
            ValueError: If run not found, not running, or session mismatch.
        """
        if request.run_id not in self._active_runs:
            raise ValueError(f"Run {request.run_id} not found")

        active_run = self._active_runs[request.run_id]

        # Verify session ownership
        if active_run.handle.session_id != request.session_id:
            raise ValueError(
                f"Run {request.run_id} does not belong to session {request.session_id}"
            )

        if active_run.handle.status != RunStatus.RUNNING:
            raise ValueError(f"Run {request.run_id} is not running")

        # Set interrupt flag
        active_run.interrupt_requested = True
        active_run.cancellation_token.cancel()

        # Cancel the task if it exists
        if active_run.task:
            active_run.task.cancel()
            try:
                await active_run.task
            except asyncio.CancelledError:
                pass

        active_run.handle.status = RunStatus.INTERRUPTED
        # A task cancelled before its coroutine starts cannot execute the
        # _execute_run finally block, so close the stream explicitly here.
        active_run.event_queue.put_nowait(None)

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

        active_session = self._active_sessions[session_id]

        snapshot = refresh_run_context(
            active_session.setup.binding,
            session_id=active_session.session.id,
            mode=active_session.session.mode,
        )
        active_session.setup.context_snapshot = snapshot
        active_session.setup.instruction_sources = snapshot.instruction_sources

        sources = [
            ContextSource(
                name=source.path.name if source.path else source.scope.name,
                type=(
                    "agent_md"
                    if source.scope.name == "AGENT_PACKAGE"
                    else source.scope.name.lower()
                ),
                path=source.path,
                description=f"Resolved {source.scope.name.lower()} instructions",
            )
            for source in snapshot.instruction_sources
        ]

        # Backward-compatible fallback for setups without resolved sources.
        if not sources and active_session.setup.agent_package:
            sources.append(ContextSource(
                name="AGENT.md",
                type="agent_md",
                path=active_session.setup.agent_package.path / "AGENT.md",
                description="Agent definition and instructions",
            ))

        if not snapshot.instruction_sources and active_session.setup.workspace_path:
            user_md = active_session.setup.workspace_path / "USER.md"
            if user_md.exists():
                sources.append(ContextSource(
                    name="USER.md",
                    type="user_md",
                    path=user_md,
                    description="User preferences",
                ))

            memory_md = active_session.setup.workspace_path / "MEMORY.md"
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
        if active_session.setup.skill_activator:
            active_skills = active_session.setup.skill_activator.list_persistent()
            transient_skills = active_session.setup.skill_activator.list_transient()

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
            mode=active_session.setup.agent.mode if hasattr(active_session.setup.agent, 'mode') else "chat",
        )

    # =========================================================================
    # Memory Operations (ADR-XXX: Future Work)
    # =========================================================================

    async def search_memory(self, request: MemorySearchRequest) -> MemorySearchResult:
        """Search memory through the tools resolved for the session's agent."""
        active_session = self._resolve_memory_session(request.session_id)
        tool = self._resolve_memory_tool(active_session, "memory_search")
        result = tool.execute(query=request.query, limit=request.limit)

        matches: list[MemoryFile] = []
        for line in result.content.splitlines():
            stripped = line.strip()
            if not stripped or not stripped[0].isdigit() or ". " not in stripped:
                continue
            location = stripped.split(". ", 1)[1]
            path, _, line_number = location.partition(":")
            matches.append(MemoryFile(path=path, title=line_number or None))
        snippets = [
            line.strip() for line in result.content.splitlines()
            if line.strip() and not line.strip()[0].isdigit()
            and not line.startswith("Found ")
        ]
        for match, snippet in zip(matches, snippets, strict=False):
            match.snippet = snippet
        return MemorySearchResult(query=request.query, results=matches[:request.limit])

    async def get_memory_file(
        self,
        path: str,
        *,
        session_id: str | None = None,
    ) -> MemoryFile | None:
        """Read a memory file through the resolved memory tool."""
        active_session = self._resolve_memory_session(session_id)
        tool = self._resolve_memory_tool(active_session, "memory_get")
        result = tool.execute(path=path)
        if result.is_error:
            return None
        _header, separator, content = result.content.partition("\n\n")
        return MemoryFile(path=path, content=content if separator else result.content)

    def _resolve_memory_session(self, session_id: str | None) -> ActiveSession:
        if session_id is not None:
            if session_id not in self._active_sessions:
                raise ValueError(f"Session {session_id} not found")
            return self._active_sessions[session_id]
        if len(self._active_sessions) != 1:
            raise ValueError("session_id is required when multiple sessions are active")
        return next(iter(self._active_sessions.values()))

    @staticmethod
    def _resolve_memory_tool(active_session: ActiveSession, name: str) -> Any:
        catalog = active_session.setup.binding.loaded_tool_catalog
        spec = catalog.get(name) if catalog is not None else None
        if spec is None:
            raise ValueError(f"Memory tool {name!r} is not available")
        return spec.tool

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
            loop = asyncio.get_running_loop()
            active_session = self._active_sessions[active_run.session.id]

            def prompt_for_permission(request: Any) -> bool:
                call_id = f"permission_{uuid4().hex[:8]}"
                bridge: ThreadFuture[bool] = ThreadFuture()

                def publish_request() -> None:
                    future: asyncio.Future[str] = loop.create_future()
                    active_run.permission_futures[call_id] = future
                    active_run.handle.status = RunStatus.PAUSED
                    active_run.event_queue.put_nowait(PermissionRequested(
                        request=request,
                        tool_name=request.tool_name,
                        call_id=call_id,
                    ))

                    def finish(decision: asyncio.Future[str]) -> None:
                        bridge.set_result(decision.result() == "allow")

                    future.add_done_callback(finish)

                loop.call_soon_threadsafe(publish_request)
                return bridge.result()

            active_session.permission_manager.prompt_handler = prompt_for_permission

            # Create skill activation handler
            skill_handler = create_skill_activation_handler(
                active_run.setup,
                active_run.session,
            )

            # Callback to handle events
            def on_event(event: AnyEvent) -> None:
                """Handle events from the run."""
                if isinstance(event, InteractionRequested):
                    active_run.interaction_futures[event.call_id] = loop.create_future()
                    active_run.handle.status = RunStatus.PAUSED
                # Put event in queue (synchronously)
                # The queue will be consumed by stream_events()
                active_run.event_queue.put_nowait(event)

            next_message: Any = message
            while True:
                await active_run.session.send(
                    next_message,
                    on_event=on_event,
                    skill_activation_handler=skill_handler,
                    cancellation_token=active_run.cancellation_token,
                )
                if active_run.handle.status != RunStatus.PAUSED:
                    break

                pending_interactions = [
                    future for future in active_run.interaction_futures.values()
                    if not future.done()
                ]
                if pending_interactions:
                    next_message = await pending_interactions[-1]
                    active_run.handle.status = RunStatus.RUNNING
                    continue

                # Permission prompts resume the still-running Session.send call;
                # reaching here means the run completed after that decision.
                active_run.handle.status = RunStatus.RUNNING
                break

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
