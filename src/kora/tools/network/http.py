"""
http_request tool - Make HTTP requests.

Supports GET, POST, PUT, DELETE, PATCH methods with SSRF protection.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any, override
from urllib.parse import urlparse

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


@dataclass
class HTTPConfig:
    """Configuration for HTTP tool."""

    default_timeout: int = 30
    max_timeout: int = 60
    max_output_chars: int = 100000
    max_redirects: int = 5
    user_agent: str = "Kora-Agent/1.0"


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
    "Set-Cookie",
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

        if not isinstance(url, str):
            return ToolResult("", self.name, "Error: url must be a string", is_error=True)

        # Validate URL for SSRF
        error = _validate_url(url)
        if error:
            return ToolResult("", self.name, f"Error: {error}", is_error=True)

        # Validate headers
        if isinstance(headers, dict):
            for key in headers:
                if key in BLOCKED_HEADERS:
                    return ToolResult("", self.name, f"Error: Header '{key}' is not allowed", is_error=True)
            # Add user agent
            if "User-Agent" not in headers:
                headers = {**headers, "User-Agent": self.config.user_agent}
        else:
            headers = {"User-Agent": self.config.user_agent}

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )

        try:
            client = self._get_client()
            response = client.request(
                method=method.upper() if isinstance(method, str) else "GET",
                url=url,
                headers=headers,
                content=body if isinstance(body, str) else None,
                timeout=timeout_seconds,
            )

            # Handle redirects with validation
            redirect_count = 0
            while response.is_redirect and redirect_count < self.config.max_redirects:
                redirect_url = response.headers.get("location")
                if not redirect_url:
                    break

                error = _validate_url(redirect_url)
                if error:
                    return ToolResult("", self.name, f"Error: Redirect blocked - {error}", is_error=True)

                response = client.request(
                    method=method.upper() if isinstance(method, str) else "GET",
                    url=redirect_url,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                redirect_count += 1

            # Format response
            parts = [f"HTTP {response.status_code} {response.reason_phrase}"]

            # Response body
            try:
                content = response.text
            except Exception:
                content = f"<binary data: {len(response.content)} bytes>"

            content, truncated = _truncate(content, self.config.max_output_chars)
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
