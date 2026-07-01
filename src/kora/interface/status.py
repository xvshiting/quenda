"""
Status text provider for Kora REPL.

The status bar is intentionally presentation-only:
- It exposes text for prompt_toolkit's bottom toolbar
- It does not write cursor-control ANSI codes directly
- It keeps the terminal layout stable while still showing activity
"""

from __future__ import annotations

import itertools
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from kora.interface.theme import InterfaceTheme


class StatusBarState(Enum):
    """State of the status bar."""

    IDLE = auto()
    RUNNING = auto()
    HIDDEN = auto()
    INTERRUPTED = auto()
    ERROR = auto()


@dataclass
class StatusContext:
    """
    Context information for status bar rendering.

    Provides all available context that status providers can use
    to generate status text.
    """

    mode: str = "chat"
    model: str = ""
    provider: str = ""
    workspace_id: str = ""
    session_id: str = ""
    current_tool: str | None = None
    tool_summary: str | None = None
    step_count: int = 0
    token_usage: dict | None = None  # For future expansion
    activity_count: int = 0


class StatusProvider(Protocol):
    """
    Protocol for status bar content providers.

    Implement this protocol to customize status bar appearance.
    """

    def get_idle_text(self, context: StatusContext) -> str:
        """
        Get text for idle state.

        Args:
            context: Current status context.

        Returns:
            Status bar text for idle state.
        """
        ...

    def get_running_text(
        self,
        context: StatusContext,
        frame: str,
        message: str,
        details_hint: str,
    ) -> str:
        """
        Get text for running state.

        Args:
            context: Current status context.
            frame: Current animation frame character.
            message: Current running message.
            details_hint: Optional hint for expanded details.

        Returns:
            Status bar text for running state.
        """
        ...

    def get_interrupted_text(self, context: StatusContext) -> str:
        """
        Get text for interrupted state.

        Args:
            context: Current status context.

        Returns:
            Status bar text for interrupted state.
        """
        ...

    def get_error_text(self, context: StatusContext, error: str) -> str:
        """
        Get text for error state.

        Args:
            context: Current status context.
            error: Error message.

        Returns:
            Status bar text for error state.
        """
        ...


class DefaultStatusProvider:
    """
    Default status bar provider using InterfaceTheme.

    This is the standard status bar implementation that uses
    templates from InterfaceTheme for rendering.
    """

    def __init__(self, theme: InterfaceTheme | None = None):
        """
        Initialize the default status provider.

        Args:
            theme: Theme configuration. Uses default if not provided.
        """
        # Import here to avoid circular import
        from kora.interface.theme import InterfaceTheme
        self.theme = theme or InterfaceTheme()

    def get_idle_text(self, context: StatusContext) -> str:
        return self.theme.status_idle_template.format(
            agent_icon=self.theme.agent_icon,
            mode=context.mode,
            sep=self.theme.status_separator,
        )

    def get_running_text(
        self,
        context: StatusContext,
        frame: str,
        message: str,
        details_hint: str,
    ) -> str:
        return self.theme.status_running_template.format(
            frame=frame,
            message=message or context.tool_summary or "",
            details_hint=f" {details_hint}" if details_hint else "",
        )

    def get_interrupted_text(self, context: StatusContext) -> str:
        return self.theme.status_interrupted_template.format(
            interrupt_icon=self.theme.interrupt_icon,
        )

    def get_error_text(self, context: StatusContext, error: str) -> str:
        message = error[: self.theme.max_message_length]
        return self.theme.status_error_template.format(
            error_icon=self.theme.error_icon,
            message=message,
        )


# Legacy frames for backwards compatibility
THINKING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


