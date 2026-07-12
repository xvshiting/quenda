"""Tests for Host one-shot runner helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from quenda.host import runner


class FakeSession:
    def __init__(self, session_id: str = "session-1") -> None:
        self.id = session_id
        self.sent_message: object | None = None
        self.on_event = None
        self.skill_activation_handler = None
        self.saved = False
        self.system_prompt: str | None = None

    def send_sync(
        self,
        message: object,
        *,
        on_event=None,
        skill_activation_handler=None,
    ) -> str:
        self.sent_message = message
        self.on_event = on_event
        self.skill_activation_handler = skill_activation_handler
        return "ok"

    def save(self) -> None:
        self.saved = True

    def set_system_prompt(self, prompt: str | None) -> None:
        self.system_prompt = prompt


class FakeAgent:
    def __init__(self) -> None:
        self.opened_session: FakeSession | None = None
        self.loaded_session_ids: list[str] = []
        self.mcp_calls: list[tuple[object, object]] = []
        self.system_prompt: str | None = None

    def open_session(self, *, session_id: str | None = None) -> FakeSession:
        self.opened_session = FakeSession(session_id or "new-session")
        return self.opened_session

    def load_session(self, session_id: str) -> FakeSession | None:
        self.loaded_session_ids.append(session_id)
        return None

    def set_mcp(self, manager: object, config: object) -> None:
        self.mcp_calls.append((manager, config))

    def set_system_prompt(self, prompt: str | None) -> None:
        self.system_prompt = prompt


class FakeSkillActivator:
    def __init__(self) -> None:
        self.active: set[str] = set()

    def is_active(self, name: str) -> bool:
        return name in self.active

    def activate_skill(self, name: str, *, transient: bool) -> object:
        assert transient is True
        self.active.add(name)
        return object()

    def list_persistent(self) -> list[str]:
        return []

    def list_transient(self) -> list[str]:
        return sorted(self.active)


def make_setup() -> tuple[Any, FakeAgent]:
    agent = FakeAgent()
    binding = SimpleNamespace(
        mcp_manager=None,
        active_skill_names=[],
        transient_skill_names=[],
    )
    setup = SimpleNamespace(
        agent=agent,
        binding=binding,
        agent_package=SimpleNamespace(config=None),
        skill_activator=FakeSkillActivator(),
        context_snapshot=None,
        instruction_sources=[],
    )
    return setup, agent


def test_run_agent_once_opens_sends_and_saves(monkeypatch, tmp_path: Path) -> None:
    setup, agent = make_setup()
    seen: dict[str, object] = {}

    monkeypatch.setattr(runner, "setup_agent", lambda *args, **kwargs: setup)

    ok = runner.run_agent_once(
        agent_path=tmp_path / "agent",
        workspace=tmp_path,
        user_message="hello",
        on_event=lambda event: seen.setdefault("event", event),
        on_setup=lambda setup_arg, session_arg: seen.update(
            setup=setup_arg,
            session=session_arg,
        ),
    )

    assert ok is True
    assert agent.opened_session is not None
    assert agent.opened_session.sent_message == "hello"
    assert agent.opened_session.on_event is not None
    assert agent.opened_session.skill_activation_handler is not None
    assert agent.opened_session.saved is True
    assert seen["setup"] is setup
    assert seen["session"] is agent.opened_session


def test_run_agent_once_resumes_or_creates_named_session(monkeypatch, tmp_path: Path) -> None:
    setup, agent = make_setup()
    monkeypatch.setattr(runner, "setup_agent", lambda *args, **kwargs: setup)

    ok = runner.run_agent_once(
        agent_path=tmp_path / "agent",
        workspace=tmp_path,
        user_message="hello",
        session_id="session-42",
    )

    assert ok is True
    assert agent.loaded_session_ids == ["session-42"]
    assert agent.opened_session is not None
    assert agent.opened_session.id == "session-42"


def test_skill_activation_handler_refreshes_prompt(monkeypatch) -> None:
    setup, agent = make_setup()
    session = FakeSession()
    snapshot = SimpleNamespace(
        composed_prompt="updated prompt",
        instruction_sources=["source"],
    )
    monkeypatch.setattr(runner, "refresh_run_context", lambda *args, **kwargs: snapshot)

    handler = runner.create_skill_activation_handler(setup, session)

    assert handler(["python"]) == "updated prompt"
    assert setup.binding.transient_skill_names == ["python"]
    assert setup.context_snapshot is snapshot
    assert setup.instruction_sources == ["source"]
    assert session.system_prompt == "updated prompt"
    assert agent.system_prompt == "updated prompt"
