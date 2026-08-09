"""Behavioral contract tests for the interface-neutral HostService seam."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import quenda.host.service as service_module
from quenda.host.instructions import InstructionScope, InstructionSource
from quenda.host.service import HostService
from quenda.host.service_types import (
    CreateSessionRequest,
    InteractionResponseRequest,
    InterruptRequest,
    MemorySearchRequest,
    PermissionDecisionRequest,
    RequestContext,
    RunStatus,
    StartRunRequest,
)
from quenda.kernel.types import ToolResult
from quenda.runtime.events import (
    InteractionRequested,
    PermissionRequested,
    RunCompleted,
    RunPaused,
)
from quenda.runtime.permission import PermissionKind, PermissionRequest


class InteractionSession:
    """Fake Runtime session that pauses once, then completes after a response."""

    id = "session-1"
    mode = "chat"
    messages: list[Any] = []

    def __init__(self) -> None:
        self.id = "session-1"
        self.messages = []
        self.received: list[Any] = []
        self.system_prompt: str | None = None

    async def send(self, message: Any, *, on_event, **_: Any) -> str:
        self.received.append(message)
        if len(self.received) == 1:
            on_event(InteractionRequested(call_id="question-1", request={"prompt": "Name?"}))
            on_event(RunPaused(reason="interaction_requested"))
            return ""
        on_event(RunCompleted(session_id=self.id, final_content="Thanks"))
        return "Thanks"

    def save(self) -> None:
        """Match the public Runtime Session persistence interface."""

    def set_system_prompt(self, prompt: str | None) -> None:
        self.system_prompt = prompt


class PersistentAgent:
    """Storage-backed Agent boundary fake shared by multiple HostService instances."""

    def __init__(self) -> None:
        self.sessions: dict[str, InteractionSession] = {}

    def open_session(self, *, session_id: str | None = None) -> InteractionSession:
        session = InteractionSession()
        if session_id is not None:
            session.id = session_id

        def save() -> None:
            self.sessions[session.id] = session

        session.save = save  # type: ignore[method-assign]
        return session

    def load_session(self, session_id: str) -> InteractionSession | None:
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                id=session.id,
                agent_name="test-agent",
                messages=session.messages,
                metadata={"mode": session.mode},
                created_at=datetime(2026, 1, 1),
            )
            for session in self.sessions.values()
        ]


class PersistentSession(InteractionSession):
    async def send(self, message: Any, *, on_event, **_: Any) -> str:
        self.messages.append(message)
        self.save()
        on_event(RunCompleted(session_id=self.id, final_content="stored"))
        return "stored"


class PermissionSession(InteractionSession):
    def __init__(self) -> None:
        super().__init__()
        self.permission_manager: Any = None

    async def send(self, message: Any, *, on_event, **_: Any) -> str:
        self.received.append(message)
        allowed = await asyncio.to_thread(
            self.permission_manager.decide,
            PermissionRequest(
                kind=PermissionKind.FILESYSTEM_WRITE,
                resource="/tmp/result.txt",
                tool_name="write_file",
            ),
        )
        on_event(RunCompleted(session_id=self.id, final_content=str(allowed.allowed)))
        return str(allowed.allowed)


class RepeatingInteractionSession(InteractionSession):
    async def send(self, message: Any, *, on_event, **_: Any) -> str:
        self.received.append(message)
        if len(self.received) % 2:
            on_event(InteractionRequested(call_id="question-1", request={}))
            on_event(RunPaused(reason="interaction_requested"))
            return ""
        on_event(RunCompleted(session_id=self.id, final_content="done"))
        return "done"


class BlockingSession(InteractionSession):
    async def send(self, message: Any, *, on_event, **_: Any) -> str:
        await asyncio.Event().wait()
        return ""


def fake_setup(session: InteractionSession, tmp_path: Path) -> SimpleNamespace:
    agent = SimpleNamespace(
        open_session=lambda **_: session,
        load_session=lambda _session_id: session,
    )
    package = SimpleNamespace(name="test-agent", path=tmp_path)
    snapshot = SimpleNamespace(instruction_sources=[], composed_prompt="initial")
    binding = SimpleNamespace(
        workspace_path=tmp_path,
        loaded_tool_catalog=None,
        context_snapshot=snapshot,
    )
    return SimpleNamespace(
        agent=agent,
        agent_package=package,
        binding=binding,
        context_snapshot=snapshot,
        instruction_sources=[],
        workspace_id="workspace-1",
        workspace_path=tmp_path,
        provider_name="test",
        model_name="test",
        user=SimpleNamespace(id="local"),
        skill_activator=None,
    )


@pytest.fixture(autouse=True)
def use_fake_context_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module,
        "refresh_run_context",
        lambda binding, session_id="", mode="chat": binding.context_snapshot,
    )


@pytest.mark.asyncio
async def test_interaction_response_resumes_the_same_host_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = InteractionSession()
    monkeypatch.setattr(
        service_module,
        "setup_agent",
        lambda *_args, **_kwargs: fake_setup(session, tmp_path),
    )
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )

    handle = await service.start_run(
        StartRunRequest(session_id=created.id, message="Hello")
    )
    for _ in range(20):
        if handle.status is RunStatus.PAUSED:
            break
        await asyncio.sleep(0)

    assert handle.status is RunStatus.PAUSED
    await service.respond_to_interaction(
        InteractionResponseRequest(
            request_id="question-1",
            session_id=created.id,
            response="Ada",
        )
    )
    events = [envelope.event async for envelope in service.stream_events(handle.id)]

    assert handle.status is RunStatus.COMPLETED
    assert session.received == ["Hello", "Ada"]
    assert any(isinstance(event, RunCompleted) for event in events)


@pytest.mark.asyncio
async def test_interaction_response_targets_the_run_with_the_pending_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = RepeatingInteractionSession()
    monkeypatch.setattr(
        service_module,
        "setup_agent",
        lambda *_args, **_kwargs: fake_setup(session, tmp_path),
    )
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )

    for response in ("first", "second"):
        handle = await service.start_run(
            StartRunRequest(session_id=created.id, message=f"ask {response}")
        )
        for _ in range(20):
            if handle.status is RunStatus.PAUSED:
                break
            await asyncio.sleep(0)
        await service.respond_to_interaction(
            InteractionResponseRequest(
                request_id="question-1",
                session_id=created.id,
                response=response,
            )
        )
        _events = [event async for event in service.stream_events(handle.id)]
        assert handle.status is RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_permission_decision_resumes_the_same_host_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = PermissionSession()

    def setup(*_args: Any, **kwargs: Any) -> SimpleNamespace:
        session.permission_manager = kwargs["permission_policy"]
        return fake_setup(session, tmp_path)

    monkeypatch.setattr(service_module, "setup_agent", setup)
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )
    handle = await service.start_run(
        StartRunRequest(session_id=created.id, message="Write the file")
    )
    for _ in range(20):
        if handle.status is RunStatus.PAUSED:
            break
        await asyncio.sleep(0)

    assert handle.status is RunStatus.PAUSED
    stream = service.stream_events(handle.id)
    requested = await anext(stream)
    assert isinstance(requested.event, PermissionRequested)
    await service.decide_permission(
        PermissionDecisionRequest(
            request_id=requested.event.call_id,
            session_id=created.id,
            decision="allow",
        )
    )
    _events = [event async for event in stream]

    assert handle.status is RunStatus.COMPLETED
    assert session.received == ["Write the file"]


@pytest.mark.asyncio
async def test_interrupt_returns_with_terminal_status_and_closes_event_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = BlockingSession()
    monkeypatch.setattr(
        service_module,
        "setup_agent",
        lambda *_args, **_kwargs: fake_setup(session, tmp_path),
    )
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )
    handle = await service.start_run(
        StartRunRequest(session_id=created.id, message="Wait")
    )

    await service.interrupt_run(
        InterruptRequest(run_id=handle.id, session_id=created.id)
    )
    events = [event async for event in service.stream_events(handle.id)]

    assert handle.status is RunStatus.INTERRUPTED
    assert events == []


def test_request_context_cannot_access_another_users_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = InteractionSession()
    monkeypatch.setattr(
        service_module,
        "setup_agent",
        lambda *_args, **_kwargs: fake_setup(session, tmp_path),
    )
    service = HostService()

    with pytest.raises(PermissionError, match="does not match"):
        service.create_session(
            CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path),
            context=RequestContext(user=SimpleNamespace(id="other")),
        )


@pytest.mark.asyncio
async def test_session_history_is_recoverable_by_a_new_host_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = PersistentAgent()

    def setup(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        session = PersistentSession()

        def open_session(*, session_id: str | None = None) -> PersistentSession:
            opened = PersistentSession()
            opened.id = session_id or f"session-{len(agent.sessions) + 1}"

            def save() -> None:
                agent.sessions[opened.id] = opened

            opened.save = save  # type: ignore[method-assign]
            return opened

        result = fake_setup(session, tmp_path)
        result.agent = agent
        agent.open_session = open_session  # type: ignore[method-assign]
        return result

    monkeypatch.setattr(service_module, "setup_agent", setup)
    first_service = HostService()
    created = first_service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )
    handle = await first_service.start_run(
        StartRunRequest(session_id=created.id, message="Remember this")
    )
    _events = [
        envelope async for envelope in first_service.stream_events(handle.id)
    ]
    second_created = first_service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )
    second_handle = await first_service.start_run(
        StartRunRequest(session_id=second_created.id, message="Another session")
    )
    _events = [
        envelope async for envelope in first_service.stream_events(second_handle.id)
    ]

    second_service = HostService()
    resumed = second_service.create_session(
        CreateSessionRequest(
            agent_path=tmp_path,
            workspace_path=tmp_path,
            session_id=created.id,
        )
    )

    assert resumed.id == created.id
    assert resumed.message_count == 1
    assert second_service.get_session(created.id) is not None
    assert {item.id for item in second_service.list_sessions("workspace-1")} == {
        created.id,
        second_created.id,
    }


def test_get_context_reports_the_resolved_instruction_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = InteractionSession()
    soul = tmp_path / "SOUL.md"
    user = tmp_path / "private" / "USER.md"
    sources = [
        InstructionSource(
            scope=InstructionScope.AGENT_PACKAGE,
            content="agent",
            path=tmp_path / "AGENT.md",
        ),
        InstructionSource(
            scope=InstructionScope.USER_AGENT,
            content="soul",
            path=soul,
        ),
        InstructionSource(
            scope=InstructionScope.USER_GLOBAL,
            content="user",
            path=user,
        ),
    ]

    def setup(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        result = fake_setup(session, tmp_path)
        result.context_snapshot.instruction_sources = sources
        result.instruction_sources = sources
        return result

    monkeypatch.setattr(service_module, "setup_agent", setup)
    monkeypatch.setattr(
        service_module,
        "refresh_run_context",
        lambda _binding, session_id="", mode="chat": SimpleNamespace(
            instruction_sources=sources,
            composed_prompt="resolved",
        ),
    )
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )

    context = service.get_context(created.id)

    assert [source.path for source in context.sources] == [
        tmp_path / "AGENT.md",
        soul,
        user,
    ]


@pytest.mark.asyncio
async def test_memory_operations_use_the_resolved_agent_memory_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = InteractionSession()

    class SearchTool:
        def execute(self, **_: object) -> ToolResult:
            return ToolResult(
                "",
                "memory_search",
                'Found 1 memory result(s) for "Host":\n\n'
                "1. projects/quenda.md:3\nHostService owns session control.",
            )

    class GetTool:
        def execute(self, **_: object) -> ToolResult:
            return ToolResult(
                "",
                "memory_get",
                "projects/quenda.md:1-3\n\n# Quenda\n\nHostService owns session control.",
            )

    catalog = SimpleNamespace(
        get=lambda name: SimpleNamespace(
            tool=SearchTool() if name == "memory_search" else GetTool()
        )
    )

    def setup(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        result = fake_setup(session, tmp_path)
        result.binding.loaded_tool_catalog = catalog
        return result

    monkeypatch.setattr(service_module, "setup_agent", setup)
    service = HostService()
    created = service.create_session(
        CreateSessionRequest(agent_path=tmp_path, workspace_path=tmp_path)
    )

    matches = await service.search_memory(
        MemorySearchRequest(query="Host", session_id=created.id)
    )
    memory = await service.get_memory_file(
        "projects/quenda.md",
        session_id=created.id,
    )

    assert [match.path for match in matches.results] == ["projects/quenda.md"]
    assert matches.results[0].snippet == "HostService owns session control."
    assert memory is not None
    assert memory.content == "# Quenda\n\nHostService owns session control."
