"""
Core types for the Kernel layer.

These types are pure data structures with no external dependencies.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class TextContent:
    """文本内容块，用于多模态消息。"""

    type: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True)
class ImageContent:
    """
    图片内容块，用于多模态消息。

    支持两种形式：
    - URL：通过 image_url 指定图片地址
    - Base64：通过 media_type 和 data 指定编码数据
    """

    type: Literal["image"] = "image"
    image_url: str | None = None  # URL 形式
    media_type: str | None = None  # Base64 形式的媒体类型 (image/png, image/jpeg 等)
    data: str | None = None  # Base64 编码的图片数据


@dataclass(frozen=True)
class ImageSource:
    """
    图片来源，使用 URI scheme 风格。

    scheme:
    - file: 本地文件
    - https: 远程 HTTPS URL
    - http: 远程 HTTP URL
    - data: 内嵌 base64 数据
    """

    scheme: Literal["file", "https", "http", "data"]
    uri: str  # "file:///path/to/image.jpg" 或 "https://..." 或 "data:image/jpeg;base64,..."
    media_type: str  # image/jpeg, image/png 等
    filename: str | None = None  # 原始文件名，用于显示


@dataclass(frozen=True)
class ImageRef:
    """
    图片引用，用于会话中的图片管理。

    用户看到的是 [img0]，实际图片数据通过此引用结构管理。
    消息历史只存引用标记，不存图片 payload。
    """

    id: str  # 引用 ID，如 "img0"
    source: ImageSource
    size_bytes: int | None = None  # 文件大小，可选

    def display_name(self) -> str:
        """获取用于显示的名称。"""
        if self.source.filename:
            return self.source.filename
        return self.id


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
        image_content: Optional image content when the tool reads an image file.
            Used by read_file tool when reading image files. The image data is
            passed to the model for vision understanding.
    """

    call_id: str
    name: str
    content: str
    is_error: bool = False
    duration_ms: int = 0
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""
    image_content: ImageContent | None = None


@dataclass(frozen=True)
class Message:
    """
    A message in the conversation.

    content 支持三种形式：
    - str: 纯文本消息
    - Sequence[ToolCall | ToolResult]: 工具调用或结果
    - Sequence[TextContent | ImageContent]: 多模态内容（文本+图片）
    """

    role: Literal["user", "assistant", "system"]
    content: str | Sequence[ToolCall | ToolResult] | Sequence[TextContent | ImageContent]


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
