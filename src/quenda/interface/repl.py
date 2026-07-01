"""
REPL with status bar for Kora.

Uses prompt_toolkit's bottom toolbar for a proper status bar that sits
below the input area, with dynamic thinking animation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path
    from quenda.host.commands import CommandRegistry, CommandCandidate
    from quenda.host.repl import ReplRuntime

from quenda.interface.status import get_status_bar

# Try to import prompt_toolkit for enhanced REPL
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout.processors import BeforeInput
    from prompt_toolkit.styles import Style

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    Completer = object  # type: ignore[misc,assignment]
    Completion = object  # type: ignore[misc,assignment]
    Style = object  # type: ignore[misc,assignment]

# Animation frames for thinking state
THINKING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class ReplInput(Protocol):
    """Protocol for REPL input handlers."""

    def get_input(self, prompt: str) -> str:
        """Get user input with the given prompt."""
        ...


class BasicInput:
    """Basic REPL input without prompt_toolkit."""

    def get_input(self, prompt: str) -> str:
        """Get user input using basic input()."""
        return input(prompt)


def format_activity_log(status_bar) -> str:
    """Format the activity log panel contents."""
    entries = getattr(status_bar, "get_activity_log", lambda: [])()
    if not entries:
        return "No activity log available."

    lines = ["", "Activity Log", "-" * 12]
    lines.extend(entries)
    lines.append("-" * 12)
    return "\n".join(lines)


def print_command_menu(registry: CommandRegistry) -> None:
    """Print available commands."""
    commands = registry.list_commands()
    if not commands:
        print("No commands available.")
        return

    print("\nAvailable commands:\n")
    for cmd in sorted(commands, key=lambda c: c.name):
        print(f"  /{cmd.name:<12} {cmd.description}")
    print("")


if HAS_PROMPT_TOOLKIT:

    class CommandCompleter(Completer):
        """
        Completer for slash commands with two-stage completion.

        Stage 1: Complete command names (e.g., /mod -> /mode)
        Stage 2: Show candidates for command arguments (e.g., /mode -> [chat, code, architect])

        This completer consumes candidates from ReplRuntime, which delegates to
        individual commands via their get_candidates() method.
        """

        def __init__(
            self,
            registry: CommandRegistry,
            runtime: ReplRuntime | None = None,
        ) -> None:
            self._registry = registry
            self._runtime = runtime

        def get_completions(self, document, complete_event):
            """Get completions for current input."""
            text = document.text_before_cursor

            # Only complete slash commands
            if not text.startswith("/"):
                return

            # Parse command and args
            if " " in text[1:]:
                # Stage 2: Argument completion
                cmd_name, _, args = text[1:].partition(" ")
                yield from self._get_argument_completions(cmd_name, args, text)
            else:
                # Stage 1: Command name completion
                yield from self._get_command_completions(text)

        def _get_command_completions(self, text: str):
            """Get completions for command names."""
            cmd_partial = text[1:].lower()

            # If just "/", show all commands
            if not cmd_partial:
                for cmd in sorted(self._registry.list_commands(), key=lambda c: c.name):
                    yield Completion(
                        f"/{cmd.name}",
                        start_position=-1,
                        display=f"/{cmd.name}",
                        display_meta=cmd.description,
                    )
                return

            # Complete partial command names
            for cmd in self._registry.list_commands():
                if cmd.name.startswith(cmd_partial):
                    yield Completion(
                        f"/{cmd.name}",
                        start_position=-len(text),
                        display=f"/{cmd.name}",
                        display_meta=cmd.description,
                    )

        def _get_argument_completions(self, cmd_name: str, args: str, text: str):
            """Get completions for command arguments."""
            # Try to get candidates from runtime
            if self._runtime is not None:
                try:
                    candidates = self._runtime.get_command_candidates(cmd_name, args)
                    for candidate in candidates:
                        # Calculate start position based on current args
                        # We want to replace the partial argument, not the whole text
                        yield Completion(
                            candidate.value,
                            start_position=-len(args) if args else 0,
                            display=candidate.label,
                            display_meta=candidate.description,
                        )
                    return
                except Exception:
                    pass  # Fall back to legacy completion

            # Legacy: try command's get_completions method
            command = self._registry.get(cmd_name)
            if command is None:
                return

            # Get legacy completions (returns strings)
            legacy_completions = getattr(command, "get_completions", lambda x: [])(args)
            for completion in legacy_completions:
                yield Completion(
                    completion,
                    start_position=-len(args) if args else 0,
                    display=completion,
                )

    class PromptToolkitInput:
        """REPL input using prompt_toolkit with a lightweight status strip."""

        def __init__(
            self,
            registry: CommandRegistry,
            status_bar,
            runtime: ReplRuntime | None = None,
        ) -> None:
            completer = CommandCompleter(registry, runtime)
            self._status_bar = status_bar
            self._bindings = KeyBindings()

            @self._bindings.add("c-o")
            def _show_activity_log(event) -> None:
                self._status_bar.toggle_activity_expanded()
                event.app.invalidate()

            # Style that removes background color from bottom toolbar so it
            # blends into the terminal instead of drawing a colored bar.
            _toolbar_style = Style.from_dict({
                "bottom-toolbar": "nobold",  # text styling only, no background
            })

            self._session = PromptSession(
                completer=completer,
                refresh_interval=0.1,
                bottom_toolbar=lambda: self._status_bar.get_text(),
                style=_toolbar_style,
                key_bindings=self._bindings,
            )

        def get_input(self, prompt: str) -> str:
            """Get user input with completion support."""
            with patch_stdout(raw=True):
                return self._session.prompt(prompt)

    def create_repl_input(
        registry: CommandRegistry,
        status_bar=None,
        runtime: ReplRuntime | None = None,
    ) -> ReplInput:
        """
        Create appropriate REPL input handler.

        Uses prompt_toolkit by default when available for slash completion
        and live command hints. Set KORA_USE_PROMPT_TOOLKIT=0 to force the
        basic input fallback.

        Args:
            registry: Command registry for completion hints.
            status_bar: Optional status bar manager used for the toolbar.
            runtime: Optional ReplRuntime for two-stage argument completion.

        Returns:
            A ReplInput instance.
        """
        if HAS_PROMPT_TOOLKIT and os.environ.get("KORA_USE_PROMPT_TOOLKIT", "1") != "0":
            return PromptToolkitInput(registry, status_bar or get_status_bar(), runtime)
        return BasicInput()

else:
    # Fallback: basic input without completion
    CommandCompleter = None  # type: ignore[misc,assignment]

    def create_repl_input(
        registry: CommandRegistry,
        status_bar=None,
        runtime: ReplRuntime | None = None,
    ) -> ReplInput:
        """Create basic REPL input handler."""
        return BasicInput()


__all__ = [
    "ReplInput",
    "print_command_menu",
    "create_repl_input",
    "format_activity_log",
    "HAS_PROMPT_TOOLKIT",
    "THINKING_FRAMES",
]
