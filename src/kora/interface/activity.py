"""
Terminal activity indicator for Kora Interface layer.

Provides protocols and implementations for activity indicators that keep
the terminal feeling alive while the model is thinking or tools are running.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, TextIO, TypeVar

if TYPE_CHECKING:
    from kora.interface.theme import InterfaceTheme

T = TypeVar("T")

# Legacy frames for backwards compatibility
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


class ActivityIndicator(Protocol):
    """
    Protocol for activity indicators.

    An activity indicator shows progress or activity during long-running
    operations. Implementations can range from simple spinners to progress
    bars or silent (no output) indicators.

    All methods should be safe to call from any thread.
    """

    def start(self) -> None:
        """
        Start displaying the indicator.

        Should be idempotent - calling start() when already started
        should have no effect.
        """
        ...

    def stop(self) -> None:
        """
        Stop displaying the indicator and clear any output.

        Should be idempotent - calling stop() when already stopped
        should have no effect.
        """
        ...

    def update(self, message: str) -> None:
        """
        Update the indicator message.

        Args:
            message: New message to display.
        """
        ...

    @property
    def is_running(self) -> bool:
        """
        Check if the indicator is currently running.

        Returns:
            True if the indicator is active and displaying.
        """
        ...


@dataclass
class InterruptListenerHandle:
    """Handle for a background ESC listener."""

    thread: threading.Thread
    stop_flag: threading.Event

    def stop(self) -> None:
        """Signal the listener to stop."""
        self.stop_flag.set()


@dataclass
class SpinnerIndicator:
    """
    Animated spinner activity indicator.

    This is the default implementation that shows a rotating spinner
    animation in the terminal. It uses InterfaceTheme for configuration.

    The indicator is intentionally simple:
    - Only animates when the output stream is a TTY
    - Writes a single status line that updates in place
    - Can be stopped from another thread safely
    - Shows hint about interrupting (configurable via theme)
    - Ctrl+C to interrupt (ESC listener disabled due to prompt_toolkit conflict)
    """

    message: str = "Working..."
    stream: TextIO | None = None
    theme: InterfaceTheme | None = None
    interval: float | None = None
    enabled: bool | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    _started: bool = field(default=False, init=False)
    _frame_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # Import here to avoid circular import
        from kora.interface.theme import InterfaceTheme

        self._theme = self.theme or InterfaceTheme()
        if self.stream is None:
            self.stream = sys.stdout
        if self.interval is None:
            self.interval = self._theme.spinner_interval
        if self.enabled is None:
            self.enabled = bool(getattr(self.stream, "isatty", lambda: False)())
        self._frames = list(self._theme.spinner_frames)

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        """Start animating the status line."""
        if not self.enabled or self._started:
            return

        self._started = True
        self._stop_event.clear()
        self._frame_count = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop animating and clear the status line."""
        if not self._started:
            return

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        self._clear_line()
        self._started = False

    def update(self, message: str) -> None:
        """Update the message shown by the indicator."""
        with self._lock:
            self.message = message

    def _run(self) -> None:
        frame_index = 0
        assert self.interval is not None  # for type checker
        while not self._stop_event.wait(self.interval):
            self._write_frame(self._frames[frame_index % len(self._frames)])
            frame_index += 1
            self._frame_count = frame_index

    def _write_frame(self, frame: str) -> None:
        with self._lock:
            # Determine whether to show ESC hint
            show_hint = False
            hint = ""
            if self._theme.show_esc_hint:
                if self._theme.esc_hint_always:
                    # Always show hint
                    show_hint = True
                else:
                    # Show hint every N frames
                    show_hint = (
                        self._frame_count > 0
                        and self._frame_count % self._theme.esc_hint_interval == 0
                    )

            hint = f" {self._theme.esc_hint_text}" if show_hint else ""
            text = f"\r{frame} {self.message}{hint}"
            padding = max(0, 60 - len(text))  # Fixed width for clearing
            assert self.stream is not None
            self.stream.write(text + (" " * padding))
            self.stream.flush()

    def _clear_line(self) -> None:
        assert self.stream is not None
        self.stream.write("\r" + (" " * 70) + "\r")
        self.stream.flush()


