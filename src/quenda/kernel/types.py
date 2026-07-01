"""
Core types for the Kernel layer.

These types are pure data structures with no external dependencies.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ToolResult:
    """
    The result of a tool execution.

    Attributes:
        call_id: The ID of the tool call this result corresponds to.
        name: The name of the tool that was executed.
        content: The output content of the tool.
        is_error: Whether the execution resulted in an error.
        duration_ms: Execution time in milliseconds.
        display_hint: Optional human-readable hint for display (e.g., "pyproject.toml").
            Shown in parentheses after the summary. Tools can provide this for better
            readability than raw arguments.
        change_preview: Optional diff preview for file modification tools.
            Should contain unified diff format showing only changed hunks.
            Only shown when there are actual changes.
        result_summary: Optional summary of the result (e.g., "47 lines", "23 matches").
            Shown after the tool name for quick understanding.
    """

    call_id: str
    name: str
    content: str
    is_error: bool = False
    duration_ms: int = 0
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


@dataclass(frozen=True)
class Message:
    """A message in the conversation."""

    role: Literal["user", "assistant", "system"]
    content: str | Sequence[ToolCall | ToolResult]


@dataclass(frozen=True)
class StreamChunk:
    """
    A chunk of streamed response.

    Used for streaming model responses incrementally.
    """

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    is_final: bool = False


@dataclass(frozen=True)
class UsageStats:
    """
    Token usage statistics from a model response.

    Providers return this information which can be aggregated
    for session-level tracking.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class ModelResponse:
    """
    Standardized model response.

    All model providers must convert their responses to this format.
    """

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence"] = "end_turn"
    usage: UsageStats | None = None
