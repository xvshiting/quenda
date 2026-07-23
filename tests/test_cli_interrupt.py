"""Tests for CLI interrupt behavior."""

from quenda.cli import _register_exit_interrupt


def test_second_ctrl_c_within_window_confirms_exit() -> None:
    should_exit, recorded_at = _register_exit_interrupt(None, now=10.0)
    assert should_exit is False
    assert recorded_at == 10.0

    should_exit, recorded_at = _register_exit_interrupt(recorded_at, now=11.0)
    assert should_exit is True
    assert recorded_at is None


def test_ctrl_c_after_window_starts_a_new_sequence() -> None:
    should_exit, recorded_at = _register_exit_interrupt(10.0, now=11.6)
    assert should_exit is False
    assert recorded_at == 11.6
