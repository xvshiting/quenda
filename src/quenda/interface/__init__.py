"""
Interface layer for Kora.

The interface layer is responsible for:
- Rendering Runtime events to human-readable output
- REPL interaction (input, completion, hints)
- Terminal output formatting (markdown-lite)
- Interactive selection UI (arrow-key navigation, custom input)
- Status bar display
- Activity indicators
- Theme configuration

This is the presentation layer - handles UI concerns only.
"""

# Theme configuration
from quenda.interface.theme import InterfaceTheme

# Status bar
from quenda.interface.status import (
    StatusBarManager,
    StatusBarState,
    StatusContext,
    StatusProvider,
    DefaultStatusProvider,
    get_status_bar,
    THINKING_FRAMES,
)

# Activity indicators
from quenda.interface.activity import (
    ActivityIndicator,
    SpinnerIndicator,
    SilentIndicator,
    ProgressIndicator,
    TerminalActivityIndicator,  # Legacy alias
    InterruptListenerHandle,
    run_with_activity_indicator,
    start_interrupt_listener,
    SPINNER_FRAMES,
)

# Console rendering
from quenda.interface.console import ConsoleRenderer

# Welcome message
from quenda.interface.welcome import (
    WelcomeContext,
    WelcomeProvider,
    DefaultWelcomeProvider,
    MinimalWelcomeProvider,
    SilentWelcomeProvider,
)

# Event handling
from quenda.interface.events import (
    EventHandler,
    StreamingEventHandler,
    ActivityEventHandler,
    ProgressEventHandler,
    BatchEventHandler,
    CollectingEventHandler,
    CompositeEventHandler,
)

# Interaction rendering
from quenda.interface.interaction import render_interaction_request

# Interactive selection
from quenda.interface.selector import select_option

# REPL input
from quenda.interface.repl import (
    ReplInput,
    print_command_menu,
    create_repl_input,
    HAS_PROMPT_TOOLKIT,
)

# Markdown rendering
from quenda.interface.markdown import (
    MarkdownLiteRenderer,
    render_markdown_lite,
)

__all__ = [
    # Theme
    "InterfaceTheme",
    # Status bar
    "StatusBarManager",
    "StatusBarState",
    "StatusContext",
    "StatusProvider",
    "DefaultStatusProvider",
    "get_status_bar",
    "THINKING_FRAMES",
    # Activity indicators
    "ActivityIndicator",
    "SpinnerIndicator",
    "SilentIndicator",
    "ProgressIndicator",
    "TerminalActivityIndicator",
    "InterruptListenerHandle",
    "run_with_activity_indicator",
    "start_interrupt_listener",
    "SPINNER_FRAMES",
    # Console rendering
    "ConsoleRenderer",
    # Welcome
    "WelcomeContext",
    "WelcomeProvider",
    "DefaultWelcomeProvider",
    "MinimalWelcomeProvider",
    "SilentWelcomeProvider",
    # Event handling
    "EventHandler",
    "StreamingEventHandler",
    "ActivityEventHandler",
    "ProgressEventHandler",
    "BatchEventHandler",
    "CollectingEventHandler",
    "CompositeEventHandler",
    # Interaction
    "render_interaction_request",
    "select_option",
    # REPL
    "ReplInput",
    "print_command_menu",
    "create_repl_input",
    "HAS_PROMPT_TOOLKIT",
    # Markdown
    "MarkdownLiteRenderer",
    "render_markdown_lite",
]
