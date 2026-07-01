"""
Tests for markdown-lite terminal wrapping.
"""

from quenda.interface.console import ConsoleRenderer
from quenda.interface.markdown import render_markdown_lite, wrap_terminal_text
from quenda.runtime.events import ModelResponded, RunCompleted


def test_wrap_terminal_text_wraps_long_plain_line() -> None:
    """Long plain text should wrap to the requested width."""
    text = "This is a long sentence that should wrap after a limited number of characters."
    wrapped = wrap_terminal_text(text, width=40)

    lines = wrapped.splitlines()
    assert len(lines) >= 2
    assert all(len(line) <= 40 for line in lines if line)


def test_render_markdown_lite_wrap_option_applies_width() -> None:
    """render_markdown_lite should support wrapping."""
    text = "A fairly long line that should wrap cleanly when requested."
    rendered = render_markdown_lite(text, wrap=True, width=35)

    lines = rendered.splitlines()
    assert len(lines) >= 2
    assert all(len(line) <= 35 for line in lines if line)


def test_console_renderer_completion_has_spacing() -> None:
    """Run completion should start on its own block."""
    renderer = ConsoleRenderer()
    event = RunCompleted(total_steps=3, duration_ms=1200)
    rendered = renderer.render(event)

    assert rendered is not None
    assert rendered.startswith("\n\n✅ Done")


def test_console_renderer_preserves_model_content() -> None:
    """Model responses should render as a single paragraph by default."""
    renderer = ConsoleRenderer()
    event = ModelResponded(
        content="This is a very long assistant response that should wrap so it does not run off the edge of the terminal.",
        stop_reason="end_turn",
    )
    rendered = renderer.render(event)

    assert rendered is not None
    assert rendered.strip("\n") == "This is a very long assistant response that should wrap so it does not run off the edge of the terminal."
