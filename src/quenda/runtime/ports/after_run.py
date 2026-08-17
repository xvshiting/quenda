"""Injected Host work that runs after a successful Runtime Run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from quenda.kernel.types import Message
    from quenda.runtime.events import AnyEvent, RunCompleted


@dataclass(frozen=True)
class AfterRunContext:
    """Immutable inputs available to one isolated after-Run handler."""

    session_id: str
    agent_name: str
    messages: tuple[Message, ...]
    completed: RunCompleted


class AfterRunHandler(Protocol):
    """Perform optional Host maintenance without changing Run completion."""

    async def process(self, context: AfterRunContext) -> list[AnyEvent]:
        """Return observable maintenance events; failures are isolated by Runtime."""
        ...


__all__ = ["AfterRunContext", "AfterRunHandler"]
