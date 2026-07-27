"""Authoritative, timezone-aware temporal context."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Clock(Protocol):
    """Small seam for obtaining the current aware datetime."""

    def now(self) -> datetime:
        """Return the current datetime."""
        ...


@dataclass(frozen=True)
class SystemClock:
    """Clock adapter backed by the operating system."""

    timezone_name: str | None = None

    def now(self) -> datetime:
        if self.timezone_name:
            return datetime.now(ZoneInfo(self.timezone_name))
        return datetime.now().astimezone()


@dataclass(frozen=True)
class TemporalContext:
    """A normalized snapshot used by prompts and time-aware tools."""

    local_datetime: str
    local_date: str
    timezone_name: str
    utc_offset: str
    utc_datetime: str

    @classmethod
    def capture(
        cls,
        clock: Clock | None = None,
        *,
        timezone_name: str | None = None,
    ) -> TemporalContext:
        current = (clock or SystemClock(timezone_name)).now()
        if current.tzinfo is None or current.utcoffset() is None:
            current = current.astimezone()

        if timezone_name:
            current = current.astimezone(ZoneInfo(timezone_name))

        resolved_name = timezone_name or _timezone_name(current)
        return cls(
            local_datetime=current.isoformat(timespec="seconds"),
            local_date=current.date().isoformat(),
            timezone_name=resolved_name,
            utc_offset=_format_utc_offset(current),
            utc_datetime=current.astimezone(UTC).isoformat(timespec="seconds"),
        )

    def render_prompt(self) -> str:
        """Render stable date facts for the model's system context."""
        return (
            "## Current Environment\n\n"
            f"Current local date: {self.local_date}\n"
            f"Timezone: {self.timezone_name}\n"
            f"UTC offset: {self.utc_offset}\n\n"
            "Treat this date and timezone as authoritative. Resolve “today”, "
            "“tomorrow”, “yesterday”, and other relative dates from them. "
            "Use `get_current_datetime` when exact time or timezone conversion is required."
        )


def resolve_timezone(name: str) -> ZoneInfo:
    """Resolve an IANA timezone name."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def _timezone_name(current: datetime) -> str:
    configured = os.environ.get("TZ")
    if configured:
        return configured.removeprefix(":")

    key = getattr(current.tzinfo, "key", None)
    if isinstance(key, str) and key:
        return key

    for candidate in (Path("/etc/localtime"), Path("/var/db/timezone/localtime")):
        try:
            target = candidate.resolve()
        except OSError:
            continue
        marker = "zoneinfo/"
        if marker in str(target):
            return str(target).split(marker, 1)[1]

    return current.tzname() or "local"


def _format_utc_offset(current: datetime) -> str:
    offset = current.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


__all__ = [
    "Clock",
    "SystemClock",
    "TemporalContext",
    "resolve_timezone",
]
