"""Markdown-lite renderer for terminal output.

Renders common Markdown formats for better terminal readability:
- Headers: # ## ### → bold/color (no size change, no ### prefix)
- Bold: **text** → ANSI bold
- Italic: *text* → ANSI italic
- Inline code: `code` → reverse/highlight
- Code blocks: ``` → indented
- Lists: - item → bullet points
- Ordered lists: 1. item → numbered
- Horizontal rules: --- → dimmed line

Does NOT render:
- Links (keep as plain text)
- Tables (keep as plain text)
- Images (keep as plain text)
"""

from __future__ import annotations

import re
import shutil
import textwrap
from typing import Match


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class MarkdownLiteRenderer:
    """Lightweight Markdown renderer for terminal output."""

    def __init__(self, *, enable_colors: bool = True) -> None:
        self.enable_colors = enable_colors

        self._bold_on = "\033[1m" if enable_colors else ""
        self._bold_off = "\033[0m" if enable_colors else ""
        self._italic_on = "\033[3m" if enable_colors else ""
        self._italic_off = "\033[0m" if enable_colors else ""
        self._reverse_on = "\033[36m" if enable_colors else ""
        self._reverse_off = "\033[0m" if enable_colors else ""
        self._dim_on = "\033[2m" if enable_colors else ""
        self._dim_off = "\033[0m" if enable_colors else ""
        self._cyan_on = "\033[36m" if enable_colors else ""
        self._cyan_off = "\033[0m" if enable_colors else ""
        self._yellow_on = "\033[33m" if enable_colors else ""
        self._yellow_off = "\033[0m" if enable_colors else ""

    def render(self, text: str) -> str:
        """Render markdown-lite text to terminal-friendly output."""
        if not text:
            return text

        result = text
        result, code_blocks = self._protect_code_blocks(result)
        result = self._normalize_indentation(result)
        result = self._render_headers(result)
        result = self._render_horizontal_rules(result)
        result = self._render_unordered_lists(result)
        result = self._render_ordered_lists(result)
        result = self._render_inline_code(result)
        result = self._render_bold(result)
        result = self._render_italic(result)
        result = self._restore_code_blocks(result, code_blocks)
        return result

    def _protect_code_blocks(self, text: str) -> tuple[str, dict[str, tuple[str, str]]]:
        """Replace code blocks with placeholders."""
        code_blocks: dict[str, tuple[str, str]] = {}
        counter = [0]

        def replace_block(match: Match[str]) -> str:
            lang = match.group(1) or ""
            code = match.group(2)
            placeholder = f"\x00CODE{counter[0]}\x00"
            code_blocks[placeholder] = (lang, code)
            counter[0] += 1
            return placeholder

        result = re.sub(r"```(\w*)\n(.*?)```", replace_block, text, flags=re.DOTALL)
        return result, code_blocks

    def _restore_code_blocks(self, text: str, code_blocks: dict[str, tuple[str, str]]) -> str:
        """Restore code blocks with indentation."""
        for placeholder, (lang, code) in code_blocks.items():
            lines = code.strip().split("\n")
            indented = "\n".join(f"  {line}" for line in lines)
            if lang:
                text = text.replace(placeholder, f"{self._dim_on}  [{lang}]{self._dim_off}\n{indented}")
            else:
                text = text.replace(placeholder, f"{indented}")
        return text

    def _normalize_indentation(self, text: str) -> str:
        """Strip accidental indentation from non-empty lines.

        The renderer does not support nested markdown structure, so keeping
        leading spaces usually makes prose drift to the right for no benefit.
        """
        return "\n".join(line.lstrip(" ") if line.strip() else line for line in text.splitlines())

    def _render_headers(self, text: str) -> str:
        """Render headers: # ## ### → bold/color, remove ### prefix."""

        def replace(match: Match[str]) -> str:
            level = len(match.group(1))
            content = match.group(2).strip()

            if level == 1:
                return f"{self._bold_on}{self._yellow_on}{content}{self._yellow_off}{self._bold_off}"
            if level == 2:
                return f"{self._bold_on}{self._cyan_on}{content}{self._cyan_off}{self._bold_off}"
            if level == 3:
                return f"{self._bold_on}{content}{self._bold_off}"
            return f"{self._dim_on}{self._bold_on}{content}{self._bold_off}{self._dim_off}"

        return re.sub(r"^(#{1,6})\s+(.+)$", replace, text, flags=re.MULTILINE)

    def _render_horizontal_rules(self, text: str) -> str:
        """Render --- as dimmed horizontal line."""
        return re.sub(r"^---+$", f"{self._dim_on}{'─' * 40}{self._dim_off}", text, flags=re.MULTILINE)

    def _render_unordered_lists(self, text: str) -> str:
        """Render - item → bullet point."""

        def replace(match: Match[str]) -> str:
            return f"  • {match.group(1)}"

        return re.sub(r"^- (.+)$", replace, text, flags=re.MULTILINE)

    def _render_ordered_lists(self, text: str) -> str:
        """Render 1. item → numbered."""
        counter = [0]

        def replace(match: Match[str]) -> str:
            counter[0] += 1
            return f"  {counter[0]}. {match.group(1)}"

        return re.sub(r"^\d+\.\s+(.+)$", replace, text, flags=re.MULTILINE)

    def _render_inline_code(self, text: str) -> str:
        """Render `code` with highlight."""

        def replace(match: Match[str]) -> str:
            return f"{self._reverse_on} {match.group(1)} {self._reverse_off}"

        return re.sub(r"`([^`]+)`", replace, text)

    def _render_bold(self, text: str) -> str:
        """Render **bold** text."""

        def replace(match: Match[str]) -> str:
            return f"{self._bold_on}{match.group(1)}{self._bold_off}"

        return re.sub(r"\*\*([^*]+?)\*\*", replace, text)

    def _render_italic(self, text: str) -> str:
        """Render *italic* text."""

        def replace(match: Match[str]) -> str:
            return f"{self._italic_on}{match.group(1)}{self._italic_off}"

        return re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", replace, text)


