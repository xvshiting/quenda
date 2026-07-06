"""
web_fetch tool - Fetch and extract content from web pages.

Converts HTML to readable text and extracts main content.
"""

from __future__ import annotations

import json
import re
import importlib.util
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import override
from urllib.parse import urljoin

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.tools.network.http import _validate_url


@dataclass
class WebFetchConfig:
    """Configuration for web_fetch tool."""

    default_timeout: int = 30
    max_timeout: int = 60
    max_content_chars: int = 50000
    max_redirects: int = 5
    max_download_bytes: int = 2_000_000
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


BLOCK_TAGS = {
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}

IGNORED_TAGS = {
    "button",
    "canvas",
    "form",
    "iframe",
    "input",
    "nav",
    "noscript",
    "script",
    "select",
    "style",
    "svg",
    "textarea",
}

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _ReadableHTMLParser(HTMLParser):
    """Small stdlib-only HTML text extractor."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self._in_title = False
        self._ignored_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        if tag == "title":
            self._in_title = True
            return

        if tag == "meta":
            attr_map = {name.lower(): value or "" for name, value in attrs}
            if attr_map.get("name", "").lower() == "description":
                self.meta_description = attr_map.get("content", "").strip()
            return

        if tag in IGNORED_TAGS:
            if tag not in VOID_TAGS:
                self._ignored_depth += 1
            return

        if self._ignored_depth == 0 and tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == "title":
            self._in_title = False
            return

        if tag in IGNORED_TAGS and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return

        if self._ignored_depth == 0 and tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return

        if self._ignored_depth == 0:
            self._chunks.append(text)

    def text(self) -> str:
        return _normalize_text(" ".join(self._chunks))


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text if needed."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]", True
    return text, False


def _normalize_text(text: str) -> str:
    """Normalize whitespace while preserving paragraph-ish breaks."""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text(html: str) -> tuple[str, str, str]:
    """Extract title, description, and readable text from HTML."""
    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()

    return (
        _normalize_text(parser.title),
        _normalize_text(parser.meta_description),
        parser.text(),
    )


def _build_headers(url: str) -> dict[str, str]:
    """Build headers that look like a normal document navigation."""
    encodings = ["gzip", "deflate"]
    if _supports_brotli():
        encodings.append("br")

    return {
        "User-Agent": WebFetchConfig().user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,text/plain;q=0.7,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": ", ".join(encodings),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": _origin(url),
    }


def _supports_brotli() -> bool:
    """Return whether httpx can decode Brotli responses in this environment."""
    return (
        importlib.util.find_spec("brotli") is not None
        or importlib.util.find_spec("brotlicffi") is not None
    )


def _origin(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/"


def _content_type(response: object) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("content-type", "")).split(";", 1)[0].strip().lower()


def _format_response_content(response: object, max_chars: int) -> tuple[str, bool]:
    content_type = _content_type(response)
    text = getattr(response, "text", "")

    if "json" in content_type:
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return _truncate(text.strip(), max_chars)

    if content_type.startswith("text/") and content_type not in {"text/html", "application/xhtml+xml"}:
        return _truncate(_normalize_text(text), max_chars)

    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        content = getattr(response, "content", b"")
        return (
            f"Unsupported content type: {content_type or 'unknown'} ({len(content)} bytes)",
            False,
        )

    title, description, body = _extract_text(text)
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if description:
        parts.append(f"Description: {description}")
    if body:
        parts.append(body)

    return _truncate("\n\n".join(parts).strip(), max_chars)


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
                "max_chars": {
                    "type": "integer",
                    "description": f"Maximum characters to return (max {self.config.max_content_chars}).",
                    "default": self.config.max_content_chars,
                },
            },
            "required": ["url"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        url = kwargs.get("url", "")
        timeout = kwargs.get("timeout", self.config.default_timeout)
        max_chars = kwargs.get("max_chars", self.config.max_content_chars)

        if not isinstance(url, str):
            return ToolResult("", self.name, "Error: url must be a string", is_error=True)

        error = _validate_url(url)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )
        max_chars_int = min(
            int(max_chars) if isinstance(max_chars, (int, float)) else self.config.max_content_chars,
            self.config.max_content_chars,
        )

        try:
            import httpx
        except ImportError:
            return ToolResult("", self.name, "Error: httpx is required. Install with: pip install httpx", is_error=True)

        try:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
                response = client.get(url, headers={**_build_headers(url), "User-Agent": self.config.user_agent})

                redirect_count = 0
                while getattr(response, "is_redirect", False) and redirect_count < self.config.max_redirects:
                    redirect_url = response.headers.get("location")
                    if not redirect_url:
                        break

                    next_url = urljoin(str(response.url), redirect_url)
                    error = _validate_url(next_url)
                    if error:
                        return ToolResult("", self.name, f"Error: Redirect blocked - {error}", is_error=True)

                    response = client.get(
                        next_url,
                        headers={**_build_headers(next_url), "User-Agent": self.config.user_agent},
                    )
                    redirect_count += 1

                if getattr(response, "is_redirect", False):
                    return ToolResult("", self.name, "Error: Too many redirects", is_error=True)

                content = getattr(response, "content", b"")
                if len(content) > self.config.max_download_bytes:
                    return ToolResult(
                        "",
                        self.name,
                        f"Error: Response too large ({len(content)} bytes, max {self.config.max_download_bytes})",
                        is_error=True,
                    )

            status_code = getattr(response, "status_code", 0)
            if status_code >= 400:
                excerpt, _ = _format_response_content(response, 1000)
                return ToolResult(
                    "",
                    self.name,
                    (
                        f"Error: HTTP {status_code} while fetching {response.url}\n"
                        f"Content-Type: {_content_type(response) or 'unknown'}\n\n"
                        f"{excerpt}"
                    ).strip(),
                    is_error=True,
                )

            content, truncated = _format_response_content(response, max_chars_int)

            result = (
                f"URL: {response.url}\n"
                f"Status: HTTP {response.status_code}\n"
                f"Content-Type: {_content_type(response) or 'unknown'}\n\n"
                f"{content}"
            ).strip()
            if truncated:
                result += "\n\n[content truncated]"

            return ToolResult("", self.name, result)

        except Exception as e:
            return ToolResult("", self.name, f"Error: {type(e).__name__}: {e}", is_error=True)
