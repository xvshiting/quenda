"""
Capture web page screenshots.

Supports full-page, viewport, and element-specific screenshots.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def screenshot(
    url: str,
    output: str = "screenshot.png",
    full_page: bool = True,
    selector: str | None = None,
    wait_for: str | None = None,
    timeout: int = 30,
    delay: float = 0,
    scroll_to_load: bool = True,
    headless: bool = True,
    use_system_chrome: bool = False,
    viewport: dict[str, int] | None = None,
    user_agent: str | None = None,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Take a screenshot of a web page.

    Args:
        url: URL to screenshot
        output: Output file path (supports .png, .jpg, .jpeg)
        full_page: Capture full page (scrolls if needed)
        selector: Capture only this element (overrides full_page)
        wait_for: CSS selector to wait for before screenshot
        timeout: Timeout in seconds
        delay: Additional delay in seconds before taking screenshot
        scroll_to_load: Scroll page to trigger lazy-loaded content (for full_page)
        headless: Run browser in headless mode
        use_system_chrome: Use installed Chrome instead of bundled Chromium
        viewport: Browser viewport size
        user_agent: Custom user agent string
        cookies: List of cookies to set before navigation

    Returns:
        Dict with 'path', 'url', 'size' fields
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "error": "playwright is required. Install with: pip install playwright && playwright install chromium",
            "path": None,
        }

    viewport = viewport or {"width": 1280, "height": 720}
    timeout_ms = timeout * 1000

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

            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            page.set_default_timeout(timeout_ms)

            # Navigate to URL with domcontentloaded for faster initial load
            page.goto(url, wait_until="domcontentloaded")

            # Wait for network to settle
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10000))
            except Exception:
                # Continue even if networkidle times out
                pass

            # Wait for specific element if provided
            if wait_for:
                page.wait_for_selector(wait_for, timeout=timeout_ms)

            # For full page screenshots, scroll to trigger lazy-loaded content
            if full_page and scroll_to_load and not selector:
                _scroll_to_load_content(page)

            # Additional delay if specified
            if delay > 0:
                import time
                time.sleep(delay)

            # Take screenshot
            output_path = Path(output)

            if selector:
                # Screenshot specific element
                element = page.wait_for_selector(selector, timeout=timeout_ms)
                element.screenshot(path=str(output_path))
            else:
                # Screenshot page
                page.screenshot(path=str(output_path), full_page=full_page)

            final_url = page.url
            page_height = page.evaluate("document.body.scrollHeight")
            browser.close()

            # Get file size
            file_size = output_path.stat().st_size if output_path.exists() else 0

            return {
                "path": str(output_path.absolute()),
                "url": final_url,
                "page_height": page_height,
                "viewport_height": viewport.get("height", 720),
                "full_page": full_page,
                "size_bytes": file_size,
                "size_human": _format_size(file_size),
            }

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "path": None,
        }


def _scroll_to_load_content(page) -> None:
    """
    Scroll through the page to trigger lazy-loaded content.

    This is important for full-page screenshots of modern SPAs
    that load images/content on scroll.
    """
    try:
        # Get the total page height
        total_height = page.evaluate("document.body.scrollHeight")
        viewport_height = page.evaluate("window.innerHeight")

        if total_height <= viewport_height:
            # No scrolling needed
            return

        # Scroll down in chunks
        scroll_step = viewport_height // 2
        current_position = 0

        while current_position < total_height:
            # Scroll down
            page.evaluate(f"window.scrollTo(0, {current_position})")

            # Wait a bit for content to load
            page.wait_for_timeout(100)

            # Update total height (may have changed due to lazy load)
            total_height = page.evaluate("document.body.scrollHeight")

            current_position += scroll_step

        # Scroll back to top before screenshot
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(100)

    except Exception:
        # If scrolling fails, continue anyway
        pass


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Take web page screenshot")
    parser.add_argument("url", help="URL to screenshot")
    parser.add_argument("-o", "--output", default="screenshot.png", help="Output file")
    parser.add_argument("--viewport-only", action="store_true", help="Capture viewport only (not full page)")
    parser.add_argument("--selector", help="Capture only this element")
    parser.add_argument("--wait-for", help="CSS selector to wait for")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--delay", type=float, default=0, help="Additional delay before screenshot")
    parser.add_argument("--no-scroll", action="store_true", help="Disable auto-scroll for lazy content")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--system-chrome", action="store_true", help="Use system Chrome")

    args = parser.parse_args()

    result = screenshot(
        url=args.url,
        output=args.output,
        full_page=not args.viewport_only,
        selector=args.selector,
        wait_for=args.wait_for,
        timeout=args.timeout,
        delay=args.delay,
        scroll_to_load=not args.no_scroll,
        headless=not args.no_headless,
        use_system_chrome=args.system_chrome,
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Screenshot saved to: {result['path']}")
    print(f"Full page: {result['full_page']}")
    print(f"Page height: {result['page_height']}px")
    print(f"Size: {result['size_human']}")
