"""Network tools for Quenda."""

from quenda.tools.network.http import (
    HTTPConfig,
    HTTPRequestTool,
)
from quenda.tools.network.fetching import (
    WebFetchConfig,
    WebFetchTool,
)

__all__ = [
    "HTTPRequestTool",
    "HTTPConfig",
    "WebFetchTool",
    "WebFetchConfig",
    "get_network_tools",
]


def get_network_tools() -> list:
    """Get framework-level network tools."""
    return [
        HTTPRequestTool(),
        WebFetchTool(),
    ]
