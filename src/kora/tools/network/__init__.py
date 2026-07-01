"""
Network tools for Kora.

- http_request: Make HTTP requests with SSRF protection
- web_fetch: Fetch content from web pages
- web_search: Search the web using DuckDuckGo
"""

from kora.tools.network.http import (
    HTTPConfig,
    HTTPRequestTool,
)
from kora.tools.network.fetching import (
    WebFetchConfig,
    WebFetchTool,
)
from kora.tools.network.searching import (
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
        WebSearchTool(),
    ]