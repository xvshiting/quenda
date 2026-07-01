"""
Tests for Host layer storage.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from kora.host import FileStorage, FileStorageConfig, RunState
from kora.runtime import SessionState, Session, AgentConfig
from kora.kernel.types import Message, ToolCall, ToolResult


class TestRunState:
    """Tests for RunState."""

    def test_run_state_creation(self) -> None:
        """Test creating a run state."""
        run = RunState(
            id="run-123",
            session_id="session-456",
            agent_name="test-agent",
            status="completed",
            user_message="Hello",
            final_content="Hi there!",
            step_count=3,
            created_at=datetime.now(),
            completed_at=datetime.now(),
        )

        assert run.id == "run-123"
        assert run.session_id == "session-456"
        assert run.status == "completed"
        assert run.step_count == 3

    def test_run_state_serialization(self) -> None:
        """Test run state serialization."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        completed = datetime(2024, 1, 15, 10, 30, 5)

        run = RunState(
            id="run-123",
            session_id="session-456",
            agent_name="test-agent",
            status="completed",
            user_message="Hello",
            final_content="Hi!",
            step_count=2,
            created_at=created,
            completed_at=completed,
        )

        data = run.to_dict()
        assert data["id"] == "run-123"
        assert data["created_at"] == "2024-01-15T10:30:00"

        # Deserialize
        restored = RunState.from_dict(data)
        assert restored.id == run.id
        assert restored.created_at == created


class TestFileStorage:
    """Tests for FileStorage."""

    @pytest.fixture
    def temp_storage(self) -> FileStorage:
        """Create a temporary file storage."""
        with TemporaryDirectory() as tmpdir:
            config = FileStorageConfig(base_dir=Path(tmpdir))
            yield FileStorage(config)

    def test_save_and_load_session(self, temp_storage: FileStorage) -> None:
        """Test saving and loading a session."""
        state = SessionState.create("test-agent")
        state.add_user_message("Hello")

        # Save
        temp_storage.save_session(state)

        # Load
        loaded = temp_storage.load_session(state.id)
        assert loaded is not None
        assert loaded.id == state.id
        assert loaded.agent_name == "test-agent"
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Hello"

    def test_load_nonexistent_session(self, temp_storage: FileStorage) -> None:
        """Test loading a session that doesn't exist."""
        loaded = temp_storage.load_session("nonexistent")
        assert loaded is None

    def test_list_sessions(self, temp_storage: FileStorage) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        state1 = SessionState.create("agent-1")
        state2 = SessionState.create("agent-2")
        state3 = SessionState.create("agent-1")

        temp_storage.save_session(state1)
        temp_storage.save_session(state2)
        temp_storage.save_session(state3)

        # List all
        all_sessions = temp_storage.list_sessions()
        assert len(all_sessions) == 3

        # Filter by agent
        agent1_sessions = temp_storage.list_sessions(agent_name="agent-1")
        assert len(agent1_sessions) == 2

    def test_delete_session(self, temp_storage: FileStorage) -> None:
        """Test deleting a session."""
        state = SessionState.create("test-agent")
        temp_storage.save_session(state)

        # Delete
        result = temp_storage.delete_session(state.id)
        assert result is True

        # Verify deleted
        loaded = temp_storage.load_session(state.id)
        assert loaded is None

        # Delete nonexistent
        result = temp_storage.delete_session("nonexistent")
        assert result is False

    def test_save_and_load_run(self, temp_storage: FileStorage) -> None:
        """Test saving and loading a run."""
        run = RunState(
            id="run-123",
            session_id="session-456",
            agent_name="test-agent",
            status="completed",
            user_message="Hello",
            final_content="Hi!",
            step_count=2,
            created_at=datetime.now(),
            completed_at=datetime.now(),
        )

        # Save
        temp_storage.save_run(run)

        # Load
        loaded = temp_storage.load_run(run.id)
        assert loaded is not None
        assert loaded.id == run.id
        assert loaded.session_id == "session-456"
        assert loaded.step_count == 2

    def test_list_runs(self, temp_storage: FileStorage) -> None:
        """Test listing runs for a session."""
        # Create runs for different sessions
        run1 = RunState(
            id="run-1",
            session_id="session-A",
            agent_name="test-agent",
            status="completed",
            user_message="Msg 1",
            final_content=None,
            step_count=1,
            created_at=datetime.now(),
        )
        run2 = RunState(
            id="run-2",
            session_id="session-A",
            agent_name="test-agent",
            status="completed",
            user_message="Msg 2",
            final_content=None,
            step_count=2,
            created_at=datetime.now(),
        )
        run3 = RunState(
            id="run-3",
            session_id="session-B",
            agent_name="test-agent",
            status="completed",
            user_message="Msg 3",
            final_content=None,
            step_count=1,
            created_at=datetime.now(),
        )

        temp_storage.save_run(run1)
        temp_storage.save_run(run2)
        temp_storage.save_run(run3)

        # List runs for session-A
        runs = temp_storage.list_runs("session-A")
        assert len(runs) == 2

        # List runs for session-B
        runs = temp_storage.list_runs("session-B")
        assert len(runs) == 1


