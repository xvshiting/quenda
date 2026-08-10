"""Terminal activity rendering regression tests."""

import time
from io import StringIO

from wcwidth import wcswidth

from quenda.interface.activity import SpinnerIndicator
from quenda.interface.theme import InterfaceTheme


def test_spinner_clears_previous_cjk_cell_width() -> None:
    stream = StringIO()
    indicator = SpinnerIndicator(
        stream=stream,
        enabled=False,
        theme=InterfaceTheme(show_esc_hint=False),
    )
    indicator._started_at = time.monotonic()

    indicator.message = "正在读取中文"
    indicator._write_frame("⠋")
    previous_width = indicator._last_frame_width
    indicator.message = "完成"
    indicator._write_frame("⠙")

    assert previous_width >= wcswidth("⠋ 正在读取中文 · 0s")
    assert indicator._last_frame_width == wcswidth("⠙ 完成 · 0s")
    assert stream.getvalue().endswith(" " * (previous_width - indicator._last_frame_width))
