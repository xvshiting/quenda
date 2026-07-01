#!/usr/bin/env python3
"""
Interactive Kernel Demo.

Run this script to test the Kernel with a simulated model.

Usage:
    python demo_kernel.py
"""

from quenda.kernel import Kernel, Message, Model, ModelResponse, Tool, ToolCall, ToolResult


class EchoTool:
    """A simple echo tool for demonstration."""

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
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo back",
                },
            },
            "required": ["message"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        message = kwargs.get("message", "")
        print(f"  [Tool] echo executed with: {message}")
        return ToolResult(
            call_id="",
            name="echo",
            content=f"Echo: {message}",
        )


class CalculatorTool:
    """A simple calculator tool."""

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Perform basic arithmetic calculations."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression to evaluate (e.g., '2 + 3 * 4')",
                },
            },
            "required": ["expression"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        expression = kwargs.get("expression", "")
        print(f"  [Tool] calculate executed with: {expression}")
        try:
            # Safe evaluation of simple math expressions
            result = eval(str(expression), {"__builtins__": {}}, {})
            return ToolResult(
                call_id="",
                name="calculate",
                content=f"Result: {result}",
            )
        except Exception as e:
            return ToolResult(
                call_id="",
                name="calculate",
                content=f"Error: {e}",
                is_error=True,
            )


class InteractiveModel:
    """
    A model that prompts for input interactively.

    This simulates what an LLM would do - respond with text or tool calls.
    """

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        # Show conversation history
        print("\n[Model] Current conversation:")
        for msg in messages:
            role = msg.role.upper()
            content = msg.content
            if isinstance(content, str):
                print(f"  {role}: {content[:100]}{'...' if len(content) > 100 else ''}")
            else:
                print(f"  {role}: <{len(content)} tool items>")

        # Show available tools
        print(f"\n[Model] Available tools: {[t.name for t in tools]}")

        # Prompt user for response
        print("\n[Model] Choose response type:")
        print("  1. Text response")
        print("  2. Tool call: echo")
        print("  3. Tool call: calculate")
        print("  4. Stop (end_turn)")

        choice = input("\nChoice [1-4]: ").strip()

        if choice == "1":
            text = input("Enter response text: ")
            return ModelResponse(content=text, stop_reason="end_turn")

        elif choice == "2":
            msg = input("Enter message to echo: ")
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="call_echo", name="echo", arguments={"message": msg})
                ],
                stop_reason="tool_use",
            )

        elif choice == "3":
            expr = input("Enter expression to calculate: ")
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="call_calc", name="calculate", arguments={"expression": expr})
                ],
                stop_reason="tool_use",
            )

        elif choice == "4":
            return ModelResponse(content="[Session ended]", stop_reason="end_turn")

        else:
            return ModelResponse(content="Invalid choice, please try again.", stop_reason="end_turn")


def main() -> None:
    """Run the interactive kernel demo."""
    print("=" * 60)
    print("Kora Kernel Interactive Demo")
    print("=" * 60)

    # Create tools
    tools = [EchoTool(), CalculatorTool()]

    # Create model
    model = InteractiveModel()

    # Create kernel
    kernel = Kernel(model, tools, max_iterations=10)

    # Initial message
    user_input = input("\nEnter your initial message: ")
    messages = [Message(role="user", content=user_input)]

    print("\n" + "-" * 60)
    print("Starting Kernel execution...")
    print("-" * 60)

    # Run kernel and collect steps
    all_steps = []
    for step in kernel.run(messages):
        all_steps.append(step)

        if step.type == "model":
            response = step.content
            assert isinstance(response, ModelResponse)
            print(f"\n[Step: MODEL]")
            if response.content:
                print(f"  Content: {response.content}")
            if response.tool_calls:
                print(f"  Tool calls: {[tc.name for tc in response.tool_calls]}")
            print(f"  Stop reason: {response.stop_reason}")

        elif step.type == "tool":
            result = step.content
            assert isinstance(result, ToolResult)
            print(f"\n[Step: TOOL]")
            print(f"  Tool: {result.name}")
            print(f"  Result: {result.content}")
            if result.is_error:
                print("  (Error)")

    print("\n" + "=" * 60)
    print("Kernel execution completed!")
    print(f"Total steps: {len(all_steps)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
