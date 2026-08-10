"""Tests for REPL-specific interface helpers."""

from types import SimpleNamespace

import pytest
from prompt_toolkit.document import Document

from quenda.interface.repl import (
    HAS_PROMPT_TOOLKIT,
    CommandCompleter,
    PromptToolkitInput,
    format_activity_log,
)
from quenda.interface.status import StatusBarManager


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


@pytest.mark.skipif(not HAS_PROMPT_TOOLKIT, reason="prompt-toolkit is unavailable")
def test_prompt_session_keeps_automatic_slash_completion_enabled() -> None:
    command = SimpleNamespace(name="model", description="Switch model")
    registry = SimpleNamespace(
        list_commands=lambda: [command],
        get=lambda _name: command,
    )
    repl = PromptToolkitInput(registry, StatusBarManager())

    assert repl._session.default_buffer.complete_while_typing()


@pytest.mark.skipif(not HAS_PROMPT_TOOLKIT, reason="prompt-toolkit is unavailable")
def test_slash_completer_returns_command_prefix_matches() -> None:
    commands = [
        SimpleNamespace(name="model", description="Switch model"),
        SimpleNamespace(name="mode", description="Switch mode"),
    ]
    registry = SimpleNamespace(list_commands=lambda: commands, get=lambda _name: None)
    completer = CommandCompleter(registry)

    completions = list(completer.get_completions(Document("/mod"), None))

    assert [completion.text for completion in completions] == ["/model", "/mode"]
