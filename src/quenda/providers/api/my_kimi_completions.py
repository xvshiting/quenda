"""
Custom Kimi-style Completions API implementation.

This is a specialized API for non-standard Kimi-style endpoints that:
- Don't support OpenAI's standard tool calling format
- May return tool calls in content as JSON or XML
- Don't accept role: tool messages

This is NOT the official Kimi/Moonshot API. For official Kimi support,
use the moonshot provider with openai-completions API.

Used by:
- Custom Kimi-style deployments without tool-call-parser
- Non-standard OpenAI-compatible endpoints
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from typing import TYPE_CHECKING, override

from quenda.kernel.types import Message, ModelResponse, StreamChunk, ToolCall, UsageStats
from quenda.kernel.tool import Tool
from quenda.providers.api.base import Api
from quenda.providers.api.converters import (
    convert_messages_to_openai,
    convert_tools_to_openai,
)
from quenda.providers.errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from quenda.providers.retry import retry_with_backoff

if TYPE_CHECKING:
    pass


# System prompt to inject when tools are available (for servers without tool-call-parser)
TOOL_CALL_INSTRUCTION = """When you need to use a tool, respond ONLY with a JSON object in this exact format:
{"name": "tool_name", "arguments": {"param": "value"}}

For multiple tool calls, respond ONLY with a JSON array:
[{"name": "tool_name1", "arguments": {...}}, {"name": "tool_name2", "arguments": {...}}]

