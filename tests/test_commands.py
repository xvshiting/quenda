"""
Tests for the Slash Command system (ADR-008).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quenda.host.commands import (
    CommandCandidate,
    CommandContext,
    CommandRegistry,
    CommandResolution,
    create_default_registry,
    HelpCommand,
    ClearCommand,
    ExitCommand,
    ModeCommand,
    ModelCommand,
    SessionCommand,
    ContextCommand,
    ResetCommand,
    ReplAction,
    VALID_MODES,
)


@dataclass
class FakeSessionState:
    """Minimal fake session state."""
    agent_name: str = "test-agent"
    id: str = "test-state-id"
    created_at: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeAgentConfig:
    """Minimal fake agent config with tools list."""
    def __init__(self) -> None:
        self.tools: list = []
        self.system_prompt: str | None = None


class FakeSession:
    """Minimal fake session for testing commands."""

    def __init__(self, *, session_id: str = "test-session-id") -> None:
        self._id = session_id
        self._messages: list = []
        self._model = None
        self._state = FakeSessionState()
        self._agent = FakeAgentConfig()
        self._agent.system_prompt = "You are a helpful assistant using {{model.name}}."

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> FakeSessionState:
        return self._state

    @property
    def system_prompt(self) -> str | None:
        """Public API: get system prompt."""
        return self._agent.system_prompt

    @property
    def tools(self) -> list:
        """Public API: get tools."""
        return self._agent.tools

    @property
    def mode(self) -> str:
        """Public API: get current mode."""
        return self._state.metadata.get("mode", "chat")

    @mode.setter
    def mode(self, value: str) -> None:
        """Public API: set mode."""
        self._state.metadata["mode"] = value

    @property
    def model(self) -> Any:
        """Public API: get current model."""
        return self._model

    def clear(self) -> None:
        self._messages.clear()

    def set_model(self, model: Any) -> None:
        self._model = model

    def set_system_prompt(self, prompt: str | None) -> None:
        self._agent.system_prompt = prompt

    def save(self) -> None:
        pass

    def __len__(self) -> int:
        return len(self._messages)


class FakeAgent:
    """Minimal fake agent for testing commands."""

    def __init__(self) -> None:
        self._storage = None
        self._config = FakeAgentConfig()

    @property
    def tools(self) -> list:
        """Public API: get tools."""
        return self._config.tools

    @property
    def model(self) -> Any:
        return None

    @property
    def storage(self) -> Any:
        return self._storage

    @property
    def model(self) -> Any:
        return None

    @property
    def storage(self) -> Any:
        return self._storage

    @property
    def system_prompt(self) -> str | None:
        return self._config.system_prompt

    def list_sessions(self) -> list:
        return []

    def set_system_prompt(self, prompt: str | None) -> None:
        self._config.system_prompt = prompt


def make_context(session=None, agent=None) -> CommandContext:
    return CommandContext(
        session=FakeSession() if session is None else session,
        agent=FakeAgent() if agent is None else agent,
    )


class TestCommandRegistry:
    """Test the command registry itself."""

    def test_empty_registry(self) -> None:
        registry = CommandRegistry()
        assert len(registry) == 0
        assert registry.get("help") is None
        assert "help" not in registry

    def test_register_and_get(self) -> None:
        registry = CommandRegistry()

        class FakeCmd:
            name = "test"
            description = "A test command"
            usage = "/test"
            def execute(self, args, ctx):  # type: ignore
                from quenda.host.commands import CommandResult
                return CommandResult(status="ok", message="done")

        registry.register(FakeCmd())
        assert len(registry) == 1
        assert "test" in registry
        cmd = registry.get("test")
        assert cmd is not None
        assert cmd.name == "test"

    def test_list_commands(self) -> None:
        registry = CommandRegistry()

        class CmdA:
            name = "a"
            description = "cmd a"
            usage = "/a"
            def execute(self, args, ctx):  # type: ignore
                from quenda.host.commands import CommandResult
                return CommandResult(status="ok", message="a")

        class CmdB:
            name = "b"
            description = "cmd b"
            usage = "/b"
            def execute(self, args, ctx):  # type: ignore
                from quenda.host.commands import CommandResult
                return CommandResult(status="ok", message="b")

        registry.register(CmdA())
        registry.register(CmdB())
        names = [c.name for c in registry.list_commands()]
        assert "a" in names
        assert "b" in names


class TestDefaultRegistry:
    """Test the default command registry."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()

    def test_has_all_builtin_commands(self) -> None:
        expected = {"help", "clear", "exit", "session", "model", "mode", "context", "reset", "compress", "status", "skill"}
        actual = {c.name for c in self.registry.list_commands()}
        assert actual == expected

    def test_registry_is_reusable(self) -> None:
        r1 = create_default_registry()
        r2 = create_default_registry()
        assert r1.get("help") is not r2.get("help")  # Different instances


