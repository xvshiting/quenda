"""
Tests for Kernel core loop.

Uses fake model and fake tools for deterministic testing.
"""

import pytest

from kora.kernel import Kernel, KernelStep, Message, Model, ModelResponse, Tool, ToolCall, ToolResult


class FakeTool:
    """A fake tool for testing."""

    def __init__(self, name: str, result: str = "ok") -> None:
        self._name = name
        self._result = result
        self.call_count = 0
        self.last_args: dict | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"A fake tool named {self._name}"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
        }

    def execute(self, **kwargs: object) -> ToolResult:
        self.call_count += 1
        self.last_args = kwargs
        return ToolResult(
            call_id="",
            name=self._name,
            content=self._result,
        )


class FakeModel:
    """A fake model for testing with scripted responses."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.last_messages: list[Message] | None = None
        self.last_tools: list[Tool] | None = None

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        self.call_count += 1
        self.last_messages = messages
        self.last_tools = tools
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(content="No more responses", stop_reason="end_turn")


class TestKernelBasics:
    """Basic kernel tests."""

    def test_kernel_simple_response(self) -> None:
        """Kernel handles a simple text response."""
        model = FakeModel([
            ModelResponse(content="Hello, world!", stop_reason="end_turn"),
        ])
        tool = FakeTool("test_tool")

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Hi")]
        steps = list(kernel.run(messages))

        assert len(steps) == 1
        assert steps[0].type == "model"
        assert isinstance(steps[0].content, ModelResponse)
        assert steps[0].content.content == "Hello, world!"

    def test_kernel_tool_call_and_continue(self) -> None:
        """Kernel executes tool and continues the loop."""
        tool = FakeTool("echo", result="echo result")
        model = FakeModel([
            # First response: call the tool
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="echo", arguments={"input": "hello"})],
                stop_reason="tool_use",
            ),
            # Second response: final answer
            ModelResponse(content="I got: echo result", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Say hello")]
        steps = list(kernel.run(messages))

        # Should have: model response (tool call), tool result, model response (final)
        assert len(steps) == 3
        assert steps[0].type == "model"
        assert steps[1].type == "tool"
        assert steps[2].type == "model"

        # Tool should have been called
        assert tool.call_count == 1
        assert tool.last_args == {"input": "hello"}

    def test_kernel_multiple_tool_calls(self) -> None:
        """Kernel handles multiple tool calls in one response."""
        tool1 = FakeTool("tool1", result="result1")
        tool2 = FakeTool("tool2", result="result2")

        model = FakeModel([
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="tool1", arguments={}),
                    ToolCall(id="call_2", name="tool2", arguments={}),
                ],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool1, tool2])
        messages = [Message(role="user", content="Run both")]
        steps = list(kernel.run(messages))

        # Should have: model, tool, tool, model
        assert len(steps) == 4
        assert tool1.call_count == 1
        assert tool2.call_count == 1

    def test_kernel_tool_not_found(self) -> None:
        """Kernel handles missing tool gracefully."""
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="nonexistent", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="OK", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [])  # No tools registered
        messages = [Message(role="user", content="Test")]
        steps = list(kernel.run(messages))

        # Tool result should be an error
        assert steps[1].type == "tool"
        tool_result = steps[1].content
        assert isinstance(tool_result, ToolResult)
        assert tool_result.is_error
        assert "not found" in tool_result.content.lower()

    def test_kernel_tool_exception(self) -> None:
        """Kernel handles tool exceptions gracefully."""
        class FailingTool:
            @property
            def name(self) -> str:
                return "fail"

            @property
            def description(self) -> str:
                return "A failing tool"

            @property
            def parameters(self) -> dict:
                return {}

            def execute(self, **kwargs: object) -> ToolResult:
                raise RuntimeError("Tool failed!")

        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="fail", arguments={})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="OK", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [FailingTool()])
        messages = [Message(role="user", content="Test")]
        steps = list(kernel.run(messages))

        tool_result = steps[1].content
        assert isinstance(tool_result, ToolResult)
        assert tool_result.is_error
        assert "failed" in tool_result.content.lower()

    def test_kernel_max_iterations(self) -> None:
        """Kernel respects max_iterations limit."""
        model = FakeModel([
            ModelResponse(content="...", stop_reason="tool_use"),
        ] * 10)  # More responses than max_iterations

        kernel = Kernel(model, [], max_iterations=3)
        messages = [Message(role="user", content="Test")]
        steps = list(kernel.run(messages))

        # Should stop after max_iterations
        assert len(steps) == 3
        assert model.call_count == 3

    def test_kernel_run_to_completion(self) -> None:
        """run_to_completion returns all steps as a list."""
        model = FakeModel([
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [])
        messages = [Message(role="user", content="Test")]
        steps = kernel.run_to_completion(messages)

        assert isinstance(steps, list)
        assert len(steps) == 1

    def test_kernel_passes_tools_to_model(self) -> None:
        """Kernel passes tools to the model."""
        tool = FakeTool("test")
        model = FakeModel([
            ModelResponse(content="OK", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Test")]
        list(kernel.run(messages))

        assert model.last_tools == [tool]

    def test_kernel_updates_messages(self) -> None:
        """Kernel adds tool calls and results to messages."""
        tool = FakeTool("echo", result="echoed")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"input": "hi"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Test")]
        list(kernel.run(messages))

        # Model should have received updated messages
        second_call_messages = model.last_messages
        assert second_call_messages is not None
        # After the loop completes, messages contains:
        # user, assistant (tool calls), user (results), assistant (final response)
        assert len(second_call_messages) == 4


class TestKernelStep:
    """Tests for KernelStep."""

    def test_kernel_step_model(self) -> None:
        """KernelStep for model response."""
        response = ModelResponse(content="Hello")
        step = KernelStep(type="model", content=response)

        assert step.type == "model"
        assert step.content == response

    def test_kernel_step_tool(self) -> None:
        """KernelStep for tool result."""
        result = ToolResult(call_id="1", name="test", content="ok")
        step = KernelStep(type="tool", content=result)

        assert step.type == "tool"
        assert step.content == result


class TestKernelPrimitives:
    """Tests for Kernel primitive methods (invoke_model, execute_tool)."""

    def test_invoke_model_returns_response(self) -> None:
        """invoke_model returns ModelResponse without modifying messages."""
        model = FakeModel([
            ModelResponse(content="Hello!", stop_reason="end_turn"),
        ])
        tool = FakeTool("test")

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Hi")]

        response = kernel.invoke_model(messages)

        assert isinstance(response, ModelResponse)
        assert response.content == "Hello!"
        # Messages should NOT be modified
        assert len(messages) == 1
        # Model should have been called
        assert model.call_count == 1

    def test_invoke_model_with_custom_tools(self) -> None:
        """invoke_model can use custom tools instead of registered ones."""
        tool1 = FakeTool("tool1")
        tool2 = FakeTool("tool2")
        model = FakeModel([
            ModelResponse(content="OK", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool1])
        messages = [Message(role="user", content="Test")]

        response = kernel.invoke_model(messages, tools=[tool2])

        # Model should receive custom tools, not registered ones
        assert model.last_tools == [tool2]

    def test_invoke_model_does_not_check_stop_reason(self) -> None:
        """invoke_model returns response even with tool_use stop_reason."""
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="test", arguments={})],
                stop_reason="tool_use",
            ),
        ])
        tool = FakeTool("test")

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Test")]

        response = kernel.invoke_model(messages)

        # Should return the response as-is
        assert response.stop_reason == "tool_use"
        assert len(response.tool_calls) == 1

    def test_execute_tool_returns_result(self) -> None:
        """execute_tool executes tool and returns result."""
        tool = FakeTool("echo", result="echoed")
        model = FakeModel([])

        kernel = Kernel(model, [tool])
        call = ToolCall(id="call_1", name="echo", arguments={"input": "hello"})

        result = kernel.execute_tool(call)

        assert isinstance(result, ToolResult)
        assert result.name == "echo"
        assert result.content == "echoed"
        assert not result.is_error
        assert tool.call_count == 1
        assert tool.last_args == {"input": "hello"}

    def test_execute_tool_handles_missing_tool(self) -> None:
        """execute_tool returns error result for missing tool."""
        model = FakeModel([])

        kernel = Kernel(model, [])  # No tools registered
        call = ToolCall(id="call_1", name="nonexistent", arguments={})

        result = kernel.execute_tool(call)

        assert result.is_error
        assert "not found" in result.content.lower()
        assert result.name == "nonexistent"

    def test_execute_tool_handles_exception(self) -> None:
        """execute_tool returns error result for tool exceptions."""
        class FailingTool:
            @property
            def name(self) -> str:
                return "fail"

            @property
            def description(self) -> str:
                return "A failing tool"

            @property
            def parameters(self) -> dict:
                return {}

            def execute(self, **kwargs: object) -> ToolResult:
                raise RuntimeError("Tool failed!")

        model = FakeModel([])
        kernel = Kernel(model, [FailingTool()])
        call = ToolCall(id="call_1", name="fail", arguments={})

        result = kernel.execute_tool(call)

        assert result.is_error
        assert "failed" in result.content.lower()

    def test_execute_tool_filters_reserved_args(self) -> None:
        """execute_tool filters out arguments starting with underscore."""
        tool = FakeTool("test")
        model = FakeModel([])

        kernel = Kernel(model, [tool])
        call = ToolCall(
            id="call_1",
            name="test",
            arguments={"input": "hello", "_internal": "filtered"},
        )

        result = kernel.execute_tool(call)

        # Tool should not receive _internal argument
        assert tool.last_args == {"input": "hello"}

    def test_execute_tool_includes_timing(self) -> None:
        """execute_tool records execution duration."""
        tool = FakeTool("test")
        model = FakeModel([])

        kernel = Kernel(model, [tool])
        call = ToolCall(id="call_1", name="test", arguments={})

        result = kernel.execute_tool(call)

        assert result.duration_ms >= 0

    def test_primitives_do_not_modify_messages(self) -> None:
        """Primitives don't auto-append to messages like run() does."""
        tool = FakeTool("echo", result="echoed")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={})],
                stop_reason="tool_use",
            ),
        ])

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Test")]

        # invoke_model should not modify messages
        response = kernel.invoke_model(messages)
        assert len(messages) == 1

        # execute_tool should not modify messages
        if response.tool_calls:
            result = kernel.execute_tool(response.tool_calls[0])
            assert len(messages) == 1  # Still not modified

    def test_run_still_works_after_adding_primitives(self) -> None:
        """Existing run() behavior is preserved."""
        tool = FakeTool("echo", result="echoed")
        model = FakeModel([
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"input": "hi"})],
                stop_reason="tool_use",
            ),
            ModelResponse(content="Done", stop_reason="end_turn"),
        ])

        kernel = Kernel(model, [tool])
        messages = [Message(role="user", content="Test")]
        steps = list(kernel.run(messages))

        # Should still work as before
        assert len(steps) == 3
        assert steps[0].type == "model"
        assert steps[1].type == "tool"
        assert steps[2].type == "model"
