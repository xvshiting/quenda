"""
Message and tool format converters.

Converts Kora's internal format to provider-specific formats.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from kora.kernel.types import ToolCall, ToolResult

if TYPE_CHECKING:
    from kora.kernel.tool import Tool
    from kora.kernel.types import Message


def convert_messages_to_openai(messages: list[Message]) -> list[dict]:
    """
    Convert Kora messages to OpenAI-compatible format.

    This format is used by:
    - OpenAI
    - DashScope
    - JDCloud
    - OpenRouter
    - Most OpenAI-compatible APIs

    OpenAI message format for tool calls:
    1. assistant message with tool_calls
    2. tool message with tool_call_id and content (one per tool call)

    Kora format:
    - assistant: content=ToolCall list
    - user: content=ToolResult list
    """
    openai_messages = []

    for msg in messages:
        if isinstance(msg.content, str):
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        else:
            items = list(msg.content)

            if not items:
                continue

            # Check the type of the first item
            first_item = items[0]

            if isinstance(first_item, ToolCall):
                # Assistant message with tool calls
                # Only add the assistant message with tool_calls
                # Tool results will come in a separate user message
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in items
                ]
                openai_messages.append({
                    "role": "assistant",
                    "tool_calls": tool_calls,
                })

            elif isinstance(first_item, ToolResult):
                # Tool results (from user message)
                for tr in items:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.call_id,
                        "content": tr.content,
                    })

    return openai_messages


def convert_tools_to_openai(tools: list[Tool]) -> list[dict]:
    """
    Convert Kora tools to OpenAI-compatible format.

    Automatically injects a _summary parameter for display purposes.
    The LLM is encouraged to fill this with a brief description of what it's doing.
    """
    converted_tools = []
    for tool in tools:
        # Inject _summary parameter into the schema
        parameters = dict(tool.parameters)

        if "properties" not in parameters:
            parameters["properties"] = {}

        # Add _summary parameter
        parameters["properties"]["_summary"] = {
            "type": "string",
            "description": "Brief description of what this tool call is doing (e.g., 'reading config file', 'running tests'). Shown to user for visibility.",
        }

        # _summary is optional, not in required
        converted_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": parameters,
            },
        })

    return converted_tools