def _visible_length(text: str) -> int:
    """Return visible string length without ANSI escape sequences."""
    return len(ANSI_PATTERN.sub("", text))


def _wrap_plain_line(line: str, width: int) -> str:
    """Wrap a single plain text line while preserving ANSI escapes."""
    if _visible_length(line) <= width:
        return line

    content = line.strip()
    available = max(20, width)

    if "\x1b[" not in content:
        return textwrap.fill(
            content,
            width=available,
            break_long_words=False,
            break_on_hyphens=False,
        )

    tokens = re.findall(r"\x1b\[[0-9;]*m|[^\s\x1b]+|\s+", content)
    lines: list[str] = []
    current = ""
    current_len = 0

    for token in tokens:
        if ANSI_PATTERN.fullmatch(token):
            current += token
            continue

        if token.isspace():
            if current_len > 0:
                current += token
            continue

        token_len = _visible_length(token)
        if current_len > 0 and current_len + 1 + token_len > width:
            lines.append(current.rstrip())
            current = ""
            current_len = 0

        if current_len > 0:
            current += " "
            current_len += 1

        current += token
        current_len += token_len

    if current.strip():
        lines.append(current.rstrip())

    return "\n".join(lines)


def wrap_terminal_text(text: str, *, width: int | None = None) -> str:
    """
    Wrap terminal text to the current terminal width.

    Preserves blank lines and leaves structural markdown lines alone.
    """
    if not text:
        return text

    if width is None:
        width = shutil.get_terminal_size((100, 20)).columns

    width = max(40, width)
    wrapped_lines: list[str] = []

    for line in text.splitlines():
        if not line.strip():
            wrapped_lines.append("")
            continue

        stripped = line.lstrip(" ")
        if stripped.startswith("```") or stripped.startswith("#"):
            wrapped_lines.append(line)
            continue
        if line.startswith("  ") and (
            stripped.startswith("• ")
            or stripped[:2].isdigit()
            or stripped.startswith("[")
        ):
            wrapped_lines.append(line)
            continue
        if line.startswith("  "):
            line = line.strip()

        wrapped = _wrap_plain_line(line, width)
        wrapped_lines.extend(wrapped.splitlines() if wrapped else [""])

    return "\n".join(wrapped_lines)


def render_markdown_lite(
    text: str,
    *,
    enable_colors: bool = True,
    wrap: bool = False,
    width: int | None = None,
) -> str:
    """Render markdown-lite text."""
    rendered = MarkdownLiteRenderer(enable_colors=enable_colors).render(text)
    if wrap:
        rendered = wrap_terminal_text(rendered, width=width)
    return rendered


__all__ = ["MarkdownLiteRenderer", "render_markdown_lite", "wrap_terminal_text"]
