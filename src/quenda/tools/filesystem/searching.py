"""
search_text tool - Find where things are.

Covers: grep, rg

Uses ripgrep (rg) when available for fast search.
Falls back to native Python implementation.

Examples:
    search_text(pattern="AgentConfig")              # Search all files
    search_text(pattern="def run", path="src")      # Search in specific directory
    search_text(pattern="TODO", include="*.py")     # Search only Python files
    search_text(pattern="error", ignore_case=True)  # Case insensitive
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


@dataclass
class SearchTextConfig:
    """Configuration for search_text tool."""

    max_results: int = 100
    max_output_chars: int = 100000  # 100KB max output


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


class SearchTextTool(Tool):
    """
    Search for text patterns in files.

    Covers: grep, rg
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: SearchTextConfig | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or SearchTextConfig()

    @property
    @override
    def name(self) -> str:
        return "search_text"

    @property
    @override
    def description(self) -> str:
        return "Search for text patterns in files. Supports regex and file filtering."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (supports regex).",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search. Default: workspace root.",
                    "default": ".",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.md').",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case insensitive search.",
                    "default": False,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context around each match.",
                    "default": 2,
                },
            },
            "required": ["pattern"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        path = kwargs.get("path", ".")
        include = kwargs.get("include")
        ignore_case = bool(kwargs.get("ignore_case", False))
        context_lines = int(kwargs.get("context_lines", 2))

        if not isinstance(pattern, str):
            return ToolResult("", self.name, "Error: pattern must be a string", is_error=True)

        search_path, error = _validate_path(self.workspace, path if isinstance(path, str) else ".")
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        if not search_path.exists():
            return ToolResult("", self.name, f"Error: Path not found: {path}", is_error=True)

        # Try ripgrep first
        if self._has_ripgrep():
            return self._search_with_ripgrep(
                pattern=pattern,
                search_path=search_path,
                include=include if isinstance(include, str) else None,
                ignore_case=ignore_case,
                context_lines=context_lines,
            )

        # Fallback to native
        return self._search_native(
            pattern=pattern,
            search_path=search_path,
            include=include if isinstance(include, str) else None,
            ignore_case=ignore_case,
            context_lines=context_lines,
        )

    def _has_ripgrep(self) -> bool:
        """Check if ripgrep is available."""
        return shutil.which("rg") is not None

    def _search_with_ripgrep(
        self,
        pattern: str,
        search_path: Path,
        include: str | None,
        ignore_case: bool,
        context_lines: int,
    ) -> ToolResult:
        """Search using ripgrep."""
        args = [
            "rg",
            "--with-filename",
            "--line-number",
            "--column",
            "-C", str(context_lines),
            "--max-count", str(self.config.max_results),
        ]

        if ignore_case:
            args.append("-i")

        if include:
            args.extend(["--glob", include])

        args.append("--")
        args.append(pattern)
        args.append(str(search_path))

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout or result.stderr

            if not output:
                return ToolResult("", self.name, f"No matches found for: {pattern}")

            output, truncated = _truncate(output, self.config.max_output_chars)
            if truncated:
                output += "\n\n[Results truncated. Use 'include' to filter files.]"

            return ToolResult("", self.name, output)

        except subprocess.TimeoutExpired:
            return ToolResult("", self.name, "Error: Search timed out", is_error=True)
        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)

    def _search_native(
        self,
        pattern: str,
        search_path: Path,
        include: str | None,
        ignore_case: bool,
        context_lines: int,
    ) -> ToolResult:
        """Native Python search implementation."""
        try:
            flags = re.IGNORECASE if ignore_case else 0
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult("", self.name, f"Error: Invalid regex: {e}", is_error=True)

        matches = []
        files = [search_path] if search_path.is_file() else list(search_path.rglob("*"))

        for file_path in files:
            if not file_path.is_file():
                continue

            if include and not file_path.match(include):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    if compiled.search(line):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)

                        rel_path = file_path.relative_to(self.workspace)
                        context = []
                        for j in range(start, end):
                            prefix = ">>>" if j == i else "   "
                            context.append(f"{prefix} {rel_path}:{j+1}: {lines[j]}")

                        matches.append("\n".join(context))

                        if len(matches) >= self.config.max_results:
                            break

                if len(matches) >= self.config.max_results:
                    break

            except Exception:
                continue

        if not matches:
            return ToolResult("", self.name, f"No matches found for: {pattern}")

        output = "\n\n".join(matches)
        output, truncated = _truncate(output, self.config.max_output_chars)
        if truncated:
            output += "\n\n[Results truncated. Use 'include' to filter files.]"

        return ToolResult("", self.name, output)