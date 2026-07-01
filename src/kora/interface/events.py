"""
Event handling protocols and implementations for Kora Interface layer.

Provides abstractions for handling Runtime events in different ways:
- StreamingEventHandler: Real-time output as events arrive
- ActivityEventHandler: Real-time indicator updates without rendering content
- ProgressEventHandler: Real-time rendering for process/progress events only
- BatchEventHandler: Collect events and render at the end
- CollectingEventHandler: Collect events without rendering (for observability)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from kora.interface.activity import ActivityIndicator
    from kora.interface.console import ConsoleRenderer
    from kora.interface.status import StatusBarManager
    from kora.interface.theme import InterfaceTheme
    from kora.runtime.events import (
        AnyEvent,
        RunStarted,
        RunCompleted,
        RunInterrupted,
        ModelResponded,
        ToolExecuted,
        ErrorOccurred,
        CompressionStarted,
        CompressionCompleted,
    )


class EventHandler(Protocol):
    """
    Protocol for handling Runtime events.

    An event handler receives events from the Runtime and processes them
    in some way - typically rendering to output, collecting for analysis,
    or forwarding to external systems.

    All methods should be safe to call synchronously during run execution.
    """

    def on_run_started(self, event: RunStarted) -> None:
        """
        Handle run started event.

        Args:
            event: The run started event.
        """
        ...

    def on_model_responded(self, event: ModelResponded) -> None:
        """
        Handle model responded event.

        Args:
            event: The model responded event with content and/or tool calls.
        """
        ...

    def on_tool_executed(self, event: ToolExecuted) -> None:
        """
        Handle tool executed event.

        Args:
            event: The tool executed event with result and status.
        """
        ...

    def on_run_completed(self, event: RunCompleted) -> None:
        """
        Handle run completed event.

        Args:
            event: The run completed event with summary.
        """
        ...

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        """
        Handle run interrupted event.

        Args:
            event: The run interrupted event.
        """
        ...

    def on_error(self, event: ErrorOccurred) -> None:
        """
        Handle error event.

        Args:
            event: The error event with details.
        """
        ...

    def on_event(self, event: AnyEvent) -> None:
        """
        Handle any event (dispatch method).

        This is the main entry point called by the Runtime.
        Implementations should dispatch to specific on_* methods.

        Args:
            event: Any runtime event.
        """
        ...


@dataclass
class StreamingEventHandler:
    """
    Event handler that renders events in real-time.

    This is the default handler for interactive REPL and one-shot modes.
    It coordinates between the activity indicator and console renderer
    to provide responsive, streaming output.

    Usage:
        handler = StreamingEventHandler(renderer, indicator, theme)
        session.send_sync(message, on_event=handler.on_event)
    """

    renderer: ConsoleRenderer
    indicator: ActivityIndicator
    theme: InterfaceTheme
    output: TextIO = field(default_factory=lambda: sys.stdout)
    verbose_start: bool = False
    # Track pending tools for accurate indicator updates
    _pending_tools: int = field(default=0, init=False)
    _tool_summaries: list[str] = field(default_factory=list, init=False)

    def on_run_started(self, event: RunStarted) -> None:
        """Start the activity indicator."""
        self.indicator.start()
        if self.verbose_start:
            self.indicator.stop()
            rendered = self.renderer.render(event)
            if rendered:
                print(rendered, file=self.output)
            self.indicator.start()

    def on_model_responded(self, event: ModelResponded) -> None:
        """Render model response and manage indicator."""
        # Track pending tools for indicator updates
        if event.tool_call_details:
            self._pending_tools = len(event.tool_call_details)
            self._tool_summaries = [
                d.get("arguments", {}).get("_summary", "") or f"Running {d.get('name', 'tool')}..."
                for d in event.tool_call_details
            ]
            # Show first tool's summary (it's executing now)
            self.indicator.update(self._tool_summaries[0] if self._tool_summaries else "Running...")
        else:
            self._pending_tools = 0
            self._tool_summaries = []
            self.indicator.update(self.theme.thinking_message)

        # Stop indicator, render content, restart if tools pending
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)

        if event.tool_call_details:
            self.indicator.start()

    def on_tool_executed(self, event: ToolExecuted) -> None:
        """Render tool execution result."""
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)

        # Decrement pending tools counter
        self._pending_tools -= 1

        # Update indicator based on remaining tools
        if self._pending_tools > 0 and self._tool_summaries:
            # More tools pending - show next tool's summary
            # Index for next tool: original_count - pending - 1
            next_idx = len(self._tool_summaries) - self._pending_tools - 1
            if next_idx >= 0 and next_idx < len(self._tool_summaries):
                self.indicator.update(self._tool_summaries[next_idx])
            else:
                self.indicator.update(f"Executing {self._pending_tools} more tools...")
        else:
            # All tools completed - show thinking state
            self.indicator.update(self.theme.thinking_message)

        self.indicator.start()

    def on_run_completed(self, event: RunCompleted) -> None:
        """Stop indicator and render completion."""
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        """Stop indicator and show interruption message."""
        self.indicator.stop()
        print(f"\n{self.theme.interrupt_icon} Interrupted by user", file=self.output)

    def on_error(self, event: ErrorOccurred) -> None:
        """Stop indicator and render error."""
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)

    def on_compression_started(self, event: CompressionStarted) -> None:
        """Handle compression started - show indicator and render message."""
        self.indicator.update("Compressing context...")
        self.indicator.start()
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_compression_completed(self, event: CompressionCompleted) -> None:
        """Handle compression completed - render result."""
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.update(self.theme.thinking_message)
        self.indicator.start()

    def on_event(self, event: AnyEvent) -> None:
        """Dispatch event to appropriate handler."""
        if event.type == "run_started":
            self.on_run_started(event)  # type: ignore[arg-type]
        elif event.type == "model_responded":
            self.on_model_responded(event)  # type: ignore[arg-type]
        elif event.type == "tool_executed":
            self.on_tool_executed(event)  # type: ignore[arg-type]
        elif event.type == "run_completed":
            self.on_run_completed(event)  # type: ignore[arg-type]
        elif event.type == "run_interrupted":
            self.on_run_interrupted(event)  # type: ignore[arg-type]
        elif event.type == "error_occurred":
            self.on_error(event)  # type: ignore[arg-type]
        elif event.type == "compression_started":
            self.on_compression_started(event)  # type: ignore[arg-type]
        elif event.type == "compression_completed":
            self.on_compression_completed(event)  # type: ignore[arg-type]


@dataclass
class ActivityEventHandler:
    """
    Event handler that only drives the activity indicator.

    Useful for hidden follow-up phases where Host wants to preserve
    thinking/working animations without revealing intermediate content.
    """

    indicator: ActivityIndicator
    theme: InterfaceTheme
    renderer: ConsoleRenderer | None = None
    status_bar: StatusBarManager | None = None
    _pending_tools: int = field(default=0, init=False)
    _tool_summaries: list[str] = field(default_factory=list, init=False)
    _run_count: int = field(default=0, init=False)
    _last_phase: str | None = field(default=None, init=False)

    def _record_activity(self, line: str | None) -> None:
        if line and self.status_bar is not None:
            self.status_bar.append_activity(line)

    def on_run_started(self, event: RunStarted) -> None:
        self._run_count += 1
        self._last_phase = None
        self.indicator.start()
        self.indicator.update(self.theme.thinking_message)
        if self.status_bar is not None:
            self.status_bar.append_activity(f"Run {self._run_count}")
            self.status_bar.set_running(True, self.theme.thinking_message)

    def on_model_responded(self, event: ModelResponded) -> None:
        if event.tool_call_details:
            self._pending_tools = len(event.tool_call_details)
            self._tool_summaries = [
                d.get("arguments", {}).get("_summary", "") or f"Running {d.get('name', 'tool')}..."
                for d in event.tool_call_details
            ]
            message = self._tool_summaries[0] if self._tool_summaries else "Running..."
            self.indicator.update(message)
            if self.status_bar is not None:
                self.status_bar.set_running(True, message)
            self._record_activity(message)
        else:
            self._pending_tools = 0
            self._tool_summaries = []
            self.indicator.update(self.theme.thinking_message)
            if self.status_bar is not None:
                self.status_bar.set_running(True, self.theme.thinking_message)

    def on_tool_executed(self, event: ToolExecuted) -> None:
        self._pending_tools -= 1
        phase = self.theme.tool_phases.get(event.tool_name, "executing")
        phase_label = self.theme.phase_labels.get(phase, "⚡ Running")
        if self.status_bar is not None and phase_label != self._last_phase:
            self.status_bar.append_activity(f"[{phase_label}]")
        self._last_phase = phase_label
        if self.renderer is not None:
            self._record_activity(self.renderer.render(event))

        if self._pending_tools > 0 and self._tool_summaries:
            next_idx = len(self._tool_summaries) - self._pending_tools - 1
            if 0 <= next_idx < len(self._tool_summaries):
                message = self._tool_summaries[next_idx]
            else:
                message = f"Executing {self._pending_tools} more tools..."
        else:
            message = self.theme.thinking_message
        self.indicator.update(message)
        if self.status_bar is not None:
            self.status_bar.set_running(True, message)

    def on_run_completed(self, event: RunCompleted) -> None:
        self.indicator.stop()
        if self.status_bar is not None:
            self.status_bar.set_running(False)

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        self.indicator.stop()
        if self.status_bar is not None:
            self.status_bar.set_interrupted()

    def on_error(self, event: ErrorOccurred) -> None:
        self.indicator.stop()
        if self.status_bar is not None:
            self.status_bar.set_error(event.error_message)
        if self.renderer is not None:
            self._record_activity(self.renderer.render(event))

    def on_compression_started(self, event: CompressionStarted) -> None:
        self.indicator.update("Compressing context...")
        self.indicator.start()
        if self.status_bar is not None:
            self.status_bar.set_running(True, "Compressing context...")
        if self.renderer is not None:
            self._record_activity(self.renderer.render(event))

    def on_compression_completed(self, event: CompressionCompleted) -> None:
        self.indicator.update(self.theme.thinking_message)
        if self.status_bar is not None:
            self.status_bar.set_running(True, self.theme.thinking_message)
        if self.renderer is not None:
            self._record_activity(self.renderer.render(event))

    def on_event(self, event: AnyEvent) -> None:
        if event.type == "run_started":
            self.on_run_started(event)  # type: ignore[arg-type]
        elif event.type == "model_responded":
            self.on_model_responded(event)  # type: ignore[arg-type]
        elif event.type == "tool_executed":
            self.on_tool_executed(event)  # type: ignore[arg-type]
        elif event.type == "run_completed":
            self.on_run_completed(event)  # type: ignore[arg-type]
        elif event.type == "run_interrupted":
            self.on_run_interrupted(event)  # type: ignore[arg-type]
        elif event.type == "error_occurred":
            self.on_error(event)  # type: ignore[arg-type]
        elif event.type == "compression_started":
            self.on_compression_started(event)  # type: ignore[arg-type]
        elif event.type == "compression_completed":
            self.on_compression_completed(event)  # type: ignore[arg-type]


@dataclass
class ProgressEventHandler:
    """
    Event handler that renders process events but suppresses model content.

    This is used for hidden or host-managed follow-up phases where users should
    still see progress, tool execution, and operational feedback in real time,
    while assistant natural-language content remains deferred until the phase is
    known to be the final visible one.
    """

    renderer: ConsoleRenderer
    indicator: ActivityIndicator
    output: TextIO = field(default_factory=lambda: sys.stdout)
    _run_count: int = field(default=0, init=False)
    _last_phase: str | None = field(default=None, init=False)

    def on_run_started(self, event: RunStarted) -> None:
        """Track run count but don't display phase headers."""
        self._run_count += 1
        self._last_phase = None

    def on_model_responded(self, event: ModelResponded) -> None:
        return None

    def on_tool_executed(self, event: ToolExecuted) -> None:
        self.indicator.stop()
        phase = self.renderer.theme.tool_phases.get(event.tool_name, "executing")
        phase_label = self.renderer.theme.phase_labels.get(phase, "⚡ Running")
        if phase_label != self._last_phase:
            if self._last_phase is None:
                print(f"\n[{phase_label}]", file=self.output)
            else:
                print(f"\n[{phase_label}]", file=self.output)
            self._last_phase = phase_label
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_run_completed(self, event: RunCompleted) -> None:
        self.indicator.stop()

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        self.indicator.stop()

    def on_error(self, event: ErrorOccurred) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_compression_started(self, event: CompressionStarted) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_compression_completed(self, event: CompressionCompleted) -> None:
        self.indicator.stop()
        rendered = self.renderer.render(event)
        if rendered:
            print(rendered, file=self.output)
        self.indicator.start()

    def on_event(self, event: AnyEvent) -> None:
        if event.type == "run_started":
            self.on_run_started(event)  # type: ignore[arg-type]
        elif event.type == "tool_executed":
            self.on_tool_executed(event)  # type: ignore[arg-type]
        elif event.type == "run_completed":
            self.on_run_completed(event)  # type: ignore[arg-type]
        elif event.type == "run_interrupted":
            self.on_run_interrupted(event)  # type: ignore[arg-type]
        elif event.type == "error_occurred":
            self.on_error(event)  # type: ignore[arg-type]
        elif event.type == "compression_started":
            self.on_compression_started(event)  # type: ignore[arg-type]
        elif event.type == "compression_completed":
            self.on_compression_completed(event)  # type: ignore[arg-type]


