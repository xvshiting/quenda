"""Test kernel types."""

import pytest

from quenda.kernel.types import Message, ModelResponse, ToolCall, ToolResult


def test_tool_call_creation() -> None:
    """Test creating a tool call."""
    call = ToolCall(
        id="call_123",
        name="read_file",
        arguments={"path": "/tmp/test.txt"},
    )
    assert call.id == "call_123"
    assert call.name == "read_file"
    assert call.arguments["path"] == "/tmp/test.txt"


def test_tool_result_creation() -> None:
    """Test creating a tool result."""
    result = ToolResult(
        call_id="call_123",
        name="read_file",
        content="file contents here",
    )
    assert result.call_id == "call_123"
    assert not result.is_error


def test_tool_result_error() -> None:
    """Test creating an error tool result."""
    result = ToolResult(
        call_id="call_123",
        name="read_file",
        content="File not found",
        is_error=True,
    )
    assert result.is_error


def test_message_with_string_content() -> None:
    """Test creating a message with string content."""
    msg = Message(role="user", content="Hello, world!")
    assert msg.role == "user"
    assert msg.content == "Hello, world!"


def test_message_with_tool_content() -> None:
    """Test creating a message with tool calls."""
    calls = [ToolCall(id="1", name="test", arguments={})]
    msg = Message(role="assistant", content=calls)
    assert msg.role == "assistant"
    assert len(msg.content) == 1  # type: ignore[arg-type]


def test_model_response_defaults() -> None:
    """Test model response default values."""
    resp = ModelResponse()
    assert resp.content is None
    assert resp.tool_calls == []
    assert resp.stop_reason == "end_turn"


def test_model_response_with_tool_calls() -> None:
    """Test model response with tool calls."""
    calls = [
        ToolCall(id="1", name="read_file", arguments={"path": "/tmp/a.txt"}),
        ToolCall(id="2", name="write_file", arguments={"path": "/tmp/b.txt", "content": "hi"}),
    ]
    resp = ModelResponse(tool_calls=calls, stop_reason="tool_use")
    assert len(resp.tool_calls) == 2
    assert resp.stop_reason == "tool_use"
