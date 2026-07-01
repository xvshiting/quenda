#!/usr/bin/env python3
"""
Automated Kernel Demo - No user interaction required.

This demonstrates the Kernel running with a scripted model.
"""

from kora.kernel import Kernel, Message, Model, ModelResponse, Tool, ToolCall, ToolResult


class EchoTool:
    """A simple echo tool."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the input message."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        message = kwargs.get("message", "")
        return ToolResult(call_id="", name="echo", content=f"Echo: {message}")


class CalculatorTool:
    """A simple calculator tool."""

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Perform basic arithmetic."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        expression = kwargs.get("expression", "")
        try:
            result = eval(str(expression), {"__builtins__": {}}, {})
            return ToolResult(call_id="", name="calculate", content=f"Result: {result}")
        except Exception as e:
            return ToolResult(call_id="", name="calculate", content=f"Error: {e}", is_error=True)


class ScriptedModel:
    """A model with pre-scripted responses."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(content="No more responses", stop_reason="end_turn")


def main() -> None:
    print("=" * 60)
    print("Kora Kernel Automated Demo")
    print("=" * 60)

    # Create tools
    tools = [EchoTool(), CalculatorTool()]

    # Script the model's behavior:
    # 1. Call echo with "Hello"
    # 2. Call calculate with "2 + 3 * 4"
    # 3. Give final response
    model = ScriptedModel([
        ModelResponse(
            tool_calls=[ToolCall(id="c1", name="echo", arguments={"message": "Hello Kora!"})],
            stop_reason="tool_use",
        ),
        ModelResponse(
            tool_calls=[ToolCall(id="c2", name="calculate", arguments={"expression": "2 + 3 * 4"})],
            stop_reason="tool_use",
        ),
        ModelResponse(
            content="I echoed 'Hello Kora!' and calculated 2 + 3 * 4 = 14. All done!",
            stop_reason="end_turn",
        ),
    ])

    # Create kernel
    kernel = Kernel(model, tools, max_iterations=10)

    # Initial message
    messages = [Message(role="user", content="Please echo 'Hello Kora!' and calculate 2 + 3 * 4")]

    print("\n[User] Please echo 'Hello Kora!' and calculate 2 + 3 * 4")
    print("\n" + "-" * 60)
    print("Running Kernel...")
    print("-" * 60)

    # Run and display steps
    for i, step in enumerate(kernel.run(messages), 1):
        print(f"\n--- Step {i}: {step.type.upper()} ---")

        if step.type == "model":
            response = step.content
            assert isinstance(response, ModelResponse)
            if response.content:
                print(f"Model says: {response.content}")
            if response.tool_calls:
                for tc in response.tool_calls:
                    print(f"Model wants to call: {tc.name}({tc.arguments})")
            print(f"Stop reason: {response.stop_reason}")

        elif step.type == "tool":
            result = step.content
            assert isinstance(result, ToolResult)
            status = "❌ ERROR" if result.is_error else "✅ OK"
            print(f"Tool {result.name} returned: {result.content} {status}")

    print("\n" + "=" * 60)
    print("✅ Kernel execution completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
