"""Thread-local diagnostics for provider retry activity."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryNotice:
    """A provider request is about to be retried."""

    attempt: int
    max_attempts: int
    delay_seconds: float
    error_type: str
    error_message: str


RetryObserver = Callable[[RetryNotice], None]
_retry_observer: ContextVar[RetryObserver | None] = ContextVar(
    "quenda_retry_observer",
    default=None,
)


def set_retry_observer(observer: RetryObserver) -> Token[RetryObserver | None]:
    """Install an observer for the current model-call context."""
    return _retry_observer.set(observer)


def reset_retry_observer(token: Token[RetryObserver | None]) -> None:
    """Restore the previous observer."""
    _retry_observer.reset(token)


def notify_retry(notice: RetryNotice) -> None:
    """Publish a retry notice when the caller requested diagnostics."""
    observer = _retry_observer.get()
    if observer is not None:
        observer(notice)
