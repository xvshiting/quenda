"""
read_file tool - See specific content.

Covers: cat, head, tail, sed -n

Examples:
    read_file(path="app.py")                       # Read entire file
    read_file(path="app.py", start=1, end=100)     # Read lines 1-100
    read_file(path="app.log", start=-50)           # Read last 50 lines
    read_file(path="config.json", end=30)          # Read first 30 lines
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


@dataclass
class ReadFileConfig:
    """Configuration for read_file tool."""

    max_read_chars: int = 100000  # 100KB max file read


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
        return "Read file content. Supports reading specific line ranges. Use negative start for last N lines."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read.",
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

        file_path, error = _validate_path(self.workspace, path)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        if not file_path.exists():
            return ToolResult("", self.name, f"Error: File not found: {path}", is_error=True)

        if not file_path.is_file():
            return ToolResult("", self.name, f"Error: Not a file: {path}", is_error=True)

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
            result_summary = f"{lines_read} lines" if lines_read == total_lines else f"lines {start_line}-{end_line} of {total_lines}"

            return ToolResult(
                "",
                self.name,
                f"{header}\n\n{output}",
                display_hint=display_hint,
                result_summary=result_summary,
            )

        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)