@dataclass
class BatchEventHandler:
    """
    Event handler that collects events and renders at the end.

    Useful for one-shot mode when you want clean, consolidated output
    rather than streaming updates.

    Usage:
        handler = BatchEventHandler(renderer, theme)
        session.send_sync(message, on_event=handler.on_event)
        print(handler.render_all())
    """

    renderer: ConsoleRenderer
    theme: InterfaceTheme
    events: list[AnyEvent] = field(default_factory=list)
    output: TextIO = field(default_factory=lambda: sys.stdout)

    def on_run_started(self, event: RunStarted) -> None:
        self.events.append(event)

    def on_model_responded(self, event: ModelResponded) -> None:
        self.events.append(event)

    def on_tool_executed(self, event: ToolExecuted) -> None:
        self.events.append(event)

    def on_run_completed(self, event: RunCompleted) -> None:
        self.events.append(event)

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        self.events.append(event)

    def on_error(self, event: ErrorOccurred) -> None:
        self.events.append(event)

    def on_event(self, event: AnyEvent) -> None:
        """Collect all events."""
        self.events.append(event)

    def render_all(self) -> str:
        """
        Render all collected events.

        Returns:
            Combined rendered output for all events.
        """
        lines = []
        for event in self.events:
            rendered = self.renderer.render(event)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)

    def print_all(self) -> None:
        """Print all rendered events to output."""
        output = self.render_all()
        if output:
            print(output, file=self.output)

    def clear(self) -> None:
        """Clear collected events."""
        self.events.clear()


