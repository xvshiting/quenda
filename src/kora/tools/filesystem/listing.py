"""
list_files tool - See what exists.

Covers: ls, find, tree

Examples:
    list_files()                          # List workspace root
    list_files(path="src/kora")           # List specific directory
    list_files(path=".", depth=3)         # Tree view with depth limit
    list_files(pattern="*.py")            # Filter by glob pattern
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


@dataclass
class ListFilesConfig:
    """Configuration for list_files tool."""

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


class ListFilesTool(Tool):
    """
    List files and directories.

    Covers: ls, find, tree
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: ListFilesConfig | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or ListFilesConfig()

    @property
    @override
    def name(self) -> str:
        return "list_files"

    @property
    @override
    def description(self) -> str:
        return "List files and directories in the workspace. Use this to explore project structure."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Default: workspace root.",
                    "default": ".",
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth to traverse. 1 = flat list, 2+ = tree view.",
                    "default": 1,
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '**/*.md').",
                },
            },
            "required": [],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs.get("path", ".")
        depth = int(kwargs.get("depth", 1))
        pattern = kwargs.get("pattern")

        if not isinstance(path, str):
            return ToolResult("", self.name, "Error: path must be a string", is_error=True)

        dir_path, error = _validate_path(self.workspace, path)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        if not dir_path.exists():
            return ToolResult("", self.name, f"Error: Directory not found: {path}", is_error=True)

        if not dir_path.is_dir():
            return ToolResult("", self.name, f"Error: Not a directory: {path}", is_error=True)

        try:
            if depth == 1:
                output = self._list_flat(dir_path, pattern)
            else:
                output = self._list_tree(dir_path, depth, pattern)

            output, truncated = _truncate(output, self.config.max_output_chars)
            if truncated:
                output += "\n\n[Output truncated. Use 'pattern' to filter or reduce 'depth'.]"

            return ToolResult("", self.name, output)

        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)

    def _list_flat(self, dir_path: Path, pattern: str | None) -> str:
        """Flat directory listing."""
        entries = []
        for entry in sorted(dir_path.iterdir()):
            if pattern and not entry.match(pattern):
                continue
            icon = "📁" if entry.is_dir() else "📄"
            entries.append(f"{icon} {entry.name}")

        if not entries:
            return f"Directory '{dir_path.relative_to(self.workspace)}' is empty"

        return f"Contents of '{dir_path.relative_to(self.workspace)}':\n" + "\n".join(entries)

    def _list_tree(self, dir_path: Path, max_depth: int, pattern: str | None) -> str:
        """Tree-style directory listing."""
        lines = [f"📂 {dir_path.relative_to(self.workspace)}/"]

        def walk(current: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return

            try:
                entries = sorted(current.iterdir())
            except PermissionError:
                lines.append(f"{prefix}└── [Permission denied]")
                return

            for i, entry in enumerate(entries):
                if pattern and entry.is_file() and not entry.match(pattern):
                    continue

                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}📂 {entry.name}/")
                    if depth < max_depth:
                        new_prefix = prefix + ("    " if is_last else "│   ")
                        walk(entry, new_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}📄 {entry.name}")

        walk(dir_path, "", 1)
        return "\n".join(lines)
