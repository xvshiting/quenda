#!/usr/bin/env python3
r"""
Runtime Demo - Multi-turn conversation with Agent, Session, and Run.

This demonstrates the full Kora Runtime flow.
"""

import asyncio

from kora import Agent
from kora.runtime import (
    RunCompleted,
    RunStarted,
    ToolExecuted,
)

from common import GLMModel, echo, calculate


# === Event Handler ===

def print_event(event: object) -> None:
    """Print events as they occur."""
    if isinstance(event, RunStarted):
        print(f"\n▶️  [Run Started]")
    elif isinstance(event, ToolExecuted):
        status = "❌" if event.is_error else "✅"
        print(f"   🔧 [{event.tool_name}] {status} {event.result}")
    elif isinstance(event, RunCompleted):
        pass  # Handled separately


# === Main ===

async def chat_loop(agent: Agent) -> None:
    """Run an interactive chat loop."""
    print("\n" + "─" * 60)
    print("💬 开始对话 (输入 \\exit 退出, \\clear 清空历史)")
    print("─" * 60)

    session = agent.new_session()
    turn = 0

    while True:
        try:
            user_input = input("\n👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见!")
            break

        if not user_input:
            continue

        if user_input == "\\exit":
            print("\n👋 再见!")
            break

        if user_input == "\\clear":
            session.clear()
            print("🗑️  已清空对话历史")
            continue

        turn += 1
        print(f"\n─── 第 {turn} 轮 ───")

        result = await session.run(user_input, on_event=print_event)
        print(f"\n🤖 助手: {result}")


async def main() -> None:
    print("=" * 60)
    print("Kora Runtime - 多轮对话 Demo")
    print("=" * 60)

    agent = Agent(
        name="assistant",
        system_prompt="你是一个有帮助的助手。你可以使用工具来帮助用户。请用中文回答问题。",
        tools=[echo, calculate],
        model=GLMModel(),
    )

    print(f"\n✅ Agent: {agent.name}")
    print(f"   工具: {[t.name for t in agent.config.tools]}")
    print(f"\n✅ Model: GLM-5")

    await chat_loop(agent)

    print("\n" + "=" * 60)
    print("✅ 会话结束")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
