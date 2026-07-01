#!/usr/bin/env python3
r"""
Quick Start Demo - Using the Provider system with detailed output.

This demonstrates the new Provider-centric architecture with observability.
"""

import asyncio
import os
from pathlib import Path

from quenda import Agent
from quenda.runtime import (
    ModelResponded,
    RunCompleted,
    RunStarted,
    ToolExecuted,
)
from quenda.tools import get_core_tools
from quenda.providers import get_provider_registry

from common import (
    echo,
    calculate,
    get_model,
    get_deepseek_model,
    get_openai_model,
    get_anthropic_model,
    get_moonshot_model,
    get_dashscope_model,
    GLMModel,  # Legacy compatibility
)


# === Configuration ===

# Choose your provider/model (set via environment variable)
# Options: deepseek, deepseek-anthropic, openai, anthropic, moonshot, dashscope, jdcloud, ollama
PROVIDER = os.environ.get("KORA_PROVIDER", "deepseek")
MODEL_ID = os.environ.get("KORA_MODEL", "deepseek-v4-flash")


def create_model():
    """Create a model based on environment configuration."""
    registry = get_provider_registry()

    # Check if provider is available
    if not registry.has_provider(PROVIDER):
        available = registry.list_providers()
        raise ValueError(
            f"Provider '{PROVIDER}' not found. Available: {available}\n"
            "Set KORA_PROVIDER environment variable, e.g:\n"
            "  export KORA_PROVIDER=deepseek\n"
            "  export KORA_MODEL=deepseek-v4-flash"
        )

    provider = registry.get_provider(PROVIDER)

    # Check if model is available
    if not provider.has_model(MODEL_ID):
        available = [m.id for m in provider.list_models()]
        raise ValueError(
            f"Model '{MODEL_ID}' not found in provider '{PROVIDER}'.\n"
            f"Available models: {available}"
        )

    return registry.get_model(PROVIDER, MODEL_ID)


# === Event Handler ===

def print_event(event: object) -> None:
    """Print events with details."""
    if isinstance(event, RunStarted):
        print(f"  🚀 Run started")
    elif isinstance(event, ModelResponded):
        if event.tool_calls:
            print(f"  🤖 Model requested tools: {[tc['name'] for tc in event.tool_calls]}")
        else:
            content_preview = event.content[:100] if event.content else ""
            print(f"  🤖 Model thinking...")
    elif isinstance(event, ToolExecuted):
        status = "❌" if event.is_error else "✅"
        result_preview = event.result[:50] if len(event.result) > 50 else event.result
        print(f"  🔧 Tool [{event.tool_name}] {status} {result_preview}{'...' if len(event.result) > 50 else ''}")
    elif isinstance(event, RunCompleted):
        print(f"  ✅ Run completed ({event.total_steps} steps)")


# === Main ===

async def main() -> None:
    print("=" * 60)
    print("Kora Quick Start Demo")
    print("Provider-centric Architecture")
    print("=" * 60)

    # Show available providers
    registry = get_provider_registry()
    print(f"\n📦 Available providers: {registry.list_providers()}")

    # Create model
    try:
        model = create_model()
        print(f"\n✅ Model: {model.provider.id}/{model.id}")
        print(f"   Context window: {model.context_window or 'unknown'}")
        print(f"   Tool calling: {model.tool_calling}")
    except ValueError as e:
        print(f"\n❌ {e}")
        return

    # Define workspace (current directory)
    workspace = Path(".")

    # Create agent with tools
    agent = Agent(
        name="assistant",
        system_prompt="你是一个有帮助的助手。使用工具来帮助用户完成任务。",
        tools=[
            # Simple tools from @tool decorator
            echo,
            calculate,
            # Core tools for Coding Agent
            *get_core_tools(workspace),
        ],
        model=model,
    )
    print(f"\n✅ Agent: {agent.name}")
    print(f"   Tools: echo, calculate, list_files, search_text, read_file, write_file, apply_patch, run_shell")
    print(f"   Workspace: {workspace.resolve()}")

    # Open a persistent session
    session = agent.open_session()
    print(f"\n✅ Session: {session.id[:8]}...")

    # Chat loop
    print("\n" + "─" * 60)
    print("💬 开始对话 (输入 \\exit 退出, \\clear 清空历史)")
    print("─" * 60)

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

        if user_input == "\\history":
            print(f"\n📜 对话历史 ({len(session)} 条消息):")
            for i, msg in enumerate(session.messages):
                role = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(msg.role, "❓")
                preview = msg.content[:50] if isinstance(msg.content, str) else f"<{len(list(msg.content))} items>"
                print(f"   {i+1}. {role} {preview}...")
            continue

        if user_input == "\\help":
            print("\n📖 帮助:")
            print("   \\exit   - 退出程序")
            print("   \\clear  - 清空对话历史")
            print("   \\history - 查看对话历史")
            print("   \\help   - 显示帮助")
            print("   \\providers - 显示可用 providers")
            continue

        if user_input == "\\providers":
            print(f"\n📦 可用 Providers:")
            for provider_id in registry.list_providers():
                provider = registry.get_provider(provider_id)
                models = [m.id for m in provider.list_models()]
                print(f"   {provider_id}: {models}")
            continue

        # Send message
        print()
        result = await session.send(user_input, on_event=print_event)
        print(f"\n🤖 助手: {result}")

    print(f"\n✅ 会话结束，共 {len(session)} 条消息")


if __name__ == "__main__":
    asyncio.run(main())