class TestHelpCommand:
    """Test the /help command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("help")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "help"
        assert self.cmd.description

    def test_lists_all_commands(self) -> None:
        ctx = make_context()
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        # Should mention all built-in commands
        for name in ("clear", "exit", "help", "session", "model", "mode", "context", "reset"):
            assert name in result.message


class TestClearCommand:
    """Test the /clear command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("clear")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "clear"
        assert self.cmd.description

    def test_clear_returns_ok(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert "Cleared" in result.message


class TestExitCommand:
    """Test the /exit command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("exit")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "exit"
        assert self.cmd.description

    def test_exit_returns_exit_action(self) -> None:
        ctx = make_context()
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert result.action == ReplAction.EXIT
        assert "Bye" in result.message


class TestSessionCommand:
    """Test the /session command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("session")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "session"
        assert self.cmd.description

    def test_session_info(self) -> None:
        session = FakeSession(session_id="my-session-12345")
        ctx = CommandContext(session=session, agent=FakeAgent())
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert "my-session-12345" in result.message

    def test_session_info_explicit(self) -> None:
        session = FakeSession(session_id="my-session-12345")
        ctx = make_context(session=session)
        result = self.cmd.execute("info", ctx)
        assert result.status == "ok"

    def test_session_list_no_storage(self) -> None:
        ctx = make_context()
        result = self.cmd.execute("list", ctx)
        assert result.status == "error"
        assert "No storage configured" in result.message


class TestModeCommand:
    """Test the /mode command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("mode")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "mode"
        assert self.cmd.description

    def test_show_current_mode(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert "chat" in result.message

    def test_switch_to_code_mode(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("code", ctx)
        assert result.status == "ok"
        assert "code" in result.message
        assert result.rebuild_context is True
        assert result.state_patch.get("mode") == "code"
        assert session.state.metadata.get("mode") == "code"

    def test_switch_to_architect_mode(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("architect", ctx)
        assert result.status == "ok"
        assert "architect" in result.message

    def test_invalid_mode(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("invalid", ctx)
        assert result.status == "error"

    def test_cannot_switch_to_same_mode(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("chat", ctx)
        assert result.status == "ok"
        assert "Already" in result.message

    def test_valid_modes_set(self) -> None:
        assert "chat" in VALID_MODES
        assert "code" in VALID_MODES
        assert "architect" in VALID_MODES


class TestContextCommand:
    """Test the /context command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("context")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "context"
        assert self.cmd.description

    def test_show_context(self) -> None:
        session = FakeSession()
        session._agent.system_prompt = "You are a test agent."
        ctx = make_context(session=session)
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert "System Prompt" in result.message
        assert "test agent" in result.message

    def test_show_context_explicit(self) -> None:
        session = FakeSession()
        session._agent.system_prompt = "Test prompt."
        ctx = make_context(session=session)
        result = self.cmd.execute("show", ctx)
        assert result.status == "ok"

    def test_show_tools(self) -> None:
        session = FakeSession()
        agent = FakeAgent()
        ctx = CommandContext(session=session, agent=agent)
        result = self.cmd.execute("tools", ctx)
        assert result.status == "ok"
        # No tools configured
        assert "0" in result.message or "No tools" in result.message

    def test_show_session(self) -> None:
        session = FakeSession(session_id="test-ses-123")
        ctx = make_context(session=session)
        result = self.cmd.execute("session", ctx)
        assert result.status == "ok"
        assert "test-ses-123" in result.message
        assert "chat" in result.message  # default mode

    def test_unknown_subcommand(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("unknown", ctx)
        assert result.status == "error"


class TestResetCommand:
    """Test the /reset command."""

    def setup_method(self) -> None:
        self.registry = create_default_registry()
        self.cmd = self.registry.get("reset")
        assert self.cmd is not None

    def test_name_and_description(self) -> None:
        assert self.cmd.name == "reset"
        assert self.cmd.description

    def test_reset_clears_and_rebuilds(self) -> None:
        session = FakeSession()
        ctx = make_context(session=session)
        result = self.cmd.execute("", ctx)
        assert result.status == "ok"
        assert "Reset" in result.message
        assert result.rebuild_context is True
        assert result.state_patch.get("reset") is True


class TestCommandCandidates:
    """Test the new get_candidates() and resolve() methods."""

    def test_mode_command_get_candidates(self) -> None:
        """Test ModeCommand.get_candidates() returns mode options."""
        cmd = ModeCommand()
        ctx = make_context()
        candidates = cmd.get_candidates("", ctx)

        # Should always include 'chat' as default
        assert len(candidates) >= 1
        chat_candidate = next((c for c in candidates if c.id == "chat"), None)
        assert chat_candidate is not None
        assert chat_candidate.is_default is True

    def test_mode_command_resolve_needs_input(self) -> None:
        """Test ModeCommand.resolve() returns needs_input when no args."""
        cmd = ModeCommand()
        ctx = make_context()
        resolution = cmd.resolve("", ctx)

        assert resolution.status == "needs_input"
        assert len(resolution.candidates) >= 1

    def test_mode_command_resolve_ready(self) -> None:
        """Test ModeCommand.resolve() returns ready for valid mode."""
        cmd = ModeCommand()
        ctx = make_context()
        resolution = cmd.resolve("code", ctx)

        assert resolution.status == "ready"
        assert resolution.normalized_args == "code"

    def test_mode_command_resolve_invalid(self) -> None:
        """Test ModeCommand.resolve() returns invalid for bad mode."""
        cmd = ModeCommand()
        ctx = make_context()
        resolution = cmd.resolve("nonexistent", ctx)

        assert resolution.status == "invalid"
        assert "Invalid mode" in resolution.message

    def test_model_command_get_candidates_providers(self) -> None:
        """Test ModelCommand.get_candidates() returns providers."""
        cmd = ModelCommand()
        ctx = make_context()
        candidates = cmd.get_candidates("", ctx)

        # Should return provider candidates
        assert len(candidates) >= 1
        # All candidates should have "/" appended for continuation
        for c in candidates:
            assert c.value.endswith("/")

    def test_session_command_get_candidates(self) -> None:
        """Test SessionCommand.get_candidates() returns subcommands."""
        cmd = SessionCommand()
        ctx = make_context()
        candidates = cmd.get_candidates("", ctx)

        # Should include info and list subcommands
        ids = [c.id for c in candidates]
        assert "info" in ids
        assert "list" in ids

        # info should be default
        info = next(c for c in candidates if c.id == "info")
        assert info.is_default is True

    def test_session_command_resolve_subcommands(self) -> None:
        """Test SessionCommand.resolve() for subcommands."""
        cmd = SessionCommand()
        ctx = make_context()

        # 'info' should be ready
        resolution = cmd.resolve("info", ctx)
        assert resolution.status == "ready"

        # 'list' should be ready
        resolution = cmd.resolve("list", ctx)
        assert resolution.status == "ready"
