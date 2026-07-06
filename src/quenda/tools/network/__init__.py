"""
Network tools for Quenda.

- http_request: Make HTTP requests with SSRF protection
- web_fetch: Fetch content from web pages
"""

from quenda.tools.network.http import (
    HTTPConfig,
    HTTPRequestTool,
)
from quenda.tools.network.fetching import (
    WebFetchConfig,
    WebFetchTool,
)
from quenda.tools.network.searching import (
    WebSearchConfig,
    WebSearchTool,
)

__all__ = [
    "HTTPRequestTool",
    "HTTPConfig",
    "WebFetchTool",
    "WebFetchConfig",
    "WebSearchTool",
    "WebSearchConfig",
]


def get_network_tools() -> list:
    """Get all network tools."""
    return [
        HTTPRequestTool(),
        WebFetchTool(),
    ]
