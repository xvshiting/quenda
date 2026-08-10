"""
Interactive selection UI for Quenda Interface.

Provides rich selection interfaces for interaction requests:
- Arrow-key navigation with highlighting
- "Other..." option for custom input
- Fallback to basic input without prompt_toolkit
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quenda.host.interactions import InteractionOption, InteractionRequest

if TYPE_CHECKING:
    from quenda.host.interactions import InteractionContext, InteractionRegistry

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


type SelectionResult = InteractionOption | list[InteractionOption] | str | None


def _selection_marker(*, multiple: bool, checked: bool) -> str:
    """Render checkboxes only when the request allows multiple choices."""
    if not multiple:
        return ""
    return "[x]" if checked else "[ ]"


def select_option(
    request: InteractionRequest,
    registry: InteractionRegistry | None = None,
    context: InteractionContext | None = None,
) -> SelectionResult:
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
        return select_questions([request], registry, context)[0]
    else:
        return _select_basic(request, registry, context)


def select_questions(
    requests: list[InteractionRequest],
    registry: InteractionRegistry | None = None,
    context: InteractionContext | None = None,
) -> list[SelectionResult]:
    """Present one or more questions in a tabbed selector."""
    if not requests:
        return []
    if HAS_PROMPT_TOOLKIT:
        return _select_questions_with_prompt_toolkit(requests, registry, context)
    return [_select_basic(request, registry, context) for request in requests]


def _select_with_prompt_toolkit(
    request: InteractionRequest,
    registry: InteractionRegistry | None,
    context: InteractionContext | None,
) -> SelectionResult:
    """
    Use prompt_toolkit for rich selection with arrow-key navigation.
    """
    return _select_questions_with_prompt_toolkit([request], registry, context)[0]


def _select_questions_with_prompt_toolkit(
    requests: list[InteractionRequest],
    registry: InteractionRegistry | None,
    context: InteractionContext | None,
) -> list[SelectionResult]:
    """Tabbed prompt_toolkit selector supporting single and multiple choice."""
    # Resolve suggestions once so navigation and result indexes stay stable.
    question_options: list[list[InteractionOption]] = []
    for request in requests:
        options = list(request.options)
        if registry is not None and context is not None:
            options = registry.get_suggestions(request, context)
        question_options.append(options)

    other_option = InteractionOption(id="__other__", label="Other...", description="Enter custom input")
    all_question_options = [options + [other_option] for options in question_options]
    current_indexes: list[int] = []
    selected_ids: list[set[str]] = []
    for request, options in zip(requests, question_options, strict=True):
        default = request.default_option()
        current_indexes.append(next((i for i, option in enumerate(options) if default and option.id == default.id), 0))
        selected_ids.append({default.id} if default else set())

    state = {"question_idx": 0}

    def _get_formatted_text() -> list[tuple[str, str]]:
        question_idx = state["question_idx"]
        request = requests[question_idx]
        all_options = all_question_options[question_idx]
        fragments: list[tuple[str, str]] = [("", "\n")]
        if len(requests) > 1:
            for i, item in enumerate(requests):
                style = "class:active-tab" if i == question_idx else "class:tab"
                fragments.append((style, f" {i + 1}. {item.title} "))
                fragments.append(("", " "))
            fragments.append(("", "\n\n"))
        fragments.extend([("bold", request.title), ("", "\n")])
        if request.message:
            fragments.extend([("", request.message), ("", "\n")])
        fragments.append(("", "\n"))
        for i, option in enumerate(all_options):
            focused = i == current_indexes[question_idx]
            checked = option.id in selected_ids[question_idx]
            marker = _selection_marker(multiple=request.multiple, checked=checked)
            prefix = "→ " if focused else "  "
            description = f" - {option.description}" if option.description else ""
            style = "class:selected" if focused else ""
            marker_prefix = f"{marker} " if marker else ""
            fragments.extend([(style, f"{prefix}{marker_prefix}{option.label}{description}"), ("", "\n")])
        fragments.extend([
            ("", "\n"),
            ("class:hint", "←/→  Question   ↑/↓  Navigate   Space  Select   Enter  Submit   Esc  Cancel"),
            ("", "\n"),
        ])
        return fragments

    kb = KeyBindings()

    @kb.add("up")
    def _up(event: object) -> None:
        q = state["question_idx"]
        current_indexes[q] = max(0, current_indexes[q] - 1)

    @kb.add("down")
    def _down(event: object) -> None:
        q = state["question_idx"]
        current_indexes[q] = min(len(all_question_options[q]) - 1, current_indexes[q] + 1)

    @kb.add("left")
    def _left(event: object) -> None:
        state["question_idx"] = (state["question_idx"] - 1) % len(requests)

    @kb.add("right")
    def _right(event: object) -> None:
        state["question_idx"] = (state["question_idx"] + 1) % len(requests)

    @kb.add(" ")
    def _space(event: object) -> None:
        q = state["question_idx"]
        option = all_question_options[q][current_indexes[q]]
        if option.id == "__other__":
            selected_ids[q] = {option.id}
        elif requests[q].multiple:
            if option.id in selected_ids[q]:
                selected_ids[q].remove(option.id)
            else:
                selected_ids[q].add(option.id)
                selected_ids[q].discard("__other__")
        else:
            selected_ids[q] = {option.id}

    @kb.add("enter")
    def _enter(event: object) -> None:
        from prompt_toolkit.application.current import get_app
        # Enter also selects the focused row when the current question is unanswered.
        q = state["question_idx"]
        if not selected_ids[q]:
            _space(event)
        if all(selected_ids[i] or not request.required for i, request in enumerate(requests)):
            get_app().exit(result=True)

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: object) -> None:
        from prompt_toolkit.application.current import get_app
        get_app().exit(result=False)

    control = FormattedTextControl(text=_get_formatted_text, show_cursor=False)  # type: ignore[arg-type]
    app: Application[bool] = Application(
        layout=Layout(Window(content=control, dont_extend_height=True)),
        key_bindings=kb,
        style=Style.from_dict({"selected": "reverse bold", "hint": "italic", "active-tab": "reverse bold", "tab": "underline"}),
        full_screen=False,
    )
    if not app.run():
        return [None] * len(requests)

    results: list[SelectionResult] = []
    from prompt_toolkit import prompt
    for request, options, ids in zip(requests, question_options, selected_ids, strict=True):
        if "__other__" in ids:
            try:
                results.append(prompt(f"{request.title} — Enter your choice: "))
            except (KeyboardInterrupt, EOFError):
                return [None] * len(requests)
            continue
        chosen = [option for option in options if option.id in ids]
        results.append(chosen if request.multiple else (chosen[0] if chosen else None))
    return results


def _select_basic(
    request: InteractionRequest,
    registry: InteractionRegistry | None,
    context: InteractionContext | None,
) -> SelectionResult:
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

    if request.multiple:
        while True:
            try:
                user_input = input(f"Select one or more [1-{len(all_options)}], comma-separated: ").strip()
                indexes = [int(part.strip()) - 1 for part in user_input.split(",") if part.strip()]
                if indexes and all(0 <= idx < len(all_options) for idx in indexes):
                    chosen_options = [all_options[idx] for idx in dict.fromkeys(indexes)]
                    if any(option.id == "__other__" for option in chosen_options):
                        return input("Enter your choice: ").strip()
                    return chosen_options
                print(f"Please enter numbers between 1 and {len(all_options)}")
            except ValueError:
                print("Please enter valid comma-separated numbers")
            except (KeyboardInterrupt, EOFError):
                return None

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
    "select_questions",
]
