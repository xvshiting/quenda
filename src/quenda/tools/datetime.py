"""Read-only tool for precise current datetime and timezone conversion."""

from __future__ import annotations

import json
from datetime import datetime
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.runtime.temporal import Clock, SystemClock, TemporalContext, resolve_timezone


class GetCurrentDatetimeTool(Tool):
    """Return an authoritative, structured datetime snapshot."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()

    @property
    @override
    def name(self) -> str:
        return "get_current_datetime"

    @property
    @override
    def description(self) -> str:
        return (
            "Get the exact current date and time. Use this for current time, "
            "timestamps, deadlines, or timezone conversions."
        )

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone, such as UTC, Asia/Shanghai, "
                        "or America/New_York."
                    ),
                },
            },
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        requested = kwargs.get("timezone")
        timezone_name = requested if isinstance(requested, str) and requested else None

        try:
            current = self._clock.now()
            if timezone_name:
                current = current.astimezone(resolve_timezone(timezone_name))
            context = TemporalContext.capture(
                _SnapshotClock(current),
                timezone_name=timezone_name,
            )
        except ValueError as exc:
            return ToolResult(
                call_id="",
                name=self.name,
                content=str(exc),
                is_error=True,
            )

        payload = {
            "datetime": context.local_datetime,
            "date": context.local_date,
            "timezone": context.timezone_name,
            "utc_offset": context.utc_offset,
            "utc_datetime": context.utc_datetime,
        }
        return ToolResult(
            call_id="",
            name=self.name,
            content=json.dumps(payload, ensure_ascii=False),
        )


class _SnapshotClock:
    def __init__(self, current: datetime) -> None:
        self._current = current

    def now(self) -> datetime:
        return self._current


__all__ = ["GetCurrentDatetimeTool"]
