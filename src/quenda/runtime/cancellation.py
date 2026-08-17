"""Run-scoped cooperative cancellation primitives."""

from __future__ import annotations

import threading
from collections.abc import Callable
from enum import StrEnum


class CancellationReason(StrEnum):
    """Why a Run was asked to stop."""

    USER_CANCEL = "user_cancel"
    TIMEOUT = "timeout"
    PARENT_CANCEL = "parent_cancel"


class CancellationToken:
    """Thread-safe cancellation state owned by exactly one Run."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._reason = CancellationReason.USER_CANCEL
        self._lock = threading.Lock()
        self._callbacks: set[Callable[[], None]] = set()

    def cancel(
        self,
        reason: CancellationReason = CancellationReason.USER_CANCEL,
    ) -> None:
        """Request cancellation without affecting any other Run."""
        with self._lock:
            self._reason = reason
            self._cancelled.set()
            callbacks = tuple(self._callbacks)
        for callback in callbacks:
            try:
                callback()
            except Exception:
                # Cancellation remains best-effort even if one resource has
                # already closed or rejects cross-thread cleanup.
                pass

    def add_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Run callback on cancellation and return an unregister function."""
        with self._lock:
            if self._cancelled.is_set():
                invoke_now = True
            else:
                self._callbacks.add(callback)
                invoke_now = False
        if invoke_now:
            try:
                callback()
            except Exception:
                pass

        def unregister() -> None:
            with self._lock:
                self._callbacks.discard(callback)

        return unregister

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._cancelled.is_set()

    @property
    def reason(self) -> CancellationReason:
        """Return the cancellation reason."""
        with self._lock:
            return self._reason


__all__ = ["CancellationReason", "CancellationToken"]
