"""
web_search tool - Search the web.

Uses DuckDuckGo Instant Answer API for basic search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import override
from urllib.parse import urlencode

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


@dataclass
class WebSearchConfig:
    """Configuration for web_search tool."""

    default_timeout: int = 30
    max_results: int = 10
    user_agent: str = "Kora-Agent/1.0"


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo."""

    def __init__(
        self,
        config: WebSearchConfig | None = None,
    ) -> None:
        self.config = config or WebSearchConfig()

    @property
    @override
    def name(self) -> str:
        return "web_search"

    @property
    @override
    def description(self) -> str:
        return "Search the web using a search query. Returns relevant results with titles and URLs."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results.",
                    "default": 10,
                },
            },
            "required": ["query"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", self.config.max_results)

        if not isinstance(query, str):
            return ToolResult("", self.name, "Error: query must be a string", is_error=True)

        max_results_int = min(int(max_results) if isinstance(max_results, (int, float)) else 10, 20)

        try:
            import httpx
        except ImportError:
            return ToolResult("", self.name, "Error: httpx is required. Install with: pip install httpx", is_error=True)

        try:
            # DuckDuckGo Instant Answer API
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            }

            url = f"https://api.duckduckgo.com/?{urlencode(params)}"

            response = httpx.get(url, timeout=self.config.default_timeout)
            response.raise_for_status()

            data = response.json()

            # Format results
            results = []

            # Instant answer
            if data.get("AbstractText"):
                results.append(f"📌 Summary: {data['AbstractText']}")
                if data.get("AbstractURL"):
                    results.append(f"   Source: {data['AbstractURL']}")

            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_results_int]:
                if isinstance(topic, dict):
                    if "Text" in topic and "FirstURL" in topic:
                        results.append(f"📄 {topic['Text']}")
                        results.append(f"   URL: {topic['FirstURL']}")

            if not results:
                content = f"No results found for: {query}"
            else:
                content = f"Search results for '{query}':\n\n" + "\n\n".join(results)

            return ToolResult("", self.name, content)

        except Exception as e:
            return ToolResult("", self.name, f"Error: Search failed: {e}", is_error=True)
