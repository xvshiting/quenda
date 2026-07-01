"""
Security validation utilities for Kora tools.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from quenda.tools.security.patterns import (
    NETWORK_ALLOWED_SCHEMES,
    NETWORK_BLOCKED_DOMAINS,
    NETWORK_BLOCKED_HEADERS,
    NETWORK_BLOCKED_IP_RANGES,
    SHELL_BLOCKED_COMMANDS,
    SHELL_BLOCKED_ENV_VARS,
)


def validate_shell_command(command: str) -> str | None:
    """
    Validate a shell command against blocked patterns.

    Args:
        command: The shell command to validate.

    Returns:
        Error message if blocked, None if allowed.
    """
    for pattern in SHELL_BLOCKED_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Command blocked by security policy"
    return None


def validate_shell_env(env: dict[str, str]) -> str | None:
    """
    Validate environment variables for shell execution.

    Args:
        env: Environment variables to validate.

    Returns:
        Error message if blocked variable found, None if all allowed.
    """
    for key in env:
        if key in SHELL_BLOCKED_ENV_VARS:
            return f"Environment variable '{key}' is not allowed"
    return None


def validate_workspace_path(workspace: Path, path: str) -> tuple[Path, str | None]:
    """
    Validate that a path is within the workspace boundary.

    Args:
        workspace: The workspace root directory.
        path: The path to validate.

    Returns:
        Tuple of (resolved_path, error_message).
        error_message is None if path is valid.
    """
    try:
        resolved = (workspace / path).resolve()

        # Security check: ensure path is within workspace
        if not str(resolved).startswith(str(workspace)):
            return resolved, "Access denied - path outside workspace"

        return resolved, None
    except Exception as e:
        return Path(path), f"Invalid path: {e}"


def validate_url(url: str) -> str | None:
    """
    Validate a URL for SSRF protection.

    Checks:
    - Scheme is allowed (http/https)
    - Domain is not in blocked list
    - Resolved IP is not in blocked range

    Args:
        url: The URL to validate.

    Returns:
        Error message if blocked, None if allowed.
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in NETWORK_ALLOWED_SCHEMES:
            return f"URL scheme must be one of {NETWORK_ALLOWED_SCHEMES}"

        hostname = parsed.hostname
        if not hostname:
            return "URL must have a hostname"

        # Check blocked domains
        hostname_lower = hostname.lower()
        for blocked in NETWORK_BLOCKED_DOMAINS:
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
                if _ip_in_blocked_range(ip):
                    return "Access to private/internal networks is blocked"
        except socket.gaierror:
            # DNS resolution failed, let the request fail naturally
            pass

        return None

    except Exception as e:
        return f"Invalid URL: {e}"


def _ip_in_blocked_range(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a blocked range."""
    for cidr in NETWORK_BLOCKED_IP_RANGES:
        try:
            if ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def validate_headers(headers: dict[str, str]) -> str | None:
    """
    Validate HTTP headers for security.

    Args:
        headers: Headers to validate.

    Returns:
        Error message if blocked header found, None if all allowed.
    """
    for key in headers:
        if key in NETWORK_BLOCKED_HEADERS:
            return f"Header '{key}' is not allowed"
    return None


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """
    Remove blocked headers from a headers dict.

    Args:
        headers: Headers to sanitize.

    Returns:
        Sanitized headers dict.
    """
    return {
        k: v
        for k, v in headers.items()
        if k not in NETWORK_BLOCKED_HEADERS
    }


def is_ip_private(ip_str: str) -> bool:
    """
    Check if an IP address string is private/internal.

    Args:
        ip_str: IP address string.

    Returns:
        True if the IP is private/internal.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return _ip_in_blocked_range(ip)
    except ValueError:
        return False
