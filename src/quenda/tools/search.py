"""Runtime tool for discovering schemas that are not sent by default."""

from __future__ import annotations

import re
from collections.abc import Sequence

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class SearchToolsTool:
    """Search deferred tools by name and description, activating matches."""

    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools = list(tools)

    @property
    def name(self) -> str:
        return "search_tools"

    @property
    def description(self) -> str:
        return (
            "Find additional tools by capability. Use when the required tool "
            "is not currently available; matching schemas load on the next step."
        )

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Capability to find, such as 'HTTP request'.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: object) -> ToolResult:
        query = kwargs.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: query must be a non-empty string",
                is_error=True,
            )
        requested_limit = kwargs.get("max_results", 5)
        limit = requested_limit if isinstance(requested_limit, int) else 5
        limit = max(1, min(limit, 10))
        stop_words = {"a", "an", "and", "for", "of", "the", "to", "tool", "use"}
        terms = {
            term for term in re.findall(r"[a-z0-9_]+", query.lower())
            if term not in stop_words
        }

        ranked: list[tuple[int, str, Tool]] = []
        for tool in self._tools:
            haystack = f"{tool.name} {tool.description}".lower()
            score = sum(term in haystack for term in terms)
            if score:
                ranked.append((score, tool.name, tool))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        matches = [tool for _, _, tool in ranked[:limit]]

        if not matches:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"No deferred tools matched: {query}",
            )

        names = [tool.name for tool in matches]
        lines = ["Loaded tool schemas:"]
        lines.extend(f"- {tool.name}: {tool.description}" for tool in matches)
        return ToolResult(
            call_id="",
            name=self.name,
            content="\n".join(lines),
            result_summary=f"tool_activation:{','.join(names)}",
        )
