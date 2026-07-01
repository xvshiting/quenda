"""Test that Kora package can be imported."""

import quenda


def test_version() -> None:
    """Test that version is defined."""
    assert quenda.__version__ == "0.1.0"


def test_kernel_types_import() -> None:
    """Test that kernel types can be imported."""
    from quenda.kernel import Message, ModelResponse, ToolCall, ToolResult

    call = ToolCall(id="1", name="test", arguments={})
    assert call.id == "1"

    result = ToolResult(call_id="1", name="test", content="ok")
    assert result.content == "ok"

    msg = Message(role="user", content="hello")
    assert msg.role == "user"

    resp = ModelResponse(content="hi")
    assert resp.content == "hi"
