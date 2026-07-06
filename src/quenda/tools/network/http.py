"""
http_request tool - Make HTTP requests.

Supports GET, POST, PUT, DELETE, PATCH methods with SSRF protection.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from typing import Any, override
from urllib.parse import urljoin, urlparse

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


@dataclass
class HTTPConfig:
    """Configuration for HTTP tool."""

    default_timeout: int = 30
    max_timeout: int = 60
    max_output_chars: int = 100000
    max_redirects: int = 5
    max_download_bytes: int = 2_000_000
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


# SSRF protection
BLOCKED_IP_RANGES: list[str] = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",  # AWS metadata
    "0.0.0.0/8",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

BLOCKED_DOMAINS: list[str] = [
    "localhost",
    "localhost.localdomain",
    "local",
    "internal",
    "*.internal",
    "*.local",
    "metadata.google.internal",
    "metadata",
    "kubernetes",
    "kubernetes.default",
]

BLOCKED_HEADERS: list[str] = [
    "Authorization",
    "Cookie",
    "Proxy-Authorization",
    "Set-Cookie",
    "X-Forwarded-For",
    "X-Real-IP",
]


def _validate_url(url: str) -> str | None:
    """Validate URL for SSRF protection. Returns error message or None."""
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ["http", "https"]:
            return f"URL scheme must be http or https"

        hostname = parsed.hostname
        if not hostname:
            return "URL must have a hostname"

        # Check blocked domains
        hostname_lower = hostname.lower()
        for blocked in BLOCKED_DOMAINS:
            if blocked.startswith("*."):
                if hostname_lower.endswith(blocked[2:].lower()):
                    return "Access to internal domains is blocked"
            elif hostname_lower == blocked.lower():
                return "Access to internal domains is blocked"

        # Resolve and check IP
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, addr in addr_info:
                ip = ipaddress.ip_address(addr[0])
                for cidr in BLOCKED_IP_RANGES:
                    try:
                        if ip in ipaddress.ip_network(cidr, strict=False):
                            return "Access to private/internal networks is blocked"
                    except ValueError:
                        continue
        except socket.gaierror:
            pass  # DNS resolution failed, let request fail naturally

        return None

    except Exception as e:
        return f"Invalid URL: {e}"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text if needed."""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]", True
    return text, False


def _supports_brotli() -> bool:
    """Return whether httpx can decode Brotli responses in this environment."""
    return (
        importlib.util.find_spec("brotli") is not None
        or importlib.util.find_spec("brotlicffi") is not None
    )


def _default_headers(url: str, user_agent: str) -> dict[str, str]:
    """Build safe default headers for API and document requests."""
    encodings = ["gzip", "deflate"]
    if _supports_brotli():
        encodings.append("br")

    return {
        "User-Agent": user_agent,
        "Accept": "application/json,text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": ", ".join(encodings),
    }


def _merge_headers(url: str, headers: object, user_agent: str) -> dict[str, str] | str:
    """Merge caller headers with safe defaults, or return an error string."""
    merged = _default_headers(url, user_agent)

    if headers is None:
        return merged

    if not isinstance(headers, dict):
        return "headers must be an object"

    blocked = {header.lower() for header in BLOCKED_HEADERS}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return "headers must map strings to strings"
        if key.lower() in blocked:
            return f"Header '{key}' is not allowed"
        merged[key] = value

    return merged


def _content_type(response: object) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("content-type", "")).split(";", 1)[0].strip().lower()


def _format_body(response: object, max_chars: int) -> tuple[str, bool]:
    """Format response body while preserving http_request's raw-ish character."""
    content_type = _content_type(response)

    try:
        text = getattr(response, "text", "")
    except Exception:
        content = getattr(response, "content", b"")
        return f"<binary data: {len(content)} bytes>", False

    if "json" in content_type:
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return _truncate(text, max_chars)

    if content_type and not (
        content_type.startswith("text/")
        or content_type in {"application/xml", "application/xhtml+xml", "application/json"}
        or content_type.endswith("+json")
        or content_type.endswith("+xml")
    ):
        content = getattr(response, "content", b"")
        return f"<binary data: {len(content)} bytes; content-type: {content_type}>", False

    return _truncate(text, max_chars)


