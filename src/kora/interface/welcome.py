"""
Welcome message provider for Kora Interface layer.

Provides customizable startup messages for agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kora.interface.theme import InterfaceTheme


@dataclass
class WelcomeContext:
    """
    Context information for welcome message rendering.

    Provides all available context that welcome providers can use
    to generate startup messages.
    """

    agent_name: str
    workspace_id: str
    workspace_path: Path
    session_id: str
    provider: str
    model: str
    instructions: str = "Type your message and press Enter. Type '/' to see commands."


class WelcomeProvider(Protocol):
    """
    Protocol for welcome message providers.

    Implement this protocol to customize the startup message
    displayed when an agent session begins.
    """

    def render(self, context: WelcomeContext) -> str:
        """
        Render the welcome message.

        Args:
            context: Context with agent/session information.

        Returns:
            Formatted welcome message string.
        """
        ...


class DefaultWelcomeProvider:
    """
    Default welcome message provider using InterfaceTheme.

    This is the standard welcome message implementation that uses
    templates from InterfaceTheme for rendering.
    """

    def __init__(self, theme: InterfaceTheme | None = None):
        """
        Initialize the default welcome provider.

        Args:
            theme: Theme configuration. Uses default if not provided.
        """
        from kora.interface.theme import InterfaceTheme
        self.theme = theme or InterfaceTheme()

    def render(self, context: WelcomeContext) -> str:
        """Render welcome message using theme template."""
        return self.theme.welcome_template.format(
            agent_icon=self.theme.agent_icon,
            agent_name=context.agent_name,
            workspace_id=context.workspace_id,
            workspace_path=context.workspace_path,
            session_id=context.session_id,
            provider=context.provider,
            model=context.model,
            instructions=context.instructions,
        )


class MinimalWelcomeProvider:
    """
    Minimal welcome provider for CI/CD environments.

    Outputs a single line with essential information.
    """

    def __init__(self, theme: InterfaceTheme | None = None):
        """Initialize the minimal welcome provider."""
        from kora.interface.theme import InterfaceTheme
        self.theme = theme or InterfaceTheme()

    def render(self, context: WelcomeContext) -> str:
        """Render minimal welcome message."""
        return f"{context.agent_name} | {context.workspace_id} | {context.provider}/{context.model}\n"


class SilentWelcomeProvider:
    """
    Silent welcome provider that outputs nothing.

    Useful for completely quiet operation.
    """

    def render(self, context: WelcomeContext) -> str:
        """Return empty string."""
        return ""


__all__ = [
    "WelcomeContext",
    "WelcomeProvider",
    "DefaultWelcomeProvider",
    "MinimalWelcomeProvider",
    "SilentWelcomeProvider",
]
