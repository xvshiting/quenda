"""Index-free Markdown memory tools for Quenda Code."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import override

from quenda.host.extensions import AgentExtensionContext
from quenda.host.registry import ToolRegistryBuilder
from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


_TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)
_MAX_RESULT_LIMIT = 20
_MAX_GET_LINES = 400
_MAX_GET_CHARS = 16_000


def _error(name: str, message: str) -> ToolResult:
    return ToolResult("", name, f"Error: {message}", is_error=True)


def _memory_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    resolved_root = root.resolve()
    files: list[Path] = []
    for path in root.rglob("*.md"):
        try:
            resolved = path.resolve()
            resolved.relative_to(resolved_root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            files.append(resolved)
    return sorted(files)


@dataclass(frozen=True)
class _Match:
    score: int
    path: Path
    line_number: int
    excerpt: str


class MemorySearchTool(Tool):
    """Search the user's detailed Markdown memory library."""

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root

    @property
    @override
    def name(self) -> str:
        return "memory_search"

    @property
    @override
    def description(self) -> str:
        return (
            "Search the current user's Quenda Code memory library. Use when "
            "historical decisions, project context, or prior work may help."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Words or phrase to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 6, max 20).",
                    "default": 6,
                },
            },
            "required": ["query"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 6)
        if not isinstance(query, str) or not query.strip():
            return _error(self.name, "query must be a non-empty string")
        if not isinstance(limit, int) or isinstance(limit, bool):
            return _error(self.name, "limit must be an integer")
        limit = max(1, min(limit, _MAX_RESULT_LIMIT))

        files = _memory_files(self.memory_root)
        if not files:
            return ToolResult(
                "",
                self.name,
                "No detailed memory files are available.",
                result_summary="0 results",
            )

        normalized_query = query.casefold().strip()
        terms = list(dict.fromkeys(
            token.casefold() for token in _TOKEN_PATTERN.findall(query)
        ))
        matches: list[_Match] = []
        for path in files:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue

            relative = path.relative_to(self.memory_root.resolve())
            path_text = str(relative).casefold()
            lines = content.splitlines()
            best_score = 0
            best_index = 0
            for index, line in enumerate(lines):
                normalized_line = line.casefold()
                matched_terms = sum(term in normalized_line for term in terms)
                score = matched_terms * 10
                if normalized_query in normalized_line:
                    score += 50
                score += sum(term in path_text for term in terms) * 4
                if score > best_score:
                    best_score = score
                    best_index = index

            if best_score == 0:
                continue
            start = max(0, best_index - 1)
            end = min(len(lines), best_index + 2)
            excerpt = "\n".join(lines[start:end]).strip()
            matches.append(_Match(
                score=best_score,
                path=relative,
                line_number=best_index + 1,
                excerpt=excerpt,
            ))

        matches.sort(key=lambda match: (-match.score, str(match.path)))
        selected = matches[:limit]
        if not selected:
            return ToolResult(
                "",
                self.name,
                f'No memory matched "{query}".',
                result_summary="0 results",
            )

        output = [f'Found {len(selected)} memory result(s) for "{query}":']
        for index, match in enumerate(selected, 1):
            output.extend([
                "",
                f"{index}. {match.path}:{match.line_number}",
                match.excerpt,
            ])
        return ToolResult(
            "",
            self.name,
            "\n".join(output),
            result_summary=f"{len(selected)} results",
        )


class MemoryGetTool(Tool):
    """Read a precise range from one detailed memory file."""

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root

    @property
    @override
    def name(self) -> str:
        return "memory_get"

    @property
    @override
    def description(self) -> str:
        return (
            "Read a Markdown memory file returned by memory_search. Paths are "
            "relative to the user's memory library."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative .md path returned by memory_search.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First 1-based line to return (default 1).",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last 1-based line to return.",
                },
            },
            "required": ["path"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs.get("path", "")
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line")
        if not isinstance(path, str) or not path.strip():
            return _error(self.name, "path must be a non-empty string")
        if not isinstance(start_line, int) or isinstance(start_line, bool):
            return _error(self.name, "start_line must be an integer")
        if end_line is not None and (
            not isinstance(end_line, int) or isinstance(end_line, bool)
        ):
            return _error(self.name, "end_line must be an integer")
        if start_line < 1:
            return _error(self.name, "start_line must be at least 1")

        root = self.memory_root.resolve()
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return _error(self.name, "path escapes the memory library")
        if candidate.suffix.lower() != ".md":
            return _error(self.name, "only Markdown memory files can be read")
        if not candidate.is_file():
            return _error(self.name, f"memory file not found: {path}")

        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            return _error(self.name, str(error))

        if end_line is None:
            end_line = min(len(lines), start_line + _MAX_GET_LINES - 1)
        if end_line < start_line:
            return _error(self.name, "end_line must not be before start_line")
        end_line = min(end_line, start_line + _MAX_GET_LINES - 1, len(lines))
        selected = "\n".join(lines[start_line - 1:end_line])
        if len(selected) > _MAX_GET_CHARS:
            selected = selected[:_MAX_GET_CHARS] + "\n… [truncated]"

        relative = candidate.relative_to(root)
        return ToolResult(
            "",
            self.name,
            f"{relative}:{start_line}-{end_line}\n\n{selected}",
            display_hint=str(relative),
            result_summary=f"lines {start_line}-{end_line}",
        )


def register(
    builder: ToolRegistryBuilder,
    context: AgentExtensionContext,
) -> None:
    memory_root = context.user_agent_path / "memory"
    builder.register(MemorySearchTool(memory_root), source="agent_local")
    builder.register(MemoryGetTool(memory_root), source="agent_local")

