"""Tests for authoritative Host temporal context."""

from datetime import datetime
from zoneinfo import ZoneInfo

from quenda.runtime.temporal import TemporalContext


class FixedClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def test_temporal_context_renders_authoritative_local_environment() -> None:
    clock = FixedClock(datetime(2026, 7, 26, 0, 5, tzinfo=ZoneInfo("Asia/Shanghai")))

    context = TemporalContext.capture(clock)

    assert context.local_date == "2026-07-26"
    assert context.timezone_name == "Asia/Shanghai"
    assert context.utc_offset == "+08:00"
    assert "Current local date: 2026-07-26" in context.render_prompt()
    assert "Treat this date and timezone as authoritative" in context.render_prompt()


def test_temporal_context_uses_local_date_not_utc_date() -> None:
    clock = FixedClock(datetime(2026, 1, 1, 0, 30, tzinfo=ZoneInfo("Asia/Shanghai")))

    context = TemporalContext.capture(clock)

    assert context.local_date == "2026-01-01"
    assert context.utc_datetime.startswith("2025-12-31T16:30:00")
