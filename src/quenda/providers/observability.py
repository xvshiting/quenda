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


@dataclass(frozen=True)
class StreamDeltaNotice:
    """One text fragment received from a streaming model response."""

    content: str


RetryObserver = Callable[[RetryNotice], None]
_retry_observer: ContextVar[RetryObserver | None] = ContextVar(
    "quenda_retry_observer",
    default=None,
)
StreamDeltaObserver = Callable[[StreamDeltaNotice], None]
_stream_delta_observer: ContextVar[StreamDeltaObserver | None] = ContextVar(
    "quenda_stream_delta_observer",
    default=None,
)
CancellationProbe = Callable[[], bool]
CancellationRegistrar = Callable[[Callable[[], None]], Callable[[], None]]
_cancellation_probe: ContextVar[CancellationProbe | None] = ContextVar(
    "quenda_cancellation_probe", default=None
)
_cancellation_registrar: ContextVar[CancellationRegistrar | None] = ContextVar(
    "quenda_cancellation_registrar", default=None
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


def set_stream_delta_observer(
    observer: StreamDeltaObserver,
) -> Token[StreamDeltaObserver | None]:
    """Install a text-delta observer for the current model-call context."""
    return _stream_delta_observer.set(observer)


def reset_stream_delta_observer(token: Token[StreamDeltaObserver | None]) -> None:
    """Restore the previous text-delta observer."""
    _stream_delta_observer.reset(token)


def notify_stream_delta(content: str) -> None:
    """Publish streamed text when the caller requested incremental output."""
    observer = _stream_delta_observer.get()
    if observer is not None and content:
        observer(StreamDeltaNotice(content=content))


def set_cancellation_context(
    probe: CancellationProbe,
    registrar: CancellationRegistrar,
) -> tuple[Token[CancellationProbe | None], Token[CancellationRegistrar | None]]:
    """Expose one Run's cancellation state inside its provider thread."""
    return _cancellation_probe.set(probe), _cancellation_registrar.set(registrar)


def reset_cancellation_context(
    tokens: tuple[Token[CancellationProbe | None], Token[CancellationRegistrar | None]],
) -> None:
    """Restore the previous provider cancellation context."""
    _cancellation_registrar.reset(tokens[1])
    _cancellation_probe.reset(tokens[0])


def cancellation_requested() -> bool:
    """Return whether the current provider call has been cancelled."""
    probe = _cancellation_probe.get()
    return probe() if probe is not None else False


def register_cancellation_callback(callback: Callable[[], None]) -> Callable[[], None]:
    """Register cleanup for the active Run, if it supplied cancellation state."""
    registrar = _cancellation_registrar.get()
    return registrar(callback) if registrar is not None else (lambda: None)
