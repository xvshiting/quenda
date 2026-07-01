#!/usr/bin/env python3
r"""
Observability Demo - Show all events in real-time.

This demo demonstrates Kora's observability features:
1. Event streaming during Run execution
2. Multiple event handlers
3. Event-based logging and metrics
"""

import asyncio
import json
import time
from dataclasses import asdict
from datetime import datetime
from openai import OpenAI

from kora.kernel import Message, Model, ModelResponse, Tool, ToolCall, ToolResult
from kora.runtime import (
    AgentConfig,
    AnyEvent,
    ErrorOccurred,
    ModelResponded,
    Run,
    RunCompleted,
    RunStarted,
    Session,
    ToolExecuted,
)


# === Tools ===

class EchoTool:
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back a message."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        return ToolResult(call_id="", name="echo", content=f"Echo: {kwargs.get('message', '')}")


class CalculatorTool:
    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Evaluate a math expression."

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        expr = kwargs.get("expression", "")
        try:
            result = eval(str(expr), {"__builtins__": {}}, {})
            return ToolResult(call_id="", name="calculate", content=str(result))
        except Exception as e:
            return ToolResult(call_id="", name="calculate", content=str(e), is_error=True)


# === Model ===

class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def invoke(self, messages: list[Message], *, tools: list[Tool]) -> ModelResponse:
        openai_messages = []
        for msg in messages:
            if isinstance(msg.content, str):
                openai_messages.append({"role": msg.role, "content": msg.content})
            else:
                items = list(msg.content)
                if items and isinstance(items[0], ToolCall):
                    tool_calls = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                        for tc in items
                    ]
                    openai_messages.append({"role": "assistant", "tool_calls": tool_calls})
                    for tc in items:
                        openai_messages.append({"role": "tool", "tool_call_id": tc.id, "content": ""})
                elif items and isinstance(items[0], ToolResult):
                    for tr in items:
                        openai_messages.append({"role": "tool", "tool_call_id": tr.call_id or "default", "content": tr.content})

        openai_tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return ModelResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


# === Event Handlers (Observability) ===

class EventLogger:
    """Log all events to console with timestamps."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.events: list[AnyEvent] = []

    def __call__(self, event: AnyEvent) -> None:
        self.events.append(event)

        if not self.verbose:
            return

        timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
        event_type = event.type

        if isinstance(event, RunStarted):
            print(f"  [{timestamp}] 🚀 RunStarted: agent={event.agent_name}")
        elif isinstance(event, ModelResponded):
            if event.tool_calls:
                print(f"  [{timestamp}] 🤖 ModelResponded: tools={event.tool_calls}")
            else:
                preview = (event.content or "")[:50]
                print(f"  [{timestamp}] 🤖 ModelResponded: {preview}...")
        elif isinstance(event, ToolExecuted):
            status = "❌" if event.is_error else "✅"
            print(f"  [{timestamp}] 🔧 ToolExecuted: {event.tool_name} {status}")
        elif isinstance(event, RunCompleted):
            print(f"  [{timestamp}] ✅ RunCompleted: steps={event.total_steps}")
        elif isinstance(event, ErrorOccurred):
            print(f"  [{timestamp}] ❌ ErrorOccurred: {event.error_message}")


class MetricsCollector:
    """Collect metrics from events."""

    def __init__(self) -> None:
        self.runs = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.model_calls = 0
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

    def __call__(self, event: AnyEvent) -> None:
        if isinstance(event, RunStarted):
            self.runs += 1
            self.start_time = event.timestamp
        elif isinstance(event, ModelResponded):
            self.model_calls += 1
        elif isinstance(event, ToolExecuted):
            self.tool_calls += 1
            if event.is_error:
                self.tool_errors += 1
        elif isinstance(event, RunCompleted):
            self.end_time = event.timestamp

    def report(self) -> dict:
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "runs": self.runs,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "duration_seconds": duration,
        }


class EventRecorder:
    """Record events for replay/debugging."""

    def __init__(self) -> None:
        self.recordings: list[dict] = []

    def __call__(self, event: AnyEvent) -> None:
        self.recordings.append({
            "type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "run_id": event.run_id,
            **{k: v for k, v in asdict(event).items() if k not in ("type", "timestamp", "run_id")},
        })

    def export(self) -> str:
        return json.dumps(self.recordings, indent=2, ensure_ascii=False)


# === Main Demo ===

async def main() -> None:
    print("=" * 60)
    print("Kora 可观测性 Demo")
    print("=" * 60)

    # Setup
    agent = AgentConfig(
        name="assistant",
        system_prompt="你是一个有帮助的助手。",
        tools=[EchoTool(), CalculatorTool()],
    )
    session = Session.create(agent.name)
    model = OpenAICompatibleModel(
        base_url="https://modelservice.jdcloud.com/coding/openai/v1",
        api_key="pk-d00e0bab-3e43-4221-bb58-2a84a925058d",
        model="GLM-5",
    )

    # Create observability handlers
    logger = EventLogger(verbose=True)
    metrics = MetricsCollector()
    recorder = EventRecorder()

    # Create run and attach handlers
    run = Run.create(agent, session, model)
    run.on_event(logger)       # 1. Console logging
    run.on_event(metrics)      # 2. Metrics collection
    run.on_event(recorder)     # 3. Event recording

    # Execute
    user_input = input("\n💬 输入消息 (回车使用默认): ").strip()
    if not user_input:
        user_input = "用 echo 说你好，然后计算 25 * 4"

    print(f"\n💬 User: {user_input}")
    print("\n" + "─" * 60)
    print("📊 事件流 (实时):")
    print("─" * 60)

    # Run and collect events
    async for _ in run.execute(user_input):
        pass  # Events are handled by callbacks

    # Show metrics
    print("\n" + "─" * 60)
    print("📈 统计指标:")
    print("─" * 60)
    report = metrics.report()
    print(f"  • 执行次数: {report['runs']}")
    print(f"  • 模型调用: {report['model_calls']}")
    print(f"  • 工具调用: {report['tool_calls']}")
    print(f"  • 错误次数: {report['tool_errors']}")
    print(f"  • 耗时: {report['duration_seconds']:.2f}s")

    # Show recorded events
    print("\n" + "─" * 60)
    print("📝 事件记录 (JSON):")
    print("─" * 60)
    print(recorder.export()[:500] + "..." if len(recorder.export()) > 500 else recorder.export())

    print("\n" + "=" * 60)
    print("✅ 可观测性演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
