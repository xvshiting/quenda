"""
Interaction request system for Kora Host.

This provides a structured way for Host/LLM flows to request user
interaction such as choices, confirmations, or free-form input.

The design mirrors the command system:
- A small protocol for interaction kinds
- A registry for discovery and extension
- Built-in interactions plus agent-local extensions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable
from uuid import uuid4

if TYPE_CHECKING:
    from quenda.runtime.agent import Agent
    from quenda.runtime.session import Session
    from quenda.kernel.model import Model
    from quenda.host.context import ContextRebuilder
    from quenda.host.storage import Storage


class InteractionKind(StrEnum):
    """Built-in interaction kinds supported by Kora."""

    CHOICE = "choice"
    CONFIRM = "confirm"
    INPUT = "input"
    MENU = "menu"


@dataclass(frozen=True)
class InteractionOption:
    """A single selectable option for an interaction request."""

    id: str
    label: str
    description: str = ""
    value: Any = None
    is_default: bool = False


@dataclass
class InteractionRequest:
    """
    Structured request for human interaction.

    This is the Host-side contract that can be produced by LLM-guided
    flows, commands, or policy logic.
    """

    kind: str
    title: str
    message: str = ""
    options: list[InteractionOption] = field(default_factory=list)
    default_option_id: str | None = None
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "host"
    id: str = field(default_factory=lambda: str(uuid4()))

    def option_ids(self) -> set[str]:
        """Return the set of option IDs currently present."""
        return {option.id for option in self.options}

    def default_option(self) -> InteractionOption | None:
        """Return the default option, if any."""
        if self.default_option_id is not None:
            for option in self.options:
                if option.id == self.default_option_id:
                    return option

        for option in self.options:
            if option.is_default:
                return option

        return None


@dataclass(frozen=True)
class InteractionResponse:
    """
    Human response to an interaction request.

    The response is intentionally small and serializable so Host can
    persist it, replay it, or pass it into later control flow.
    """

    request_id: str
    kind: str
    status: Literal["ok", "cancelled", "error"]
    selected_option_id: str | None = None
    value: Any = None
    message: str = ""


@dataclass
class InteractionContext:
    """
    Context available to interaction handlers.

    This mirrors the command context shape so interactions can inspect
    session state, agent state, and runtime configuration.
    """

    session: Session
    agent: Agent | None = None
    model: Model | None = None
    storage: Storage | None = None
    context_builder: ContextRebuilder | None = None

    def get_system_prompt(self) -> str | None:
        """Get the current system prompt."""
        return self.session.system_prompt

    def get_tools(self) -> list:
        """Get available tools."""
        if self.agent is not None:
            return self.agent.tools
        return []

    def get_mode(self) -> str:
        """Get the current interaction mode."""
        return self.session.mode

    def set_mode(self, mode: str) -> None:
        """Set the interaction mode."""
        self.session.mode = mode


@runtime_checkable
class Interaction(Protocol):
    """Protocol for interaction kinds."""

    @property
    def kind(self) -> str:
        """The interaction kind, e.g. 'choice' or 'confirm'."""
        ...

    @property
    def description(self) -> str:
        """Short description shown in help/debug output."""
        ...

    @property
    def usage(self) -> str:
        """Usage string for this interaction kind."""
        ...

    def validate(self, request: InteractionRequest, context: InteractionContext) -> list[str]:
        """
        Validate a request before it is rendered or accepted.

        Returns:
            A list of validation errors. Empty means valid.
        """
        ...

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        """
        Return candidate options for this request.

        Interactions can derive or normalize options from request/context.
        """
        ...


class InteractionRegistry:
    """
    Central registry for interaction kinds.

    This is intentionally similar to CommandRegistry so agent packages
    can extend the control surface with the same loading pattern.
    """

    def __init__(self) -> None:
        self._interactions: dict[str, Interaction] = {}

    def register(self, interaction: Interaction) -> None:
        """Register an interaction kind."""
        self._interactions[interaction.kind] = interaction

    def get(self, kind: str) -> Interaction | None:
        """Get an interaction by kind."""
        return self._interactions.get(kind)

    def has(self, kind: str) -> bool:
        """Check whether an interaction kind is registered."""
        return kind in self._interactions

    def list_interactions(self) -> list[Interaction]:
        """List all registered interaction kinds."""
        return list(self._interactions.values())

    def validate(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[str]:
        """Validate a request with the registered handler, if any."""
        interaction = self.get(request.kind)
        if interaction is None:
            return [f"Unknown interaction kind: {request.kind}"]
        return interaction.validate(request, context)

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        """Get normalized suggestions for a request."""
        interaction = self.get(request.kind)
        if interaction is None:
            return list(request.options)
        return interaction.get_suggestions(request, context)

    def __contains__(self, kind: str) -> bool:
        return kind in self._interactions

    def __len__(self) -> int:
        return len(self._interactions)


class ChoiceInteraction:
    """Built-in choice interaction."""

    @property
    def kind(self) -> str:
        return InteractionKind.CHOICE.value

    @property
    def description(self) -> str:
        return "Present a list of choices for the user to select from"

    @property
    def usage(self) -> str:
        return "choice"

    def validate(self, request: InteractionRequest, context: InteractionContext) -> list[str]:
        errors: list[str] = []
        if not request.options:
            errors.append("choice interaction requires at least one option")
        if request.default_option_id is not None and request.default_option_id not in request.option_ids():
            errors.append(f"default_option_id `{request.default_option_id}` is not in options")
        return errors

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        return list(request.options)


class ConfirmInteraction:
    """Built-in confirmation interaction."""

    @property
    def kind(self) -> str:
        return InteractionKind.CONFIRM.value

    @property
    def description(self) -> str:
        return "Ask the user to confirm or cancel an action"

    @property
    def usage(self) -> str:
        return "confirm"

    def validate(self, request: InteractionRequest, context: InteractionContext) -> list[str]:
        errors: list[str] = []
        if request.options and len(request.options) > 2:
            errors.append("confirm interaction should not define more than two options")
        return errors

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        if request.options:
            return list(request.options)

        return [
            InteractionOption(id="yes", label="Yes", description="Proceed", is_default=True),
            InteractionOption(id="no", label="No", description="Cancel"),
        ]


class InputInteraction:
    """Built-in free-form input interaction."""

    @property
    def kind(self) -> str:
        return InteractionKind.INPUT.value

    @property
    def description(self) -> str:
        return "Ask the user for free-form text input"

    @property
    def usage(self) -> str:
        return "input"

    def validate(self, request: InteractionRequest, context: InteractionContext) -> list[str]:
        return []

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        return list(request.options)


class MenuInteraction:
    """Built-in menu interaction."""

    @property
    def kind(self) -> str:
        return InteractionKind.MENU.value

    @property
    def description(self) -> str:
        return "Display a menu-style list of selectable items"

    @property
    def usage(self) -> str:
        return "menu"

    def validate(self, request: InteractionRequest, context: InteractionContext) -> list[str]:
        if not request.options:
            return ["menu interaction requires at least one option"]
        return []

    def get_suggestions(
        self,
        request: InteractionRequest,
        context: InteractionContext,
    ) -> list[InteractionOption]:
        return list(request.options)


def create_default_registry() -> InteractionRegistry:
    """Create an InteractionRegistry with built-in interaction kinds."""
    registry = InteractionRegistry()
    registry.register(ChoiceInteraction())
    registry.register(ConfirmInteraction())
    registry.register(InputInteraction())
    registry.register(MenuInteraction())
    return registry


__all__ = [
    "InteractionKind",
    "InteractionOption",
    "InteractionRequest",
    "InteractionResponse",
    "InteractionContext",
    "Interaction",
    "InteractionRegistry",
    "ChoiceInteraction",
    "ConfirmInteraction",
    "InputInteraction",
    "MenuInteraction",
    "create_default_registry",
]