@dataclass
class StatusBarManager:
    """
    Tracks REPL status text for the bottom toolbar.

    This object is pure state + text rendering. It does not directly
    move the terminal cursor or redraw the screen.
    """

    stream: TextIO | None = None
    mode: str = "chat"
    state: StatusBarState = StatusBarState.IDLE
    message: str = ""
    activity_log: list[str] = field(default_factory=list)
    activity_expanded: bool = False

    # New: pluggable status provider
    provider: StatusProvider = field(default_factory=DefaultStatusProvider)
    context: StatusContext = field(default_factory=StatusContext)

    def __post_init__(self) -> None:
        if self.stream is None:
            self.stream = sys.stdout
        # Use theme's spinner frames if provider has theme
        if isinstance(self.provider, DefaultStatusProvider):
            frames = list(self.provider.theme.spinner_frames)
        else:
            frames = THINKING_FRAMES
        self._frame_cycle = itertools.cycle(range(len(frames)))
        self._cached_frames = frames
        self._last_frame_at = 0.0
        self._cached_frame = frames[0]

    @property
    def is_running(self) -> bool:
        return self.state == StatusBarState.RUNNING

    def set_mode(self, mode: str) -> None:
        """Set the current mode."""
        self.mode = mode
        self.context.mode = mode

    def set_running(self, running: bool, message: str = "") -> None:
        """Set the running state."""
        if running:
            self.state = StatusBarState.RUNNING
            # Get thinking_message from theme if available
            default_message = "Thinking..."
            if isinstance(self.provider, DefaultStatusProvider):
                default_message = self.provider.theme.thinking_message
            self.message = message or default_message
            self.context.tool_summary = self.message
            self._last_frame_at = 0.0
        else:
            self.state = StatusBarState.IDLE
            self.message = ""
            self.context.tool_summary = None

    def hide(self) -> None:
        """Hide the status bar while long-running output is in progress."""
        self.state = StatusBarState.HIDDEN
        self.message = ""

    def set_interrupted(self) -> None:
        """Set the interrupted state."""
        self.state = StatusBarState.INTERRUPTED
        self.message = ""

    def set_error(self, message: str = "") -> None:
        """Set the error state."""
        self.state = StatusBarState.ERROR
        self.message = message

    def append_activity(self, line: str) -> None:
        """Append one activity entry to the collapsible log."""
        text = line.strip()
        if not text:
            return
        self.activity_log.append(text)
        if len(self.activity_log) > 200:
            self.activity_log = self.activity_log[-200:]
        self.context.activity_count = len(self.activity_log)

    def clear_activity_log(self) -> None:
        """Clear the recorded activity log."""
        self.activity_log.clear()
        self.context.activity_count = 0

    def get_activity_log(self) -> list[str]:
        """Return the recorded activity log entries."""
        return list(self.activity_log)

    def toggle_activity_expanded(self) -> None:
        """Toggle the expanded activity panel."""
        self.activity_expanded = not self.activity_expanded

    def set_activity_expanded(self, expanded: bool) -> None:
        """Set expanded/collapsed state for the activity panel."""
        self.activity_expanded = expanded

    def _current_frame(self) -> str:
        """Get the current animation frame without mutating terminal state."""
        now = time.monotonic()
        if self._last_frame_at == 0.0 or now - self._last_frame_at >= 0.08:
            self._cached_frame = self._cached_frames[next(self._frame_cycle)]
            self._last_frame_at = now
        return self._cached_frame

    def _render_line(self) -> str:
        """Render the status bar content using the provider."""
        main_line = ""
        if self.state == StatusBarState.RUNNING:
            frame = self._current_frame()
            details_hint = ""
            if self.context.activity_count:
                action = "collapse" if self.activity_expanded else "expand"
                details_hint = f"[Ctrl+O {action} {self.context.activity_count} logs]"
            main_line = self.provider.get_running_text(
                self.context,
                frame,
                self.message,
                details_hint,
            )
        elif self.state == StatusBarState.HIDDEN:
            main_line = ""
        elif self.state == StatusBarState.INTERRUPTED:
            main_line = self.provider.get_interrupted_text(self.context)
        elif self.state == StatusBarState.ERROR:
            main_line = self.provider.get_error_text(self.context, self.message)
        else:
            main_line = self.provider.get_idle_text(self.context)

        if self.activity_expanded and self.activity_log:
            panel_lines = ["", " Activity", " " + "─" * 16]
            panel_lines.extend(f" {line}" for line in self.activity_log[-12:])
            return "\n".join([main_line, *panel_lines]) if main_line else "\n".join(panel_lines)

        return main_line

    def get_text(self) -> str:
        """Get status bar text (for bottom_toolbar callback)."""
        return self._render_line()

    def animate(self) -> None:
        """Kept for backwards compatibility; no direct redraw now."""
        return None

    def clear(self) -> None:
        """Kept for backwards compatibility; no direct redraw now."""
        return None


_status_bar_manager: StatusBarManager | None = None


def get_status_bar() -> StatusBarManager:
    """Get the global status bar manager."""
    global _status_bar_manager
    if _status_bar_manager is None:
        _status_bar_manager = StatusBarManager()
    return _status_bar_manager


__all__ = [
    "StatusBarState",
    "StatusBarManager",
    "StatusContext",
    "StatusProvider",
    "DefaultStatusProvider",
    "get_status_bar",
    "THINKING_FRAMES",
]