class TestSessionWithStorage:
    """Tests for Session with storage."""

    @pytest.fixture
    def temp_storage(self) -> FileStorage:
        """Create a temporary file storage."""
        with TemporaryDirectory() as tmpdir:
            config = FileStorageConfig(base_dir=Path(tmpdir))
            yield FileStorage(config)

    def test_session_save(self, temp_storage: FileStorage) -> None:
        """Test session save method."""
        state = SessionState.create("test-agent")
        state.add_user_message("Hello")

        agent = AgentConfig(name="test-agent")
        session = Session(state=state, agent=agent, storage=temp_storage)

        # Save
        session.save()

        # Verify saved
        loaded_state = temp_storage.load_session(state.id)
        assert loaded_state is not None
        assert len(loaded_state.messages) == 1

    def test_session_load(self, temp_storage: FileStorage) -> None:
        """Test session load class method."""
        # Create and save a session
        state = SessionState.create("test-agent")
        state.add_user_message("Hello")
        temp_storage.save_session(state)

        # Load
        agent = AgentConfig(name="test-agent")
        session = Session.load(state.id, temp_storage, agent)
        assert session is not None
        assert session.id == state.id
        assert len(session.messages) == 1

    def test_session_load_nonexistent(self, temp_storage: FileStorage) -> None:
        """Test loading a nonexistent session."""
        agent = AgentConfig(name="test-agent")
        session = Session.load("nonexistent", temp_storage, agent)
        assert session is None


class TestSessionWithToolCalls:
    """Tests for session persistence with tool calls."""

    @pytest.fixture
    def temp_storage(self) -> FileStorage:
        """Create a temporary file storage."""
        with TemporaryDirectory() as tmpdir:
            config = FileStorageConfig(base_dir=Path(tmpdir))
            yield FileStorage(config)

    def test_save_session_with_tool_calls(self, temp_storage: FileStorage) -> None:
        """Test saving a session with tool calls."""
        state = SessionState.create("test-agent")
        state.add_user_message("What's the weather?")

        # Add assistant message with tool calls
        tool_calls = [
            ToolCall(id="call-1", name="get_weather", arguments={"city": "Beijing"}),
        ]
        state.messages.append(Message(role="assistant", content=tool_calls))

        # Add tool results
        tool_results = [
            ToolResult(call_id="call-1", name="get_weather", content="Sunny, 25C"),
        ]
        state.messages.append(Message(role="user", content=tool_results))

        # Save and load
        temp_storage.save_session(state)
        loaded = temp_storage.load_session(state.id)

        assert loaded is not None
        assert len(loaded.messages) == 3

        # Check tool calls preserved
        assistant_msg = loaded.messages[1]
        assert isinstance(assistant_msg.content, list)
        tc = assistant_msg.content[0]
        assert isinstance(tc, ToolCall)
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Beijing"}

        # Check tool results preserved
        user_msg = loaded.messages[2]
        assert isinstance(user_msg.content, list)
        tr = user_msg.content[0]
        assert isinstance(tr, ToolResult)
        assert tr.content == "Sunny, 25C"


