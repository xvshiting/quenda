"""
Real Model Demo using OpenAI-compatible API.

This connects to a real LLM and runs the Kernel with actual model responses.
"""

import os
from openai import OpenAI

from quenda.kernel import Kernel, Message, Model, ModelResponse, Tool, ToolCall, ToolResult


class EchoTool:
    """A simple echo tool."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the input message. Use this to repeat or confirm text."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo back",
                }
            },
            "required": ["message"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        message = kwargs.get("message", "")
        print(f"\n  🔧 [Tool: echo] Received: {message}")
        return ToolResult(call_id="", name="echo", content=f"Echo: {message}")


class CalculatorTool:
    """A simple calculator tool."""

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Perform basic arithmetic calculations. Supports +, -, *, /, **, etc."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression to evaluate (e.g., '2 + 3 * 4')",
                }
            },
            "required": ["expression"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        expression = kwargs.get("expression", "")
        print(f"\n  🔧 [Tool: calculate] Evaluating: {expression}")
        try:
            # Safe evaluation of simple math expressions
            result = eval(str(expression), {"__builtins__": {}}, {})
            print(f"  🔧 [Tool: calculate] Result: {result}")
            return ToolResult(call_id="", name="calculate", content=str(result))
        except Exception as e:
            return ToolResult(call_id="", name="calculate", content=f"Error: {e}", is_error=True)


class OpenAICompatibleModel:
    """
    Model provider that uses OpenAI-compatible API.

    Converts between Kora's types and OpenAI's format.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        """Invoke the model with messages and tools."""

        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                openai_messages.append({"role": msg.role, "content": msg.content})
            else:
                # Tool calls or results
                items = list(msg.content)
                if items and isinstance(items[0], ToolCall):
                    # Assistant message with tool calls
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": str(tc.arguments).replace("'", '"'),
                            },
                        }
                        for tc in items
                    ]
                    openai_messages.append({"role": "assistant", "tool_calls": tool_calls})
                    for tc in items:
                        # Add tool result placeholder
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "",  # Will be filled in next message
                        })
                elif items and isinstance(items[0], ToolResult):
                    # User message with tool results
                    for tr in items:
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tr.call_id if tr.call_id else "default",
                            "content": tr.content,
                        })

        # Convert tools to OpenAI format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

        print(f"\n🤖 [Model] Calling {self.model}...")

        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        choice = response.choices[0]

        # Convert response back to Kora format
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        # Determine stop reason
        stop_reason = "end_turn"
        if tool_calls:
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"
        elif choice.finish_reason == "stop":
            stop_reason = "end_turn"

        content = choice.message.content

        if tool_calls:
            print(f"🤖 [Model] Requested tool calls: {[tc.name for tc in tool_calls]}")
        elif content:
            print(f"🤖 [Model] Response: {content[:100]}{'...' if len(content) > 100 else ''}")

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )


def main() -> None:
    print("=" * 60)
    print("Kora Kernel - Real Model Demo")
    print("=" * 60)

    # Configuration
    base_url = "https://modelservice.jdcloud.com/coding/openai/v1"
    api_key = "pk-d00e0bab-3e43-4221-bb58-2a84a925058d"
    model_name = "GLM-5"

    # Create model
    model = OpenAICompatibleModel(base_url=base_url, api_key=api_key, model=model_name)

    # Create tools
    tools = [EchoTool(), CalculatorTool()]

    # Create kernel
    kernel = Kernel(model, tools, max_iterations=10)

    # Get user input
    print("\nAvailable tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")

    user_input = input("\n💬 Enter your message (or press Enter for demo): ").strip()
    if not user_input:
        user_input = "请用 echo 工具说你好，然后用 calculate 工具计算 123 * 456"

    print(f"\n💬 [User] {user_input}")
    print("\n" + "-" * 60)
    print("Starting Kernel execution...")
    print("-" * 60)

    # Run kernel
    messages = [Message(role="user", content=user_input)]

    step_count = 0
    for step in kernel.run(messages):
        step_count += 1
        print(f"\n📌 Step {step_count}: {step.type.upper()}")

        if step.type == "tool":
            result = step.content
            assert isinstance(result, ToolResult)
            status = "✅" if not result.is_error else "❌"
            print(f"   {status} Tool '{result.name}' returned: {result.content}")

    print("\n" + "=" * 60)
    print(f"✅ Kernel execution completed! Total steps: {step_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