CRITICAL RULES:
1. Output ONLY the JSON - no text before, no text after
2. Do NOT say "I will..." or "Let me..." - just output the JSON
3. Do NOT use markdown code blocks - just raw JSON
4. If you need information or want to perform an action, you MUST call a tool
5. Only respond with text when you have the final answer for the user"""


class MyKimiCompletionsApi(Api):
    """
    Custom Kimi-style completions API implementation.

    This is NOT the official Kimi/Moonshot API. It's designed for
    non-standard endpoints that:
    - Don't support OpenAI's standard tool calling format
    - May return tool calls in content as JSON or XML
    - Don't accept role: tool messages

    For official Kimi/Moonshot support, use the moonshot provider
    with openai-completions API instead.
    """

    @property
    def id(self) -> str:
        return "my-kimi-completions"

    @override
    def invoke(
        self,
        *,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str],
        model: str,
        messages: list[Message],
        tools: list[Tool],
        timeout: float | None,
        max_retries: int = 3,
    ) -> ModelResponse:
        """Invoke the model via custom Kimi-style API."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for this API. "
                "Install with: pip install openai"
            )

        @retry_with_backoff(max_retries=max_retries)
        def _invoke() -> ModelResponse:
            # Build client
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout or 120.0,
                default_headers=headers if headers else None,
            )

            # Convert messages - inject tool instructions if needed
            # NOTE: For endpoints without tool-call-parser, we don't send 'tools' parameter
            # Instead, we inject tool descriptions in the system prompt
            openai_messages = self._convert_messages_with_tool_instructions(messages, tools)

            try:
                # Make request WITHOUT tools parameter (endpoint doesn't support OpenAI tool format)
                response = client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                )

                # Convert response - parse tool calls from content
                return self._convert_response(response, tools)

            except openai.RateLimitError as e:
                retry_after = None
                if hasattr(e, "response") and e.response is not None:
                    retry_after_str = e.response.headers.get("retry-after")
                    if retry_after_str:
                        try:
                            retry_after = float(retry_after_str)
                        except ValueError:
                            pass
                raise RateLimitError(str(e), retry_after=retry_after)

            except openai.APIConnectionError as e:
                raise NetworkError(f"Connection failed: {e}")

            except openai.AuthenticationError as e:
                raise AuthenticationError(f"Authentication failed: {e}")

            except openai.APIStatusError as e:
                if e.status_code == 401:
                    raise AuthenticationError(f"Authentication failed: {e}")
                elif e.status_code == 429:
                    raise RateLimitError(str(e))
                elif e.status_code >= 500:
                    raise APIError(f"Server error: {e}")
                else:
                    raise APIError(f"API error: {e}")

            except openai.APIError as e:
                raise APIError(f"API error: {e}")

        return _invoke()

    @override
    def invoke_stream(
        self,
        *,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str],
        model: str,
        messages: list[Message],
        tools: list[Tool],
        timeout: float | None,
        max_retries: int = 3,
    ) -> Generator[StreamChunk, None, None]:
        """Invoke the model with streaming response."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for this API. "
                "Install with: pip install openai"
            )

        # Build client
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout or 120.0,
            default_headers=headers if headers else None,
        )

        # Convert messages - inject tool instructions if needed
        openai_messages = self._convert_messages_with_tool_instructions(messages, tools)

        try:
            # Make streaming request WITHOUT tools parameter
            stream = client.chat.completions.create(
                model=model,
                messages=openai_messages,
                stream=True,
            )

            # Track content buffer for parsing tool calls
            content_buffer: str = ""

            for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle content
                if delta.content:
                    content_buffer += delta.content
                    yield StreamChunk(content=delta.content, is_final=False)

                # Check for finish
                if chunk.choices[0].finish_reason:
                    # Try to parse tool calls from content buffer
                    if content_buffer and tools:
                        parsed_calls = self._try_parse_tool_calls_from_content(
                            content_buffer,
                            tools
                        )
                        if parsed_calls:
                            yield StreamChunk(tool_calls=parsed_calls, is_final=True)
                        else:
                            yield StreamChunk(is_final=True)
                    else:
                        yield StreamChunk(is_final=True)

        except openai.RateLimitError as e:
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                retry_after_str = e.response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        pass
            raise RateLimitError(str(e), retry_after=retry_after)

        except openai.APIConnectionError as e:
            raise NetworkError(f"Connection failed: {e}")

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}")

        except openai.APIStatusError as e:
            if e.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {e}")
            elif e.status_code == 429:
                raise RateLimitError(str(e))
            else:
                raise APIError(f"API error: {e}")

        except openai.APIError as e:
            raise APIError(f"API error: {e}")

    def _convert_messages_with_tool_instructions(
        self,
        messages: list[Message],
        tools: list[Tool] | None,
    ) -> list[dict]:
        """
        Convert messages and inject tool call instructions if needed.

        For endpoints without tool-call-parser, we need to:
        1. Inject explicit instructions in the system message about how to format tool calls
        2. Convert tool result messages to user messages (API doesn't support role: tool)
        3. Handle assistant messages with tool calls (convert to JSON format)
        """
        openai_messages = convert_messages_to_openai(messages)

        converted_messages = []
        for msg in openai_messages:
            if msg.get("role") == "tool":
                # Convert tool result to user message format
                # Clear instruction: continue with tool call or give final answer
                tool_call_id = msg.get("tool_call_id", "unknown")
                content = msg.get("content", "")
                converted_messages.append({
                    "role": "user",
                    "content": f"[Tool result for {tool_call_id}]:\n{content}\n\nIf you need more information, call another tool with JSON. If you have the answer, respond directly.",
                })
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Convert assistant tool_calls to JSON format
                # This "teaches" the model what format to output next
                tool_calls = msg.get("tool_calls", [])
                calls_json = []
                for tc in tool_calls:
                    name = tc.get("function", {}).get("name", "unknown")
                    args_str = tc.get("function", {}).get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}
                    calls_json.append({"name": name, "arguments": args})

                # Output as JSON array - model will mimic this format
                converted_messages.append({
                    "role": "assistant",
                    "content": json.dumps(calls_json, ensure_ascii=False),
                })
            else:
                converted_messages.append(msg)

        if not tools:
            return converted_messages

        # Always inject tool instructions (model may need to make more tool calls)
        tool_instruction_added = False
        tool_descriptions = self._format_tool_descriptions(tools)

        for msg in converted_messages:
            if msg.get("role") == "system":
                # Append tool instructions to existing system message
                existing_content = msg.get("content", "")
                msg["content"] = f"{existing_content}\n\n{TOOL_CALL_INSTRUCTION}\n\nAvailable tools:\n{tool_descriptions}"
                tool_instruction_added = True
                break

        # If no system message, prepend one
        if not tool_instruction_added:
            converted_messages.insert(0, {
                "role": "system",
                "content": f"{TOOL_CALL_INSTRUCTION}\n\nAvailable tools:\n{tool_descriptions}",
            })

        return converted_messages

    def _format_tool_descriptions(self, tools: list[Tool]) -> str:
        """Format tool descriptions for the system prompt."""
        descriptions = []
        for tool in tools:
            params_desc = ""
            if tool.parameters and "properties" in tool.parameters:
                params = []
                for name, prop in tool.parameters["properties"].items():
                    if name == "_summary":
                        continue
                    param_type = prop.get("type", "any")
                    param_desc = prop.get("description", "")
                    params.append(f"  - {name} ({param_type}): {param_desc}")
                if params:
                    params_desc = "\n".join(params)

            descriptions.append(f"- {tool.name}: {tool.description}\n  Arguments:\n{params_desc}")

        return "\n".join(descriptions)

    def _convert_response(self, response, tools: list[Tool] | None) -> ModelResponse:
        """Convert response to Quenda format."""
        choice = response.choices[0]
        tool_calls = []

        # Standard OpenAI tool calls format
        if choice.message.tool_calls:
            for i, tc in enumerate(choice.message.tool_calls):
                args = (
                    json.loads(tc.function.arguments)
                    if tc.function.arguments
                    else {}
                )
                # Ensure id is not empty - generate one if missing
                call_id = tc.id if tc.id else f"call_{i}"
                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        # If no standard tool calls but content looks like tool calls,
        # try to parse it (for servers without tool-call-parser)
        elif choice.message.content and tools:
            parsed_calls = self._try_parse_tool_calls_from_content(
                choice.message.content,
                tools
            )
            if parsed_calls:
                tool_calls = parsed_calls

        # Extract usage statistics
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = UsageStats(
                input_tokens=getattr(response.usage, 'prompt_tokens', 0) or 0,
                output_tokens=getattr(response.usage, 'completion_tokens', 0) or 0,
                cached_input_tokens=None,
                reasoning_tokens=None,
            )

        # If we extracted tool calls from content, don't return the content
        content = choice.message.content if not tool_calls else None

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage=usage,
        )

    def _sanitize_json_string(self, content: str) -> str:
        """
        Sanitize JSON string by escaping control characters.

        Some models output JSON with actual newlines/tabs inside string values
        instead of \\n/\\t escape sequences. This method fixes that.
        """
        # Simple approach: try to parse first, if it fails, try sanitizing
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass

        # Escape control characters inside JSON string values
        # This is a simple heuristic that works for most cases
        result = []
        in_string = False
        escape_next = False
        i = 0

        while i < len(content):
            char = content[i]

            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue

            if char == '\\' and in_string:
                result.append(char)
                escape_next = True
                i += 1
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue

            if in_string:
                # Inside a string, escape control characters
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                else:
                    result.append(char)
            else:
                result.append(char)

            i += 1

        return ''.join(result)

    def _try_parse_json_content(self, content: str) -> list[dict] | dict | None:
        """
        Try to parse JSON content, handling control characters.

        Returns parsed data or None if parsing fails.
        """
        # First try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try sanitizing and parsing
        try:
            sanitized = self._sanitize_json_string(content)
            return json.loads(sanitized)
        except json.JSONDecodeError:
            return None

    def _try_parse_tool_calls_from_content(
        self,
        content: str,
        tools: list[Tool],
    ) -> list[ToolCall]:
        """
        Try to parse tool calls from response content.

        This handles cases where the server doesn't have tool-call-parser enabled
        and returns tool calls as text in the content.

        Supports formats:
        1. Pure JSON: {"name": "tool_name", "arguments": {...}}
        2. JSON in text: Some text {"name": "tool_name", "arguments": {...}} more text
        3. JSON array: [{"name": "..."}, {"name": "..."}]
        4. Markdown code blocks: ```json {...} ```
        5. XML: <tool>name</tool><param>value</param>
        """
        tool_calls = []

        # Get tool names for matching
        tool_names = {t.name for t in tools}

        # Strategy 1: Try parsing entire content as JSON
        if content.strip().startswith('['):
            data = self._try_parse_json_content(content)
            if data and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name') or item.get('function', {}).get('name')
                        args = item.get('arguments') or item.get('function', {}).get('arguments', {})
                        if name and name in tool_names:
                            if isinstance(args, str):
                                args = json.loads(args) if args else {}
                            tool_calls.append(ToolCall(
                                id=f"call_{len(tool_calls)}",
                                name=name,
                                arguments=args if isinstance(args, dict) else {},
                            ))
                return tool_calls
        elif content.strip().startswith('{'):
            data = self._try_parse_json_content(content)
            if data and isinstance(data, dict):
                name = data.get('name') or data.get('function', {}).get('name')
                args = data.get('arguments') or data.get('function', {}).get('arguments', {})
                if name and name in tool_names:
                    if isinstance(args, str):
                        args = json.loads(args) if args else {}
                    tool_calls.append(ToolCall(
                        id="call_0",
                        name=name,
                        arguments=args if isinstance(args, dict) else {},
                    ))
                return tool_calls

        # Strategy 2: Find JSON objects in markdown code blocks
        code_block_pattern = r'```(?:json)?\s*\n(.*?)\n```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        for match in matches:
            data = self._try_parse_json_content(match)
            if not data:
                continue
            if isinstance(data, dict):
                name = data.get('name') or data.get('function', {}).get('name')
                args = data.get('arguments') or data.get('function', {}).get('arguments', {})
                if name and name in tool_names:
                    if isinstance(args, str):
                        args = json.loads(args) if args else {}
                    tool_calls.append(ToolCall(
                        id=f"call_{len(tool_calls)}",
                        name=name,
                        arguments=args if isinstance(args, dict) else {},
                    ))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name') or item.get('function', {}).get('name')
                        args = item.get('arguments') or item.get('function', {}).get('arguments', {})
                        if name and name in tool_names:
                            if isinstance(args, str):
                                args = json.loads(args) if args else {}
                            tool_calls.append(ToolCall(
                                id=f"call_{len(tool_calls)}",
                                name=name,
                                arguments=args if isinstance(args, dict) else {},
                            ))

        # Strategy 3: Find JSON objects embedded in text
        # Use brace counting to handle nested JSON properly
        if not tool_calls:
            # Find all positions where "name" appears in the content
            # Then look for surrounding JSON objects
            name_pattern = r'"name"\s*:\s*"[^"]+"'
            for match in re.finditer(name_pattern, content):
                # Find the opening brace before this match
                pos = match.start()
                brace_start = -1
                for i in range(pos, -1, -1):
                    if content[i] == '{':
                        brace_start = i
                        break

                if brace_start == -1:
                    continue

                # Count braces to find the end
                brace_count = 0
                brace_end = brace_start
                for i, char in enumerate(content[brace_start:], brace_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            brace_end = i + 1
                            break

                # Try to parse the JSON
                json_str = content[brace_start:brace_end]
                data = self._try_parse_json_content(json_str)
                if not data:
                    continue

                name = data.get('name') or data.get('function', {}).get('name')
                args = data.get('arguments') or data.get('function', {}).get('arguments', {})

                if name and name in tool_names:
                    if isinstance(args, str):
                        args = json.loads(args) if args else {}
                    tool_calls.append(ToolCall(
                        id=f"call_{len(tool_calls)}",
                        name=name,
                        arguments=args if isinstance(args, dict) else {},
                    ))

        # Strategy 4: Parse XML-style tool calls (Kimi format)
        # Format: <tool>tool_name</tool>\n<parameter>{"arg": "value"}</parameter>
        if not tool_calls:
            for tool_name in tool_names:
                tool_pattern = rf'<tool>\s*{re.escape(tool_name)}\s*</tool>'
                if re.search(tool_pattern, content, re.IGNORECASE):
                    args = {}

                    # Try to parse <parameter> with JSON content
                    param_match = re.search(r'<parameter>\s*(.*?)\s*</parameter>', content, re.DOTALL)
                    if param_match:
                        param_content = param_match.group(1).strip()
                        # Try to parse as JSON
                        try:
                            args = json.loads(param_content)
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain value
                            args = {"value": param_content}
                    else:
                        # Fallback: parse individual <param>value</param> tags
                        param_pattern = r'<(\w+)>([^<]*)</\1>'
                        for match in re.finditer(param_pattern, content):
                            param_name = match.group(1)
                            if param_name.lower() not in ('tool', 'function', 'parameter'):
                                args[param_name] = match.group(2).strip()

                    tool_calls.append(ToolCall(
                        id=f"call_{len(tool_calls)}",
                        name=tool_name,
                        arguments=args,
                    ))

        return tool_calls