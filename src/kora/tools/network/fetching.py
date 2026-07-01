"""
web_fetch tool - Fetch and extract content from web pages.

Converts HTML to readable text and extracts main content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


@dataclass
class WebFetchConfig:
    """Configuration for web_fetch tool."""

    default_timeout: int = 30
    max_timeout: int = 60
    max_content_chars: int = 50000
    user_agent: str = "Kora-Agent/1.0"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text if needed."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]", True
    return text, False


def _extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class WebFetchTool(Tool):
    """Fetch content from a web page URL."""

    def __init__(
        self,
        config: WebFetchConfig | None = None,
    ) -> None:
        self.config = config or WebFetchConfig()

    @property
    @override
    def name(self) -> str:
        return "web_fetch"

    @property
    @override
    def description(self) -> str:
        return "Fetch content from a web page URL. Returns the page content as text."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (must be valid HTTP/HTTPS).",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (max {self.config.max_timeout}).",
                    "default": self.config.default_timeout,
                },
            },
            "required": ["url"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        url = kwargs.get("url", "")
        timeout = kwargs.get("timeout", self.config.default_timeout)

        if not isinstance(url, str):
            return ToolResult("", self.name, "Error: url must be a string", is_error=True)

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )

        try:
            import httpx
        except ImportError:
            return ToolResult("", self.name, "Error: httpx is required. Install with: pip install httpx", is_error=True)

        try:
            response = httpx.get(
                url,
                timeout=timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": self.config.user_agent},
            )
            response.raise_for_status()

            # Extract text from HTML
            content = _extract_text(response.text)

            # Truncate if needed
            content, truncated = _truncate(content, self.config.max_content_chars)

            result = f"URL: {url}\n\n{content}"
            if truncated:
                result += "\n\n[content truncated]"

            return ToolResult("", self.name, result)

        except Exception as e:
            return ToolResult("", self.name, f"Error: {type(e).__name__}: {e}", is_error=True)
