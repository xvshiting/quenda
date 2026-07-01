"""
Interrupt mechanism for Kora.

Provides a way to interrupt long-running agent executions from the UI layer.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, auto


class InterruptReason(Enum):
    """Reason for interruption."""

    USER_CANCEL = auto()  # User pressed ESC/Ctrl+C
    TIMEOUT = auto()  # Execution timed out
    ERROR = auto()  # An error occurred


@dataclass
class InterruptSignal:
    """
    Thread-safe interrupt signal.

    Used to communicate interruption from UI layer to Runtime layer.
    """

    _reason: InterruptReason | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def set(self, reason: InterruptReason = InterruptReason.USER_CANCEL) -> None:
        """Set the interrupt signal."""
        with self._lock:
            self._reason = reason

    def is_set(self) -> bool:
        """Check if interrupt is signaled."""
        with self._lock:
            return self._reason is not None

    def get_reason(self) -> InterruptReason | None:
        """Get the interrupt reason."""
        with self._lock:
            return self._reason

    def clear(self) -> None:
        """Clear the interrupt signal."""
        with self._lock:
            self._reason = None


# Global interrupt signal (shared across the process)
_interrupt_signal = InterruptSignal()


def get_interrupt_signal() -> InterruptSignal:
    """Get the global interrupt signal."""
    return _interrupt_signal


def is_interrupted() -> bool:
    """Check if execution should be interrupted."""
    return _interrupt_signal.is_set()


def interrupt(reason: InterruptReason = InterruptReason.USER_CANCEL) -> None:
    """Signal an interruption."""
    _interrupt_signal.set(reason)


def clear_interrupt() -> None:
    """Clear the interrupt signal."""
    _interrupt_signal.clear()


__all__ = [
    "InterruptReason",
    "InterruptSignal",
    "get_interrupt_signal",
    "is_interrupted",
    "interrupt",
    "clear_interrupt",
]