class TestFileStorageEdgeCases:
    """Edge case tests for FileStorage."""

    def test_storage_with_custom_base_dir(self) -> None:
        """Test storage with custom base directory."""
        with TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom_kora"
            config = FileStorageConfig(base_dir=custom_dir)
            storage = FileStorage(config)

            # Verify directories created
            assert custom_dir.exists()
            assert (custom_dir / "sessions").exists()
            assert (custom_dir / "runs").exists()

    def test_save_session_overwrites_existing(self) -> None:
        """Test that saving a session overwrites existing state."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            state = SessionState.create("test-agent")
            state.add_user_message("First message")
            storage.save_session(state)

            # Modify and save again
            state.add_user_message("Second message")
            storage.save_session(state)

            # Load and verify
            loaded = storage.load_session(state.id)
            assert loaded is not None
            assert len(loaded.messages) == 2
            assert loaded.messages[1].content == "Second message"

    def test_save_run_overwrites_existing(self) -> None:
        """Test that saving a run overwrites existing state."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            run = RunState(
                id="run-123",
                session_id="session-456",
                agent_name="test-agent",
                status="running",
                user_message="Hello",
                final_content=None,
                step_count=1,
                created_at=datetime.now(),
            )
            storage.save_run(run)

            # Update and save again
            run = RunState(
                id="run-123",
                session_id="session-456",
                agent_name="test-agent",
                status="completed",
                user_message="Hello",
                final_content="Hi!",
                step_count=3,
                created_at=run.created_at,
                completed_at=datetime.now(),
            )
            storage.save_run(run)

            # Load and verify
            loaded = storage.load_run("run-123")
            assert loaded is not None
            assert loaded.status == "completed"
            assert loaded.step_count == 3

    def test_list_sessions_empty_storage(self) -> None:
        """Test listing sessions when storage is empty."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            sessions = storage.list_sessions()
            assert sessions == []

    def test_list_runs_empty_storage(self) -> None:
        """Test listing runs when storage is empty."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            runs = storage.list_runs("nonexistent-session")
            assert runs == []

    def test_list_runs_for_nonexistent_session(self) -> None:
        """Test listing runs for a session that has no runs."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            # Create a run for a different session
            run = RunState(
                id="run-1",
                session_id="session-A",
                agent_name="test-agent",
                status="completed",
                user_message="Hello",
                final_content=None,
                step_count=1,
                created_at=datetime.now(),
            )
            storage.save_run(run)

            # List runs for different session
            runs = storage.list_runs("session-B")
            assert runs == []

    def test_save_session_with_metadata(self) -> None:
        """Test saving session with custom metadata."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            state = SessionState.create("test-agent")
            state.metadata["user_id"] = "user-123"  # Add metadata after creation
            state.add_user_message("Hello")
            storage.save_session(state)

            loaded = storage.load_session(state.id)
            assert loaded is not None
            assert loaded.metadata == {"user_id": "user-123"}

    def test_save_run_with_error_status(self) -> None:
        """Test saving run with failed status."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            run = RunState(
                id="run-failed",
                session_id="session-456",
                agent_name="test-agent",
                status="failed",
                user_message="Do something",
                final_content=None,
                step_count=0,
                created_at=datetime.now(),
            )
            storage.save_run(run)

            loaded = storage.load_run("run-failed")
            assert loaded is not None
            assert loaded.status == "failed"

    def test_tool_result_with_error(self) -> None:
        """Test saving session with tool result that has an error."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            state = SessionState.create("test-agent")
            state.add_user_message("Test")

            tool_results = [
                ToolResult(
                    call_id="call-1",
                    name="fail_tool",
                    content="Error: something went wrong",
                    is_error=True,
                ),
            ]
            state.messages.append(Message(role="user", content=tool_results))

            storage.save_session(state)
            loaded = storage.load_session(state.id)

            assert loaded is not None
            tr = loaded.messages[1].content[0]  # type: ignore
            assert isinstance(tr, ToolResult)
            assert tr.is_error is True
            assert tr.content == "Error: something went wrong"

    def test_multiple_tool_calls_in_one_message(self) -> None:
        """Test saving session with multiple tool calls in one message."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            state = SessionState.create("test-agent")
            state.add_user_message("Get weather for multiple cities")

            tool_calls = [
                ToolCall(id="call-1", name="get_weather", arguments={"city": "Beijing"}),
                ToolCall(id="call-2", name="get_weather", arguments={"city": "Shanghai"}),
                ToolCall(id="call-3", name="get_weather", arguments={"city": "Guangzhou"}),
            ]
            state.messages.append(Message(role="assistant", content=tool_calls))

            storage.save_session(state)
            loaded = storage.load_session(state.id)

            assert loaded is not None
            assistant_msg = loaded.messages[1]
            assert isinstance(assistant_msg.content, list)
            assert len(assistant_msg.content) == 3
            for i, tc in enumerate(assistant_msg.content):
                assert isinstance(tc, ToolCall)
                assert tc.id == f"call-{i + 1}"

    def test_delete_run_not_implemented(self) -> None:
        """Test that run deletion is not implemented in FileStorage."""
        with TemporaryDirectory() as tmpdir:
            storage = FileStorage(FileStorageConfig(base_dir=Path(tmpdir)))

            # FileStorage doesn't have delete_run method
            # This test documents the current behavior
            assert not hasattr(storage, "delete_run")
