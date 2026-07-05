"""
Message and tool format converters.

Converts Quenda's internal format to provider-specific formats.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from quenda.kernel.types import ImageContent, TextContent, ToolCall, ToolResult

if TYPE_CHECKING:
    from quenda.kernel.tool import Tool
    from quenda.kernel.types import Message


def convert_messages_to_openai(messages: list[Message]) -> list[dict]:
    """
    Convert Quenda messages to OpenAI-compatible format.

    This format is used by:
    - OpenAI
    - DashScope
    - JDCloud
    - OpenRouter
    - Most OpenAI-compatible APIs

    OpenAI message format for tool calls:
    1. assistant message with tool_calls
    2. tool message with tool_call_id and content (one per tool call)

    Quenda format:
    - assistant: content=ToolCall list
    - user: content=ToolResult list

    Multimodal format:
    - user: content=[TextContent, ImageContent, ...]
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
                # Some providers require content to be a string or omitted entirely
                # Use empty string for compatibility
                openai_messages.append({
                    "role": "assistant",
                    "content": "",  # Empty string for better compatibility
                    "tool_calls": tool_calls,
                })

            elif isinstance(first_item, ToolResult):
                # Tool results (from user message)
                for tr in items:
                    # Handle tool result with image content
                    if tr.image_content:
                        # Tool result contains image.
                        # OpenAI API doesn't support multimodal content in tool role messages.
                        # Workaround: send text in tool message, then send image in user message.

                        # 1. Tool message with text only
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tr.call_id,
                            "content": tr.content or "",
                        })

                        # 2. User message with image for vision understanding
                        image_parts = []
                        if tr.image_content.image_url:
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": tr.image_content.image_url},
                            })
                        elif tr.image_content.media_type and tr.image_content.data:
                            data_url = f"data:{tr.image_content.media_type};base64,{tr.image_content.data}"
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            })

                        if image_parts:
                            openai_messages.append({
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"[工具 {tr.name} 返回的图片内容]"},
                                    *image_parts,
                                ],
                            })
                    else:
                        # Text-only tool result
                        content = tr.content if tr.content is not None else ""
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tr.call_id,
                            "content": content,
                        })

            elif isinstance(first_item, (TextContent, ImageContent)):
                # Multimodal content (user message with text and/or images)
                content_parts = []
                for item in items:
                    if isinstance(item, TextContent):
                        content_parts.append({
                            "type": "text",
                            "text": item.text,
                        })
                    elif isinstance(item, ImageContent):
                        if item.image_url:
                            # URL 形式
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {"url": item.image_url},
                            })
                        elif item.media_type and item.data:
                            # Base64 形式
                            data_url = f"data:{item.media_type};base64,{item.data}"
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            })

                openai_messages.append({
                    "role": msg.role,
                    "content": content_parts,
                })

    return openai_messages


def convert_tools_to_openai(tools: list[Tool]) -> list[dict]:
    """
    Convert Quenda tools to OpenAI-compatible format.

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
