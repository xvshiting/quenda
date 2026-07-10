"""
Fetch JavaScript-rendered content from web pages.

Use this when web_fetch returns incomplete content because the page
requires JavaScript execution to render its content.
"""

from __future__ import annotations

import re
import sys
from typing import Any


def fetch_js(
    url: str,
    wait_for: str | None = None,
    timeout: int = 30,
    selectors: dict[str, str] | None = None,
    headless: bool = True,
    use_system_chrome: bool = False,
    viewport: dict[str, int] | None = None,
    user_agent: str | None = None,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Fetch content from a JavaScript-rendered page.

    Args:
        url: URL to fetch
        wait_for: CSS selector to wait for before extracting content
        timeout: Timeout in seconds
        selectors: Dict of {name: css_selector} to extract specific elements
        headless: Run browser in headless mode (no visible window)
        use_system_chrome: Use installed Chrome instead of bundled Chromium
        viewport: Browser viewport size, e.g., {"width": 1280, "height": 720}
        user_agent: Custom user agent string
        cookies: List of cookies to set before navigation

    Returns:
        Dict with 'content', 'title', 'url', and optionally 'extracted' fields
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "error": "playwright is required. Install with: pip install playwright && playwright install chromium",
            "content": None,
        }

    viewport = viewport or {"width": 1280, "height": 720}

    try:
        with sync_playwright() as p:
            # Launch browser
            launch_options = {"headless": headless}
            if use_system_chrome:
                launch_options["channel"] = "chrome"

            browser = p.chromium.launch(**launch_options)
            context = browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
            )

            # Set cookies if provided
            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            page.set_default_timeout(timeout * 1000)

            # Navigate to URL
            page.goto(url, wait_until="networkidle")

            # Wait for specific element if provided
            if wait_for:
                page.wait_for_selector(wait_for, timeout=timeout * 1000)

            # Extract content
            title = page.title()
            final_url = page.url

            # Get full page content
            content = page.content()

            # Extract text content (cleaner than raw HTML)
            text_content = page.evaluate("""() => {
                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(s => s.remove());

                // Get text content
                return document.body.innerText;
            }""")

            # Clean up text
            text_content = _normalize_text(text_content)

            result = {
                "title": title,
                "url": final_url,
                "content": text_content,
                "html_length": len(content),
            }

            # Extract specific selectors if provided
            if selectors:
                extracted = {}
                for name, selector in selectors.items():
                    elements = page.query_selector_all(selector)
                    if elements:
                        if len(elements) == 1:
                            extracted[name] = elements[0].inner_text()
                        else:
                            extracted[name] = [el.inner_text() for el in elements]
                result["extracted"] = extracted

            browser.close()
            return result

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "content": None,
        }


def _normalize_text(text: str) -> str:
    """Normalize whitespace while preserving paragraph breaks."""
    # Remove excessive whitespace
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


if __name__ == "__main__":
    # CLI usage
    import argparse

    parser = argparse.ArgumentParser(description="Fetch JavaScript-rendered content")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--wait-for", help="CSS selector to wait for")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--system-chrome", action="store_true", help="Use system Chrome")

    args = parser.parse_args()

    result = fetch_js(
        url=args.url,
        wait_for=args.wait_for,
        timeout=args.timeout,
        headless=not args.no_headless,
        use_system_chrome=args.system_chrome,
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"\n{result['content']}")
