---
name: playwright
version: "1.0.0"
description: Use this skill for browser automation and web scraping requiring JavaScript rendering. Includes fetching dynamic content, taking screenshots, filling forms, logging into websites, and exporting pages to PDF. Activate this skill when web_fetch fails due to JavaScript-dependent content or when you need browser interactions beyond simple HTTP requests.

resources:
  assets:
    - path: "scripts/"
      description: "Playwright automation scripts"
      type: script
---

# Playwright Browser Automation

## Overview

Playwright enables browser automation for tasks that require JavaScript rendering or user interaction. Use this skill when:

- `web_fetch` returns incomplete content due to JavaScript rendering
- You need to take screenshots of web pages
- You need to fill forms or interact with elements
- You need to log into websites
- You need to export pages as PDF
- You need to wait for dynamic content to load

## Prerequisites

```bash
# Install playwright
pip install playwright

# Download browser (required once)
playwright install chromium

# Or use system Chrome (no download needed)
# Set use_system_chrome=True in scripts
```

## Available Scripts

### fetch_js - Fetch JavaScript-Rendered Content

Fetch content from pages that require JavaScript execution.

```python
from playwright_scripts import fetch_js

# Basic usage
result = fetch_js(url="https://spa-site.com")

# Wait for specific element
result = fetch_js(
    url="https://example.com",
    wait_for=".content-loaded",
    timeout=30
)

# Custom selectors to extract
result = fetch_js(
    url="https://news-site.com",
    selectors={
        "title": "h1.article-title",
        "body": ".article-content",
        "author": ".author-name"
    }
)
```

### screenshot - Capture Web Page Screenshots

Take full-page or viewport screenshots.

```python
from playwright_scripts import screenshot

# Full page screenshot (default - captures entire scrollable page)
screenshot(url="https://example.com", output="page.png")

# Viewport only (visible area only)
screenshot(url="https://example.com", output="viewport.png", full_page=False)

# Specific element
screenshot(
    url="https://example.com",
    output="chart.png",
    selector="#chart-container"
)

# Wait for lazy-loaded content + extra delay
screenshot(
    url="https://image-heavy-site.com",
    output="full.png",
    wait_for=".gallery-loaded",
    delay=2.0  # Extra 2 seconds after scroll
)

# Disable auto-scroll (if causing issues)
screenshot(
    url="https://example.com",
    output="page.png",
    scroll_to_load=False
)

# Custom viewport size
screenshot(
    url="https://example.com",
    output="mobile.png",
    viewport={"width": 375, "height": 667}
)
```

**Full-page screenshot behavior:**
- By default, scrolls through the entire page to trigger lazy-loaded content
- Waits for images and dynamic content to load
- Use `scroll_to_load=False` to disable auto-scroll
- Use `delay=N` to add extra wait time after scrolling

### interact - Browser Interactions

Fill forms, click buttons, navigate pages.

```python
from playwright_scripts import interact

# Login example
result = interact(
    url="https://example.com/login",
    actions=[
        {"type": "fill", "selector": "#username", "value": "user@example.com"},
        {"type": "fill", "selector": "#password", "value": "secret"},
        {"type": "click", "selector": "button[type=submit]"},
        {"type": "wait", "selector": ".dashboard"},
    ],
    extract=".welcome-message"
)

# Search and extract
result = interact(
    url="https://shop.example.com",
    actions=[
        {"type": "fill", "selector": "#search", "value": "laptop"},
        {"type": "press", "key": "Enter"},
        {"type": "wait", "selector": ".product-list"},
    ],
    extract=".product-item"
)
```

### export_pdf - Export Page as PDF

Save web pages as PDF documents.

```python
from playwright_scripts import export_pdf

# Basic PDF export
export_pdf(url="https://example.com", output="page.pdf")

# With custom format
export_pdf(
    url="https://example.com",
    output="page.pdf",
    format="A4",
    margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
)

# Wait for content before export
export_pdf(
    url="https://report.example.com",
    output="report.pdf",
    wait_for=".report-ready"
)
```

## Action Types

| Action | Parameters | Description |
|--------|------------|-------------|
| `fill` | selector, value | Fill text input |
| `click` | selector | Click element |
| `press` | key | Press keyboard key |
| `wait` | selector, timeout? | Wait for element |
| `wait_navigation` | - | Wait for page load |
| `select` | selector, value | Select dropdown option |
| `check` | selector | Check checkbox |
| `uncheck` | selector | Uncheck checkbox |
| `hover` | selector | Hover over element |
| `screenshot` | output? | Take screenshot |
| `goto` | url | Navigate to URL |

## Browser Options

All scripts support these common options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `headless` | bool | True | Run without visible browser |
| `use_system_chrome` | bool | False | Use installed Chrome instead of bundled |
| `timeout` | int | 30 | Default timeout in seconds |
| `viewport` | dict | 1280x720 | Browser viewport size |
| `user_agent` | str | Default Chrome UA | Custom user agent |
| `cookies` | list | [] | Cookies to set before navigation |
| `delay` | float | 0 | Extra delay before screenshot (screenshot only) |
| `scroll_to_load` | bool | True | Auto-scroll to trigger lazy content (screenshot only) |

## Examples

### Scrape SPA (Single Page Application)

```python
from playwright_scripts import fetch_js

# Many modern sites load content via JavaScript
content = fetch_js(
    url="https://react-app.example.com",
    wait_for="[data-loaded=true]",
    timeout=60
)
print(content)
```

### Login and Scrape Protected Content

```python
from playwright_scripts import interact

result = interact(
    url="https://portal.example.com/login",
    actions=[
        {"type": "fill", "selector": "#email", "value": "user@example.com"},
        {"type": "fill", "selector": "#password", "value": "password123"},
        {"type": "click", "selector": "#login-btn"},
        {"type": "wait", "selector": ".dashboard"},
    ],
    extract=".user-data",
    cookies_file="session_cookies.json"  # Save session
)
```

### Take Screenshot of Dynamic Chart

```python
from playwright_scripts import screenshot

screenshot(
    url="https://charts.example.com/dynamic-chart",
    output="chart.png",
    wait_for="canvas.chart-ready",
    selector="#chart-container"
)
```

### Export Invoice to PDF

```python
from playwright_scripts import export_pdf

export_pdf(
    url="https://billing.example.com/invoice/12345",
    output="invoice_12345.pdf",
    wait_for=".invoice-loaded",
    format="A4",
    margin={"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"}
)
```

## Troubleshooting

### "Executable doesn't exist" Error

```bash
# Run this to download browser
playwright install chromium

# Or use system Chrome
# Pass use_system_chrome=True to scripts
```

### Timeout Errors

- Increase `timeout` parameter
- Check if `wait_for` selector is correct
- The page may have anti-bot protection

### Content Not Loading

- Try `wait_for` with a specific selector
- Check if the site requires cookies/authentication
- Some sites detect headless browsers; try `headless=False`

### Memory Issues

For long-running sessions, close the browser between operations:

```python
# Scripts handle this automatically
# But for multiple operations, consider reusing a session
```

## Security Notes

- Never store passwords in scripts
- Use environment variables for sensitive credentials
- Be respectful of website terms of service
- Some sites prohibit automated access
