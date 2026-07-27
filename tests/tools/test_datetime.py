"""Tests for the precise current datetime tool."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from quenda.tools.datetime import GetCurrentDatetimeTool


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 26, 14, 32, 18, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_current_datetime_returns_structured_local_time() -> None:
    result = GetCurrentDatetimeTool(clock=FixedClock()).execute()
    payload = json.loads(result.content)

    assert result.is_error is False
    assert payload["datetime"] == "2026-07-26T14:32:18+08:00"
    assert payload["date"] == "2026-07-26"
    assert payload["timezone"] == "Asia/Shanghai"
    assert payload["utc_offset"] == "+08:00"


def test_current_datetime_converts_to_requested_timezone() -> None:
    result = GetCurrentDatetimeTool(clock=FixedClock()).execute(timezone="UTC")
    payload = json.loads(result.content)

    assert payload["datetime"] == "2026-07-26T06:32:18+00:00"
    assert payload["timezone"] == "UTC"


def test_current_datetime_rejects_unknown_timezone() -> None:
    result = GetCurrentDatetimeTool(clock=FixedClock()).execute(timezone="Mars/Olympus")

    assert result.is_error is True
    assert "Unknown timezone" in result.content
