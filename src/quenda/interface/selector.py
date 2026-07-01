"""
Interactive selection UI for Kora Interface.

Provides rich selection interfaces for interaction requests:
- Arrow-key navigation with highlighting
- "Other..." option for custom input
- Fallback to basic input without prompt_toolkit
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quenda.host.interactions import InteractionOption, InteractionRequest

if TYPE_CHECKING:
    from quenda.host.interactions import InteractionRegistry, InteractionContext

# Try to import prompt_toolkit for enhanced selection
try:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


def select_option(
    request: InteractionRequest,
    registry: InteractionRegistry | None = None,
    context: InteractionContext | None = None,
) -> InteractionOption | str | None:
    """
    Present options to user and return their selection.

    Args:
        request: The interaction request with options.
        registry: Optional registry for validation.
        context: Optional context for validation.

    Returns:
        - InteractionOption: If user selected a predefined option
        - str: If user entered custom input (via "Other...")
        - None: If user cancelled
    """
    if HAS_PROMPT_TOOLKIT:
        return _select_with_prompt_toolkit(request, registry, context)
    else:
        return _select_basic(request, registry, context)


def _select_with_prompt_toolkit(
    request: InteractionRequest,
    registry: InteractionRegistry | None,
    context: InteractionContext | None,
) -> InteractionOption | str | None:
    """
    Use prompt_toolkit for rich selection with arrow-key navigation.
    """
    # Get suggestions
    options = list(request.options)
    if registry is not None and context is not None:
        options = registry.get_suggestions(request, context)

    # Add "Other..." option
    other_option = InteractionOption(id="__other__", label="Other...", description="Enter custom input")
    all_options = options + [other_option]

    # Find default index
    default_idx = 0
    default_opt = request.default_option()
    if default_opt:
        for i, opt in enumerate(options):
            if opt.id == default_opt.id:
                default_idx = i
                break

    # State for navigation
    state: dict[str, int | None] = {"current_idx": default_idx}

    def _get_formatted_text() -> list[tuple[str, str]]:
        """Build styled text fragments for the full display."""
        fragments: list[tuple[str, str]] = []

        # Title
        fragments.append(("", "\n"))
        fragments.append(("bold", request.title))
        fragments.append(("", "\n"))

        # Message
        if request.message:
            fragments.append(("", request.message))
            fragments.append(("", "\n"))

        fragments.append(("", "\n"))

        # Options list
        for i, opt in enumerate(all_options):
            number = f"{i + 1}"
            default_marker = " (default)" if opt.id == request.default_option_id or opt.is_default else ""
            description = f" - {opt.description}" if opt.description else ""

            is_selected = i == state["current_idx"]
            # Ensure a minimum 2-space indent; the selected row gets a → prefix
            prefix = "→ " if is_selected else "  "

            # Check if the option label itself should be colored (e.g. yes/green, no/red)
            label = opt.label
            if is_selected:
                # Full line highlight for selected option
                line = f"{prefix}{number}. {label}{default_marker}{description}"
                fragments.append(("class:selected", line))
            else:
                line = f"{prefix}{number}. {label}{default_marker}{description}"
                fragments.append(("", line))

            fragments.append(("", "\n"))

        # Footer hint
        fragments.append(("", "\n"))
        fragments.append(("class:hint", "↑/↓  Navigate   Enter  Select   Esc  Cancel"))
        fragments.append(("", "\n"))

        return fragments

    # Build key bindings
    kb = KeyBindings()

    @kb.add("up")
    def _up(event: object) -> None:
        idx = state["current_idx"]
        if isinstance(idx, int) and idx > 0:
            state["current_idx"] = idx - 1

    @kb.add("down")
    def _down(event: object) -> None:
        idx = state["current_idx"]
        if isinstance(idx, int) and idx < len(all_options) - 1:
            state["current_idx"] = idx + 1

    @kb.add("enter")
    def _enter(event: object) -> None:
        from prompt_toolkit.application.current import get_app
        idx = state["current_idx"]
        if isinstance(idx, int):
            get_app().exit(result=all_options[idx])

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: object) -> None:
        from prompt_toolkit.application.current import get_app
        get_app().exit(result=None)

    # Create a FormattedTextControl that re-reads state on each render
    control = FormattedTextControl(
        text=_get_formatted_text,
        show_cursor=False,
    )

    root_container = Window(content=control, dont_extend_height=True)
    layout = Layout(root_container)

    # Style: selected line uses reverse video + bold for maximum visibility
    style = Style.from_dict({
        "selected": "reverse bold",
        "hint": "italic",
    })

    # Create and run application
    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
    result = app.run()

    if result is None:
        return None

    # Handle "Other..." selection
    if result.id == "__other__":
        from prompt_toolkit import prompt
        try:
            custom = prompt("Enter your choice: ")
            return custom
        except (KeyboardInterrupt, EOFError):
            return None

    return result


def _select_basic(
    request: InteractionRequest,
    registry: InteractionRegistry | None,
    context: InteractionContext | None,
) -> InteractionOption | str | None:
    """
    Basic selection without prompt_toolkit - number input.
    """
    # Get suggestions
    options = list(request.options)
    if registry is not None and context is not None:
        options = registry.get_suggestions(request, context)

    # Add "Other..." option
    other_option = InteractionOption(id="__other__", label="Other...", description="Enter custom input")
    all_options = options + [other_option]

    # Print menu
    print(f"\n{request.title}")
    if request.message:
        print(request.message)
    print("")
    for i, opt in enumerate(all_options, 1):
        default_marker = " (default)" if opt.id == request.default_option_id or opt.is_default else ""
        description = f" - {opt.description}" if opt.description else ""
        print(f"  {i}. {opt.label}{default_marker}{description}")
    print(f"  {len(all_options) + 1}. Cancel")
    print("")

    # Get user selection
    while True:
        try:
            user_input = input(f"Select [1-{len(all_options) + 1}]: ").strip()

            if not user_input:
                # Check for default
                default = request.default_option()
                if default:
                    return default
                continue

            idx = int(user_input) - 1

            # Check for cancel
            if idx == len(all_options):
                return None

            if 0 <= idx < len(all_options):
                selected = all_options[idx]

                # Handle "Other..."
                if selected.id == "__other__":
                    custom = input("Enter your choice: ").strip()
                    return custom

                return selected

            print(f"Please enter a number between 1 and {len(all_options) + 1}")

        except ValueError:
            print("Please enter a valid number")
        except (KeyboardInterrupt, EOFError):
            return None


__all__ = [
    "select_option",
]
