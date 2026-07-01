"""Tests for REPL-specific interface helpers."""

from kora.interface.repl import format_activity_log
from kora.interface.status import StatusBarManager


def test_format_activity_log_renders_entries() -> None:
    status_bar = StatusBarManager()
    status_bar.append_activity("Searching latest filings")
    status_bar.append_activity("✓ Fetched report")

    rendered = format_activity_log(status_bar)

    assert "Activity Log" in rendered
    assert "Searching latest filings" in rendered
    assert "✓ Fetched report" in rendered


def test_running_status_includes_ctrl_o_hint_when_log_exists() -> None:
    status_bar = StatusBarManager()
    status_bar.append_activity("Searching latest filings")
    status_bar.set_running(True, "Searching latest filings")

    text = status_bar.get_text()

    assert "Searching latest filings" in text
    assert "Ctrl+O" in text


def test_expanded_activity_panel_renders_in_status_text() -> None:
    status_bar = StatusBarManager()
    status_bar.append_activity("Run 1")
    status_bar.append_activity("[🔍 Searching]")
    status_bar.append_activity("✓ Searching latest filings → 3 matches")
    status_bar.set_running(True, "Searching latest filings")
    status_bar.set_activity_expanded(True)

    text = status_bar.get_text()

    assert "Activity" in text
    assert "Run 1" in text
    assert "3 matches" in text