@dataclass
class SilentIndicator:
    """
    Silent activity indicator that produces no output.

    Useful for CI/CD environments or when output should be minimal.
    Implements the ActivityIndicator protocol but all operations are no-ops.
    """

    message: str = ""
    _running: bool = field(default=False, init=False)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def update(self, message: str) -> None:
        self.message = message


@dataclass
class ProgressIndicator:
    """
    Progress bar indicator for operations with known total.

    This is a stub for future expansion. When fully implemented, it will
    show a progress bar like: [████████░░] 80% Running tests...

    Current implementation falls back to spinner-like behavior.
    """

    total: int = 100
    message: str = "Working..."
    stream: TextIO | None = None
    theme: InterfaceTheme | None = None
    _current: int = field(default=0, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _started: bool = field(default=False, init=False)

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def progress(self) -> float:
        """Get current progress as a float between 0 and 1."""
        if self.total <= 0:
            return 0.0
        return min(1.0, self._current / self.total)

    def advance(self, amount: int = 1) -> None:
        """Advance the progress by the given amount."""
        self._current = min(self.total, self._current + amount)

    def start(self) -> None:
        """Start the indicator."""
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        # For now, just show a static message
        # TODO: Implement actual progress bar rendering

    def stop(self) -> None:
        """Stop the indicator."""
        if not self._started:
            return
        self._stop_event.set()
        self._started = False

    def update(self, message: str) -> None:
        """Update the message."""
        self.message = message


# Legacy alias for backwards compatibility
TerminalActivityIndicator = SpinnerIndicator


def run_with_activity_indicator(
    func: Callable[[], T],
    *,
    message: str = "Working...",
    stream: TextIO | None = None,
    theme: InterfaceTheme | None = None,
) -> T:
    """
    Run a blocking callable while showing a terminal activity indicator.

    If the output stream is not a TTY, the callable runs directly without
    animation.

    Args:
        func: The function to run.
        message: Initial message to display.
        stream: Output stream. Defaults to sys.stdout.
        theme: Theme configuration. Defaults to InterfaceTheme().

    Returns:
        The result of the function.
    """
    indicator = SpinnerIndicator(message=message, stream=stream or sys.stdout, theme=theme)
    indicator.start()
    try:
        return func()
    finally:
        indicator.stop()


def start_interrupt_listener() -> InterruptListenerHandle | None:
    """
    Start a background thread that listens for ESC key.

    Returns the thread object, or None if not supported.
    The thread will call interrupt() when ESC is pressed.

    Note: The thread runs as daemon and will not prevent program exit.
    Terminal settings are automatically restored when the listener
    detects an interrupt or the program exits.
    """
    # Check if we're on a TTY
    if not sys.stdin.isatty():
        return None

    # Check platform - Unix only
    try:
        import termios
        import tty
    except ImportError:
        # Windows doesn't have termios
        return None

    # Thread-local flag to signal stop
    stop_flag = threading.Event()

    def listen() -> None:
        import select

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            while not stop_flag.is_set():
                # Non-blocking check with timeout
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    char = sys.stdin.read(1)
                    if char == "\x1b":  # ESC
                        from kora.utils.interrupt import interrupt

                        interrupt()
                        break
        except Exception:
            pass
        finally:
            # Always restore terminal settings
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    return InterruptListenerHandle(thread=thread, stop_flag=stop_flag)


__all__ = [
    "ActivityIndicator",
    "SpinnerIndicator",
    "SilentIndicator",
    "ProgressIndicator",
    "TerminalActivityIndicator",  # Legacy alias
    "InterruptListenerHandle",
    "run_with_activity_indicator",
    "start_interrupt_listener",
    "SPINNER_FRAMES",  # Legacy constant
]
