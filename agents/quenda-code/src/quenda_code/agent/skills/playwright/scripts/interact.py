"""
Browser interactions for form filling, clicking, and navigation.

Use this for logging into websites, filling forms, and extracting
content after user interactions.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def interact(
    url: str,
    actions: list[dict[str, Any]],
    extract: str | None = None,
    wait_for: str | None = None,
    timeout: int = 30,
    headless: bool = True,
    use_system_chrome: bool = False,
    viewport: dict[str, int] | None = None,
    user_agent: str | None = None,
    cookies: list[dict] | None = None,
    cookies_file: str | None = None,
    slow_mo: int = 0,
) -> dict[str, Any]:
    """
    Perform browser interactions and optionally extract content.

    Args:
        url: Starting URL
        actions: List of actions to perform. Each action is a dict with:
            - type: fill, click, press, wait, select, check, uncheck, hover, goto
            - selector: CSS selector (for most actions)
            - value: Value to fill/select/press
            - key: Key to press (for press action)
        extract: CSS selector to extract text after all actions
        wait_for: CSS selector to wait for before extraction
        timeout: Default timeout in seconds
        headless: Run browser in headless mode
        use_system_chrome: Use installed Chrome instead of bundled Chromium
        viewport: Browser viewport size
        user_agent: Custom user agent string
        cookies: List of cookies to set before navigation
        cookies_file: Path to save/load cookies (JSON file)
        slow_mo: Slow down operations by N milliseconds (for debugging)

    Returns:
        Dict with 'content', 'url', 'title', and optionally 'extracted' fields
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "error": "playwright is required. Install with: pip install playwright && playwright install chromium",
            "content": None,
        }

    viewport = viewport or {"width": 1280, "height": 720}
    timeout_ms = timeout * 1000

    try:
        with sync_playwright() as p:
            # Launch browser
            launch_options = {"headless": headless}
            if use_system_chrome:
                launch_options["channel"] = "chrome"
            if slow_mo:
                launch_options["slow_mo"] = slow_mo

            browser = p.chromium.launch(**launch_options)
            context = browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
            )

            # Load cookies from file if exists
            if cookies_file:
                cookies_path = Path(cookies_file)
                if cookies_path.exists():
                    saved_cookies = json.loads(cookies_path.read_text())
                    context.add_cookies(saved_cookies)

            # Set provided cookies
            if cookies:
                context.add_cookies(cookies)

            page = context.new_page()
            page.set_default_timeout(timeout_ms)

            # Navigate to starting URL
            page.goto(url, wait_until="networkidle")

            # Execute actions
            for action in actions:
                action_type = action.get("type", "")

                if action_type == "fill":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    page.fill(selector, str(value))

                elif action_type == "click":
                    selector = action.get("selector", "")
                    page.click(selector)

                elif action_type == "press":
                    key = action.get("key", "")
                    selector = action.get("selector")
                    if selector:
                        page.press(selector, key)
                    else:
                        page.keyboard.press(key)

                elif action_type == "wait":
                    selector = action.get("selector", "")
                    wait_timeout = action.get("timeout", timeout_ms)
                    page.wait_for_selector(selector, timeout=wait_timeout)

                elif action_type == "wait_navigation":
                    page.wait_for_load_state("networkidle")

                elif action_type == "select":
                    selector = action.get("selector", "")
                    value = action.get("value", "")
                    page.select_option(selector, value)

                elif action_type == "check":
                    selector = action.get("selector", "")
                    page.check(selector)

                elif action_type == "uncheck":
                    selector = action.get("selector", "")
                    page.uncheck(selector)

                elif action_type == "hover":
                    selector = action.get("selector", "")
                    page.hover(selector)

                elif action_type == "goto":
                    goto_url = action.get("url", "")
                    page.goto(goto_url, wait_until="networkidle")

                elif action_type == "screenshot":
                    output = action.get("output", "screenshot.png")
                    full_page = action.get("full_page", True)
                    page.screenshot(path=output, full_page=full_page)

            # Wait for element if specified
            if wait_for:
                page.wait_for_selector(wait_for, timeout=timeout_ms)

            # Extract content
            title = page.title()
            final_url = page.url

            # Get text content
            text_content = page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(s => s.remove());
                return document.body.innerText;
            }""")
            text_content = _normalize_text(text_content)

            result = {
                "title": title,
                "url": final_url,
                "content": text_content,
            }

            # Extract specific content if selector provided
            if extract:
                elements = page.query_selector_all(extract)
                if elements:
                    if len(elements) == 1:
                        result["extracted"] = elements[0].inner_text()
                    else:
                        result["extracted"] = [el.inner_text() for el in elements]

            # Save cookies if file specified
            if cookies_file:
                cookies_path = Path(cookies_file)
                saved_cookies = context.cookies()
                cookies_path.write_text(json.dumps(saved_cookies, indent=2))
                result["cookies_saved"] = str(cookies_path.absolute())

            browser.close()
            return result

    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "content": None,
        }


def _normalize_text(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Browser interactions")
    parser.add_argument("url", help="Starting URL")
    parser.add_argument("--actions", type=str, help="JSON string of actions")
    parser.add_argument("--extract", help="CSS selector to extract")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--system-chrome", action="store_true", help="Use system Chrome")

    args = parser.parse_args()

    actions = json.loads(args.actions) if args.actions else []

    result = interact(
        url=args.url,
        actions=actions,
        extract=args.extract,
        timeout=args.timeout,
        headless=not args.no_headless,
        use_system_chrome=args.system_chrome,
    )

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    if result.get("extracted"):
        print(f"\nExtracted:\n{result['extracted']}")
    else:
        print(f"\nContent:\n{result['content'][:500]}...")
