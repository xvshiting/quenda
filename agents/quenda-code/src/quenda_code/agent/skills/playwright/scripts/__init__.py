"""
Playwright automation scripts for browser automation.

Scripts:
- fetch_js: Fetch JavaScript-rendered content
- screenshot: Capture web page screenshots
- interact: Browser interactions (forms, clicks, navigation)
- export_pdf: Export pages as PDF
"""

from .fetch_js import fetch_js
from .screenshot import screenshot
from .interact import interact
from .export_pdf import export_pdf

__all__ = [
    "fetch_js",
    "screenshot",
    "interact",
    "export_pdf",
]
