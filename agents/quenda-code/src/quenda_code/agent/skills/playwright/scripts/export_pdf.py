"""
Export web pages as PDF documents.

Supports custom page formats, margins, and waiting for dynamic content.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def export_pdf(
    url: str,
    output: str = "page.pdf",
    wait_for: str | None = None,
    timeout: int = 30,
    format: str = "A4",
    margin: dict[str, str] | None = None,
    landscape: bool = False,
    print_background: bool = True,
    headless: bool = True,
    use_system_chrome: bool = False,
    viewport: dict[str, int] | None = None,
    user_agent: str | None = None,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Export a web page as PDF.

    Args:
        url: URL to export
        output: Output file path (.pdf)
        wait_for: CSS selector to wait for before export
        timeout: Timeout in seconds
        format: Page format (A4, Letter, Legal, etc.)
        margin: Page margins, e.g., {"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
        landscape: Use landscape orientation
        print_background: Include background colors and images
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
    margin = margin or {
        "top": "1cm",
        "bottom": "1cm",
        "left": "1cm",
        "right": "1cm",
    }

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
            page.set_default_timeout(timeout * 1000)

            # Navigate to URL
            page.goto(url, wait_until="networkidle")

            # Wait for specific element if provided
            if wait_for:
                page.wait_for_selector(wait_for, timeout=timeout * 1000)

            # Export to PDF
            output_path = Path(output)
            page.pdf(
                path=str(output_path),
                format=format,
                landscape=landscape,
                margin=margin,
                print_background=print_background,
            )

            final_url = page.url
            browser.close()

            # Get file size
            file_size = output_path.stat().st_size if output_path.exists() else 0

            return {
                "path": str(output_path.absolute()),
                "url": final_url,
                "format": format,
                "landscape": landscape,
                "size_bytes": file_size,
                "size_human": _format_size(file_size),
            }

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "path": None,
        }


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export web page as PDF")
    parser.add_argument("url", help="URL to export")
    parser.add_argument("-o", "--output", default="page.pdf", help="Output file")
    parser.add_argument("--format", default="A4", help="Page format (A4, Letter, etc.)")
    parser.add_argument("--landscape", action="store_true", help="Landscape orientation")
    parser.add_argument("--wait-for", help="CSS selector to wait for")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--system-chrome", action="store_true", help="Use system Chrome")

    args = parser.parse_args()

    result = export_pdf(
        url=args.url,
        output=args.output,
        format=args.format,
        landscape=args.landscape,
        wait_for=args.wait_for,
        timeout=args.timeout,
        headless=not args.no_headless,
        use_system_chrome=args.system_chrome,
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"PDF saved to: {result['path']}")
    print(f"Format: {result['format']}")
    print(f"Size: {result['size_human']}")
