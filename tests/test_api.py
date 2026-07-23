"""
Test convenience API.
"""

import asyncio
import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda import Agent, tool
from quenda.kernel import Message, Model, ModelResponse
from quenda.kernel.types import ImageContent, TextContent
from quenda.runtime.events import ErrorOccurred
from quenda.runtime import RunCompleted, RunStarted


class FakeModel:
    """Fake model for testing."""

    def __init__(self, response: str = "OK") -> None:
        self.response = response

    def invoke(self, messages: list[Message], *, tools: list) -> ModelResponse:
        return ModelResponse(content=self.response, stop_reason="end_turn")


class CapturingVisionModel:
    """Fake vision-capable model that captures the messages it receives."""

    def __init__(self, response: str = "Vision response") -> None:
        self.response = response
        self.last_messages: list[Message] | None = None
        self.spec = SimpleNamespace(vision=True, context_window=None, max_output_tokens=None)

    def invoke(self, messages: list[Message], *, tools: list) -> ModelResponse:
        self.last_messages = messages
        return ModelResponse(content=self.response, stop_reason="end_turn")


class NonVisionModel:
    """Fake non-vision model used to verify early rejection."""

    def __init__(self) -> None:
        self.spec = SimpleNamespace(vision=False, context_window=None, max_output_tokens=None)

    def invoke(self, messages: list[Message], *, tools: list) -> ModelResponse:
        return ModelResponse(content="should not be reached", stop_reason="end_turn")


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

    def test_sync_interrupt_cancels_pending_task_before_next_send(self) -> None:
        """An interrupted task must not resume when the event loop is reused."""
        agent = Agent(name="test")
        session = agent.open_session()
        cancelled = False

        async def pending() -> None:
            nonlocal cancelled
            try:
                await asyncio.Event().wait()
            finally:
                cancelled = True

        loop = session._get_or_create_loop()

        def interrupt_loop() -> None:
            raise KeyboardInterrupt

        loop.call_later(0.01, interrupt_loop)
        with pytest.raises(KeyboardInterrupt):
            session._run_sync(pending())

        assert cancelled is True
        assert not asyncio.all_tasks(loop)

        async def next_send() -> str:
            return "next"

        assert session._run_sync(next_send()) == "next"

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

    def test_run_sync_accepts_image_paths(self, tmp_path: Path) -> None:
        """Test that one-shot run can attach images by file path."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        image_path = tmp_path / "sample.png"
        image_path.write_bytes(png_data)

        model = CapturingVisionModel()
        agent = Agent(name="test", model=model)

        result = agent.run_sync("Describe this image", image_paths=[str(image_path)])

        assert result == "Vision response"
        assert model.last_messages is not None
        assert len(model.last_messages) == 2
        content = model.last_messages[0].content
        assert model.last_messages[0].role == "user"
        assert model.last_messages[1].role == "assistant"
        assert isinstance(content, list)
        assert isinstance(content[0], TextContent)
        assert isinstance(content[1], ImageContent)

    @pytest.mark.asyncio
    async def test_run_rejects_images_for_non_vision_model(self) -> None:
        """Test that image input fails fast on non-vision models."""
        agent = Agent(name="test", model=NonVisionModel())
        events = []

        result = await agent.run(
            [
                TextContent(text="What is in this image?"),
                ImageContent(media_type="image/png", data="AAAA"),
            ],
            on_event=events.append,
        )

        assert result == ""
        assert any(isinstance(event, ErrorOccurred) for event in events)