class HTTPRequestTool(Tool):
    """Make HTTP requests with SSRF protection."""

    def __init__(
        self,
        config: HTTPConfig | None = None,
    ) -> None:
        self.config = config or HTTPConfig()
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create httpx client."""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.Client(
                    timeout=self.config.max_timeout,
                    follow_redirects=False,
                )
            except ImportError:
                raise ImportError("httpx is required. Install with: pip install httpx")
        return self._client

    @property
    @override
    def name(self) -> str:
        return "http_request"

    @property
    @override
    def description(self) -> str:
        return "Make an HTTP request to a specified URL. Supports GET, POST, PUT, DELETE, PATCH."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to request (must be valid HTTP/HTTPS).",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                },
                "headers": {
                    "type": "object",
                    "description": "Request headers.",
                    "additionalProperties": {"type": "string"},
                },
                "body": {
                    "type": "string",
                    "description": "Request body (for POST/PUT/PATCH).",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (max {self.config.max_timeout}).",
                    "default": self.config.default_timeout,
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Maximum response body characters to return (max {self.config.max_output_chars}).",
                    "default": self.config.max_output_chars,
                },
            },
            "required": ["url"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        url = kwargs.get("url", "")
        method = kwargs.get("method", "GET")
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        timeout = kwargs.get("timeout", self.config.default_timeout)
        max_chars = kwargs.get("max_chars", self.config.max_output_chars)

        if not isinstance(url, str):
            return ToolResult("", self.name, "Error: url must be a string", is_error=True)

        # Validate URL for SSRF
        error = _validate_url(url)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        merged_headers = _merge_headers(url, headers, self.config.user_agent)
        if isinstance(merged_headers, str):
            return ToolResult("", self.name, f"Error: {merged_headers}", is_error=True)

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )
        max_chars_int = min(
            int(max_chars) if isinstance(max_chars, (int, float)) else self.config.max_output_chars,
            self.config.max_output_chars,
        )

        try:
            client = self._get_client()
            request_method = method.upper() if isinstance(method, str) else "GET"
            response = client.request(
                method=request_method,
                url=url,
                headers=merged_headers,
                content=body if isinstance(body, str) else None,
                timeout=timeout_seconds,
            )

            # Handle redirects with validation
            redirect_count = 0
            while response.is_redirect and redirect_count < self.config.max_redirects:
                redirect_url = response.headers.get("location")
                if not redirect_url:
                    break

                next_url = urljoin(str(response.url), redirect_url)
                error = _validate_url(next_url)
                if error:
                    return ToolResult("", self.name, f"Error: Redirect blocked - {error}", is_error=True)

                response = client.request(
                    method="GET" if response.status_code in {301, 302, 303} else request_method,
                    url=next_url,
                    headers=_merge_headers(next_url, headers, self.config.user_agent),
                    timeout=timeout_seconds,
                )
                redirect_count += 1

            if response.is_redirect:
                return ToolResult("", self.name, "Error: Too many redirects", is_error=True)

            content = getattr(response, "content", b"")
            if len(content) > self.config.max_download_bytes:
                return ToolResult(
                    "",
                    self.name,
                    f"Error: Response too large ({len(content)} bytes, max {self.config.max_download_bytes})",
                    is_error=True,
                )

            # Format response
            parts = [
                f"HTTP {response.status_code} {response.reason_phrase}",
                f"URL: {response.url}",
                f"Content-Type: {_content_type(response) or 'unknown'}",
            ]

            # Response body
            content, truncated = _format_body(response, max_chars_int)
            parts.append(f"\n[body]\n{content}")

            if truncated:
                parts.append("\n[response truncated]")

            return ToolResult(
                "",
                self.name,
                "\n".join(parts),
                is_error=response.status_code >= 400,
            )

        except ImportError as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult("", self.name, f"Error: {type(e).__name__}: {e}", is_error=True)