@dataclass
class CollectingEventHandler:
    """
    Event handler that only collects events without rendering.

    Useful for testing, observability, or when you need to inspect
    events after execution.

    Usage:
        handler = CollectingEventHandler()
        session.send_sync(message, on_event=handler.on_event)
        events = handler.get_events()
    """

    events: list[AnyEvent] = field(default_factory=list)

    def on_run_started(self, event: RunStarted) -> None:
        self.events.append(event)

    def on_model_responded(self, event: ModelResponded) -> None:
        self.events.append(event)

    def on_tool_executed(self, event: ToolExecuted) -> None:
        self.events.append(event)

    def on_run_completed(self, event: RunCompleted) -> None:
        self.events.append(event)

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        self.events.append(event)

    def on_error(self, event: ErrorOccurred) -> None:
        self.events.append(event)

    def on_event(self, event: AnyEvent) -> None:
        """Collect all events."""
        self.events.append(event)

    def get_events(self) -> list[AnyEvent]:
        """
        Get a copy of collected events.

        Returns:
            List of all collected events.
        """
        return self.events.copy()

    def get_events_by_type(self, event_type: str) -> list[AnyEvent]:
        """
        Get events of a specific type.

        Args:
            event_type: The event type to filter by.

        Returns:
            List of events matching the type.
        """
        return [e for e in self.events if e.type == event_type]

    def clear(self) -> None:
        """Clear collected events."""
        self.events.clear()


