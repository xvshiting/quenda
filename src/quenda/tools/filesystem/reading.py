"""
read_file tool - See specific content.

Covers: cat, head, tail, sed -n

Examples:
    read_file(path="app.py")                       # Read entire file
    read_file(path="app.py", start=1, end=100)     # Read lines 1-100
    read_file(path="app.log", start=-50)           # Read last 50 lines
    read_file(path="config.json", end=30)          # Read first 30 lines
    read_file(path="photo.jpg")                    # Read image file (vision support)
    read_file(path="https://example.com/img.png")  # Read image from URL
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import override
from urllib.parse import urlparse

from quenda.kernel.tool import Tool
from quenda.kernel.types import ImageContent, ToolResult

from .image_utils import (
    get_image_dimensions,
    infer_media_type,
    is_image_file,
    read_image_file,
    read_image_url,
)


@dataclass
class ReadFileConfig:
    """Configuration for read_file tool."""

    max_read_chars: int = 100000  # 100KB max file read
    max_image_tokens: int = 4000  # Max tokens for image content


# URL pattern for detecting web URLs
URL_PATTERN = re.compile(r"^https?://")


def _is_url(path: str) -> bool:
    """Check if path is a URL."""
    return bool(URL_PATTERN.match(path))


def _is_image_url(url: str) -> bool:
    """Check if URL points to an image based on extension."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return any(path_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))


def _validate_path(workspace: Path, path: str) -> tuple[Path, str | None]:
    """Validate path is within workspace. Returns (resolved_path, error_message)."""
    try:
        resolved = (workspace / path).resolve()
        if not str(resolved).startswith(str(workspace.resolve())):
            return resolved, "Access denied - path outside workspace"
        return resolved, None
    except Exception as e:
        return Path(path), f"Invalid path: {e}"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text if needed. Returns (text, was_truncated)."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]", True
    return text, False


class ReadFileTool(Tool):
    """
    Read file content with range selection.

    Covers: cat, head, tail, sed -n
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: ReadFileConfig | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or ReadFileConfig()

    @property
    @override
    def name(self) -> str:
        return "read_file"

    @property
    @override
    def description(self) -> str:
        return (
            "Read file content. Supports reading specific line ranges. "
            "Also supports reading image files (png, jpg, gif, webp) and image URLs. "
            "When reading images, returns the image content for vision understanding. "
            "Use negative start for last N lines."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File path to read. Can be a local file path or an image URL "
                        "(https://... ending with .png, .jpg, .jpeg, .gif, .webp). "
                        "Images are automatically processed for vision understanding."
                    ),
                },
                "start": {
                    "type": "integer",
                    "description": "Start line (1-indexed). Negative values read last N lines (e.g., -100 = last 100 lines). Default: 1",
                    "default": 1,
                },
                "end": {
                    "type": "integer",
                    "description": "End line (inclusive). Omit to read to end of file.",
                },
            },
            "required": ["path"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs.get("path", "")
        start = kwargs.get("start", 1)
        end = kwargs.get("end")

        if not isinstance(path, str):
            return ToolResult("", self.name, "Error: path must be a string", is_error=True)

        # Handle URLs (images only for now)
        if _is_url(path):
            return self._handle_url(path)

        # Handle local files
        file_path, error = _validate_path(self.workspace, path)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        if not file_path.exists():
            return ToolResult("", self.name, f"Error: File not found: {path}", is_error=True)

        if not file_path.is_file():
            return ToolResult("", self.name, f"Error: Not a file: {path}", is_error=True)

        # Handle image files
        if is_image_file(file_path):
            return self._handle_image_file(file_path, path)

        # Handle text files
        return self._handle_text_file(file_path, path, start, end)

    def _handle_url(self, url: str) -> ToolResult:
        """Handle URL (currently only image URLs)."""
        if not _is_image_url(url):
            return ToolResult(
                "",
                self.name,
                f"Error: URL does not appear to be an image. Only image URLs are supported: {url}",
                is_error=True,
            )

        try:
            image_content = read_image_url(url, self.config.max_image_tokens)
            width, height = get_image_dimensions(
                base64.b64decode(image_content.data) if image_content.data else b""
            )
            return ToolResult(
                "",
                self.name,
                f"Image from URL: {url}\nDimensions: {width}x{height}",
                display_hint=url[:40] if len(url) <= 40 else "..." + url[-37:],
                result_summary=f"{width}x{height}",
                image_content=image_content,
            )
        except Exception as e:
            return ToolResult("", self.name, f"Error reading image URL: {e}", is_error=True)

    def _handle_image_file(self, file_path: Path, path: str) -> ToolResult:
        """Handle local image file."""
        try:
            image_content = read_image_file(file_path, self.config.max_image_tokens)
            width, height = get_image_dimensions(
                base64.b64decode(image_content.data) if image_content.data else b""
            )
            size_kb = file_path.stat().st_size / 1024

            return ToolResult(
                "",
                self.name,
                f"Image: {path}\nDimensions: {width}x{height}\nSize: {size_kb:.1f}KB",
                display_hint=file_path.name,
                result_summary=f"{width}x{height}",
                image_content=image_content,
            )
        except Exception as e:
            return ToolResult("", self.name, f"Error reading image: {e}", is_error=True)

    def _handle_text_file(
        self,
        file_path: Path,
        path: str,
        start: object,
        end: object,
    ) -> ToolResult:
        """Handle text file (original logic)."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            total_lines = len(lines)

            # Handle negative start (last N lines)
            start_line = int(start) if isinstance(start, (int, float)) else 1
            if start_line < 0:
                start_line = max(1, total_lines + start_line + 1)

            end_line = int(end) if isinstance(end, (int, float)) else total_lines
            if end_line is None or end_line > total_lines:
                end_line = total_lines

            # Extract lines
            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, end_line)
            selected_lines = lines[start_idx:end_idx]
            lines_read = len(selected_lines)

            # Format with line numbers
            output_lines = [
                f"{i:6d}\t{line}"
                for i, line in enumerate(selected_lines, start=start_line)
            ]
            output = "\n".join(output_lines)

            # Truncate if needed
            output, truncated = _truncate(output, self.config.max_read_chars)

            # Add header
            header = f"File: {path} (lines {start_line}-{end_line} of {total_lines})"
            if truncated:
                header += " [TRUNCATED]"

            # Build display_hint and result_summary
            display_hint = path if len(path) <= 40 else "..." + path[-37:]
            result_summary = (
                f"{lines_read} lines"
                if lines_read == total_lines
                else f"lines {start_line}-{end_line} of {total_lines}"
            )

            return ToolResult(
                "",
                self.name,
                f"{header}\n\n{output}",
                display_hint=display_hint,
                result_summary=result_summary,
            )

        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)