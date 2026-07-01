"""
TraceSink for Quenda Runtime observability.

This module defines the TraceSink protocol for observing runtime events.
TraceSink is an observer-only interface - it cannot affect control flow.

Usage:
    from quenda.runtime.trace import TraceSink, JsonlTraceSink

    # Create a JSONL trace sink
    sink = JsonlTraceSink("traces/run.jsonl")

    # Register with run
    run.trace_sink = sink
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Protocol

from quenda.runtime.events import AnyEvent


class TraceSink(Protocol):
    """
    Observer for runtime events.

    Runtime calls record() for each event emitted during run execution.
    This is an observer-only interface - it cannot affect control flow.

    Implementations must not raise exceptions from record().
    If an error occurs, log it internally but do not propagate.
    """

    def record(self, event: AnyEvent) -> None:
        """
        Record one runtime event.

        Args:
            event: A runtime event (RunStarted, ModelResponded, ToolExecuted, etc.)

        Note:
            This method must not raise exceptions.
            Errors should be handled internally by the implementation.
        """
        ...


class NullTraceSink:
    """
    No-op trace sink.

    Default implementation that does nothing with events.
    Used when no tracing is configured.
    """

    def record(self, event: AnyEvent) -> None:
        """Discard event silently."""
        pass


class JsonlTraceSink:
    """
    JSONL file-based trace sink.

    Appends each event as a JSON line to a file for later replay and analysis.
    Each line is a complete JSON object representing one event.

    Usage:
        sink = JsonlTraceSink("traces/run.jsonl")
        run.trace_sink = sink

    The file format is JSONL (JSON Lines):
        {"id": "...", "type": "run_started", "agent_name": "...", ...}
        {"id": "...", "type": "model_responded", ...}
        {"id": "...", "type": "tool_executed", ...}
        ...

    This format allows:
        - Streaming processing (one line at a time)
        - Easy parsing with standard JSON tools
        - Resilience to partial writes (each line is complete)
    """

    def __init__(self, path: str | Path) -> None:
        """
        Initialize the JSONL trace sink.

        Args:
            path: Path to the JSONL file. Parent directories are created if needed.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: AnyEvent) -> None:
        """
        Append event to JSONL file.

        Args:
            event: The runtime event to record.

        Note:
            Errors are silently ignored to prevent crashing the run.
        """
        try:
            data = asdict(event)
            # Add event type discriminator
            data["event_type"] = event.type
            # Ensure datetime is serialized properly
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, default=self._json_default) + "\n")
        except Exception:
            # Silently ignore errors - trace sink must not crash the run
            pass

    @staticmethod
    def _json_default(obj: object) -> str | None:
        """
        Custom JSON serializer for non-standard types.

        Args:
            obj: Object to serialize.

        Returns:
            String representation for datetime, None for others.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        return None


__all__ = [
    "TraceSink",
    "NullTraceSink",
    "JsonlTraceSink",
]