@dataclass
class CompositeEventHandler:
    """
    Event handler that dispatches to multiple handlers.

    Useful for combining behaviors, e.g., streaming output while
    also collecting events for logging.

    Usage:
        streaming = StreamingEventHandler(renderer, indicator, theme)
        collector = CollectingEventHandler()
        composite = CompositeEventHandler([streaming, collector])
        session.send_sync(message, on_event=composite.on_event)
    """

    handlers: list[EventHandler]

    def on_run_started(self, event: RunStarted) -> None:
        for handler in self.handlers:
            handler.on_run_started(event)

    def on_model_responded(self, event: ModelResponded) -> None:
        for handler in self.handlers:
            handler.on_model_responded(event)

    def on_tool_executed(self, event: ToolExecuted) -> None:
        for handler in self.handlers:
            handler.on_tool_executed(event)

    def on_run_completed(self, event: RunCompleted) -> None:
        for handler in self.handlers:
            handler.on_run_completed(event)

    def on_run_interrupted(self, event: RunInterrupted) -> None:
        for handler in self.handlers:
            handler.on_run_interrupted(event)

    def on_error(self, event: ErrorOccurred) -> None:
        for handler in self.handlers:
            handler.on_error(event)

    def on_event(self, event: AnyEvent) -> None:
        """Dispatch to all handlers."""
        for handler in self.handlers:
            handler.on_event(event)


__all__ = [
    "EventHandler",
    "StreamingEventHandler",
    "ActivityEventHandler",
    "ProgressEventHandler",
    "BatchEventHandler",
    "CollectingEventHandler",
    "CompositeEventHandler",
]
