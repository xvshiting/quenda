"""
Tests for network tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from quenda.tools.network import HTTPRequestTool, WebFetchTool


@dataclass
class FakeResponse:
    text: str
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=lambda: {"content-type": "text/html"})
    url: str = "https://example.com"
    is_redirect: bool = False
    reason_phrase: str = "OK"

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")


class FakeClient:
    def __init__(self, responses: list[FakeResponse], calls: list[dict[str, Any]]) -> None:
        self._responses = responses
        self._calls = calls

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        self._calls.append({"url": url, "headers": headers})
        return self._responses.pop(0)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        content: str | None = None,
        timeout: int | None = None,
    ) -> FakeResponse:
        self._calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "content": content,
                "timeout": timeout,
            }
        )
        return self._responses.pop(0)


def install_fake_httpx(monkeypatch, responses: list[FakeResponse]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class ClientFactory:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.client = FakeClient(responses, calls)

        def __enter__(self) -> FakeClient:
            return self.client

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            return self.client.get(url, headers)

        def request(
            self,
            method: str,
            url: str,
            headers: dict[str, str],
            content: str | None = None,
            timeout: int | None = None,
        ) -> FakeResponse:
            return self.client.request(method, url, headers, content, timeout)

    monkeypatch.setitem(__import__("sys").modules, "httpx", SimpleNamespace(Client=ClientFactory))
    return calls


def test_web_fetch_uses_browser_like_headers(monkeypatch) -> None:
    calls = install_fake_httpx(
        monkeypatch,
        [FakeResponse("<html><body><main>Hello world</main></body></html>")],
    )

    result = WebFetchTool().execute(url="https://example.com")

    assert not result.is_error
    assert "Hello world" in result.content
    assert "Mozilla/5.0" in calls[0]["headers"]["User-Agent"]
    assert "text/html" in calls[0]["headers"]["Accept"]
    assert "gzip" in calls[0]["headers"]["Accept-Encoding"]
    assert "deflate" in calls[0]["headers"]["Accept-Encoding"]
    assert calls[0]["headers"]["Referer"] == "https://example.com/"


def test_web_fetch_does_not_request_brotli_without_decoder(monkeypatch) -> None:
    from quenda.tools.network import fetching

    monkeypatch.setattr(fetching, "_supports_brotli", lambda: False)
    calls = install_fake_httpx(
        monkeypatch,
        [FakeResponse("<html><body>Hello world</body></html>")],
    )

    result = WebFetchTool().execute(url="https://example.com")

    assert not result.is_error
    assert "br" not in calls[0]["headers"]["Accept-Encoding"].split(", ")


def test_web_fetch_requests_brotli_when_decoder_exists(monkeypatch) -> None:
    from quenda.tools.network import fetching

    monkeypatch.setattr(fetching, "_supports_brotli", lambda: True)
    calls = install_fake_httpx(
        monkeypatch,
        [FakeResponse("<html><body>Hello world</body></html>")],
    )

    result = WebFetchTool().execute(url="https://example.com")

    assert not result.is_error
    assert "br" in calls[0]["headers"]["Accept-Encoding"].split(", ")


def test_web_fetch_extracts_title_description_and_ignores_noise(monkeypatch) -> None:
    html = """
    <html>
      <head>
        <title>Example Title</title>
        <meta name="description" content="Useful summary">
      </head>
      <body>
        <nav>Navigation should disappear</nav>
        <article><h1>Main story</h1><p>Useful article text.</p></article>
        <script>window.noise = true</script>
      </body>
    </html>
    """
    install_fake_httpx(monkeypatch, [FakeResponse(html)])

    result = WebFetchTool().execute(url="https://example.com/article")

    assert not result.is_error
    assert "Title: Example Title" in result.content
    assert "Description: Useful summary" in result.content
    assert "Main story" in result.content
    assert "Useful article text" in result.content
    assert "Navigation should disappear" not in result.content
    assert "window.noise" not in result.content


def test_web_fetch_formats_json(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [FakeResponse('{"name":"quenda","ok":true}', headers={"content-type": "application/json"})],
    )

    result = WebFetchTool().execute(url="https://example.com/data.json")

    assert not result.is_error
    assert '"name": "quenda"' in result.content
    assert '"ok": true' in result.content


def test_web_fetch_validates_redirects(monkeypatch) -> None:
    calls = install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(
                "",
                status_code=302,
                headers={"location": "/next"},
                url="https://example.com/start",
                is_redirect=True,
            ),
            FakeResponse("<p>Redirect target</p>", url="https://example.com/next"),
        ],
    )

    result = WebFetchTool().execute(url="https://example.com/start")

    assert not result.is_error
    assert "Redirect target" in result.content
    assert calls[1]["url"] == "https://example.com/next"


def test_web_fetch_returns_useful_http_error(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [FakeResponse("Access denied", status_code=403, headers={"content-type": "text/plain"})],
    )

    result = WebFetchTool().execute(url="https://example.com/blocked")

    assert result.is_error
    assert "HTTP 403" in result.content
    assert "Content-Type: text/plain" in result.content
    assert "Access denied" in result.content


def test_http_request_uses_safe_default_headers(monkeypatch) -> None:
    calls = install_fake_httpx(
        monkeypatch,
        [FakeResponse("ok", headers={"content-type": "text/plain"})],
    )

    result = HTTPRequestTool().execute(url="https://example.com/api")

    assert not result.is_error
    assert "HTTP 200 OK" in result.content
    assert "Mozilla/5.0" in calls[0]["headers"]["User-Agent"]
    assert "gzip" in calls[0]["headers"]["Accept-Encoding"]
    assert "application/json" in calls[0]["headers"]["Accept"]


def test_http_request_does_not_request_brotli_without_decoder(monkeypatch) -> None:
    from quenda.tools.network import http

    monkeypatch.setattr(http, "_supports_brotli", lambda: False)
    calls = install_fake_httpx(
        monkeypatch,
        [FakeResponse("ok", headers={"content-type": "text/plain"})],
    )

    result = HTTPRequestTool().execute(url="https://example.com/api")

    assert not result.is_error
    assert "br" not in calls[0]["headers"]["Accept-Encoding"].split(", ")


def test_http_request_formats_json(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [FakeResponse('{"name":"quenda","ok":true}', headers={"content-type": "application/json"})],
    )

    result = HTTPRequestTool().execute(url="https://example.com/data")

    assert not result.is_error
    assert "Content-Type: application/json" in result.content
    assert '"name": "quenda"' in result.content
    assert '"ok": true' in result.content


def test_http_request_blocks_sensitive_headers(monkeypatch) -> None:
    install_fake_httpx(monkeypatch, [FakeResponse("ok")])

    result = HTTPRequestTool().execute(
        url="https://example.com/api",
        headers={"authorization": "secret"},
    )

    assert result.is_error
    assert "not allowed" in result.content


def test_http_request_validates_relative_redirects(monkeypatch) -> None:
    calls = install_fake_httpx(
        monkeypatch,
        [
            FakeResponse(
                "",
                status_code=302,
                headers={"location": "/next"},
                url="https://example.com/start",
                is_redirect=True,
            ),
            FakeResponse("redirected", headers={"content-type": "text/plain"}, url="https://example.com/next"),
        ],
    )

    result = HTTPRequestTool().execute(url="https://example.com/start")

    assert not result.is_error
    assert "redirected" in result.content
    assert calls[1]["url"] == "https://example.com/next"


def test_http_request_reports_binary_content(monkeypatch) -> None:
    install_fake_httpx(
        monkeypatch,
        [FakeResponse("binary-ish", headers={"content-type": "image/png"})],
    )

    result = HTTPRequestTool().execute(url="https://example.com/image.png")

    assert not result.is_error
    assert "<binary data:" in result.content
    assert "image/png" in result.content
