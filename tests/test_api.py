"""
Test convenience API.
"""

import pytest

from kora import Agent, tool
from kora.kernel import Message, Model, ModelResponse
from kora.runtime import RunCompleted, RunStarted


class FakeModel:
    """Fake model for testing."""

    def __init__(self, response: str = "OK") -> None:
        self.response = response

    def invoke(self, messages: list[Message], *, tools: list) -> ModelResponse:
        return ModelResponse(content=self.response, stop_reason="end_turn")


class TestConvenienceAPI:
    """Tests for the convenience API."""

    def test_agent_creation(self) -> None:
        """Test creating an agent."""
        agent = Agent(name="test")
        assert agent.name == "test"

    def test_agent_with_tools(self) -> None:
        """Test agent with tools."""

        @tool
        def echo(msg: str) -> str:
            """Echo."""
            return msg

        agent = Agent(name="test", tools=[echo])
        assert len(agent.config.tools) == 1

    def test_open_session(self) -> None:
        """Test opening a session."""
        agent = Agent(name="test")
        session = agent.open_session()
        assert session.id
        assert len(session) == 0

    def test_run_sync(self) -> None:
        """Test synchronous run."""
        model = FakeModel(response="Hello!")

        @tool
        def dummy() -> str:
            return "ok"

        agent = Agent(name="test", tools=[dummy], model=model)
        session = agent.open_session()

        result = session.send_sync("Hi")
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_send_async(self) -> None:
        """Test async send."""
        model = FakeModel(response="Async response")

        agent = Agent(name="test", model=model)
        session = agent.open_session()

        result = await session.send("Hi")
        assert result == "Async response"

    def test_session_history(self) -> None:
        """Test that session tracks history."""
        model = FakeModel()

        agent = Agent(name="test", model=model)
        session = agent.open_session()

        session.send_sync("Hello")
        session.send_sync("World")

        # Should have 2 user messages
        assert len(session) >= 2

    def test_set_model(self) -> None:
        """Test setting model after creation."""
        agent = Agent(name="test")
        session = agent.open_session()
        session.set_model(FakeModel())

        result = session.send_sync("Hi")
        assert result == "OK"

    def test_no_model_error(self) -> None:
        """Test that running without model raises error."""
        agent = Agent(name="test")
        session = agent.open_session()

        with pytest.raises(ValueError, match="No model"):
            session.send_sync("Hi")

    def test_one_shot_run(self) -> None:
        """Test one-shot run without session."""
        model = FakeModel(response="One-shot!")

        agent = Agent(name="test", model=model)
        result = agent.run_sync("Hi")
        assert result == "One-shot!"

    @pytest.mark.asyncio
    async def test_one_shot_run_async(self) -> None:
        """Test async one-shot run."""
        model = FakeModel(response="Async one-shot!")

        agent = Agent(name="test", model=model)
        result = await agent.run("Hi")
        assert result == "Async one-shot!"

    def test_tool_decorator(self) -> None:
        """Test @tool decorator."""

        @tool
        def add(a: int, b: int) -> str:
            """Add two numbers."""
            return str(a + b)

        assert add.name == "add"
        assert "a" in add.parameters["properties"]
        assert "b" in add.parameters["properties"]

    def test_tool_execution(self) -> None:
        """Test tool execution."""

        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        result = greet.execute(name="World")
        assert "Hello" in result.content

    def test_send_collecting_sync_returns_events(self) -> None:
        """Test sending while collecting runtime events."""
        model = FakeModel(response="Collected")
        agent = Agent(name="test", model=model)
        session = agent.open_session()

        result, events = session.send_collecting_sync("Hi")

        assert result == "Collected"
        assert any(isinstance(event, RunStarted) for event in events)
        assert any(isinstance(event, RunCompleted) for event in events)

    def test_session_checkpoint_and_rollback(self) -> None:
        """Test turn checkpoint helpers for hidden follow-up phases."""
        model = FakeModel(response="Hello!")
        agent = Agent(name="test", model=model)
        session = agent.open_session()

        session.send_sync("Visible")
        checkpoint = session.checkpoint()
        session.send_sync("Hidden")

        assert len(session.messages) > checkpoint

        session.rollback_to(checkpoint)

        assert len(session.messages) == checkpoint
