"""
CLI for Quenda Agent Framework.

Provides commands to run agents:
- quenda run --agent <path> "message"  # One-shot execution
- quenda agent create <name>            # Create a local Agent Home
- quenda <name>                         # Run a local Agent Home
- quenda code                           # Run local code agent or Quenda Code
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quenda.host import (
    AgentHome,
    AgentHomeManager,
    InteractionContext,
    InteractionOption,
    InteractionRegistry,
    InteractionRequest,
    ReplRuntime,
    create_default_interaction_registry,
    create_default_registry,
    find_builtin_agent,
    load_agent_commands,
    run_agent_once,
    setup_agent,
)
from quenda.host.permission_manager import PermissionManager, format_permission_prompt
from quenda.interface import (
    ActivityEventHandler,
    CollectingEventHandler,
    CompositeEventHandler,
    ConsoleRenderer,
    DefaultWelcomeProvider,
    # Theme and providers
    InterfaceTheme,
    ProgressEventHandler,
    SpinnerIndicator,
    # Event handling
    StreamingEventHandler,
    WelcomeContext,
    create_repl_input,
    get_status_bar,
    print_command_menu,
    render_markdown_lite,
    select_option,
    select_questions,
)
from quenda.kernel.types import ImageContent, TextContent
from quenda.runtime.events import InteractionRequested
from quenda.runtime.multimodal import build_user_message, load_images
from quenda.runtime.permission import PermissionRequest

_DOUBLE_CTRL_C_WINDOW_SECONDS = 1.5
_BUILTIN_COMMANDS = frozenset({"run", "agent", "code"})


def _register_exit_interrupt(
    previous_interrupt_at: float | None,
    *,
    now: float | None = None,
) -> tuple[bool, float | None]:
    """Record an idle Ctrl+C and report whether it confirms REPL exit."""
    current = time.monotonic() if now is None else now
    if (
        previous_interrupt_at is not None
        and 0 <= current - previous_interrupt_at <= _DOUBLE_CTRL_C_WINDOW_SECONDS
    ):
        return True, None
    return False, current


def _build_cli_user_message(
    message: str,
    image_paths: Sequence[str] | None,
) -> str | Sequence[TextContent | ImageContent]:
    """Build a CLI user message and report missing image files."""
    images = load_images(image_paths) if image_paths else None
    if image_paths and len(images) != len(image_paths):
        missing = [path for path in image_paths if not Path(path).expanduser().exists()]
        for path in missing:
            print(f"Error: Image file not found: {path}", file=sys.stderr)
    return build_user_message(message, images)


def run_agent(
    agent_path: Path,
    workspace: Path,
    user_message: str | Sequence[TextContent | ImageContent],
    *,
    provider: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
    theme: InterfaceTheme | None = None,
) -> int:
    """
    Run an agent with a single message (one-shot mode).

    Args:
        agent_path: Path to AGENT.md file.
        workspace: Workspace directory for file operations.
        user_message: The task or question for the agent.
        provider: Model provider override.
        model: Model name override.
        session_id: Optional session ID to resume.
        theme: Interface theme configuration (overrides agent config).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    resolved_theme = theme or InterfaceTheme()
    renderer = ConsoleRenderer(theme=resolved_theme, verbose=True)
    indicator = SpinnerIndicator(theme=resolved_theme, stream=sys.stderr)
    streaming_handler = StreamingEventHandler(
        renderer=renderer,
        indicator=indicator,
        theme=resolved_theme,
    )

    def on_setup(setup: Any, session: Any) -> None:
        nonlocal resolved_theme, renderer, indicator, streaming_handler

        if theme is None:
            config = setup.agent_package.config
            if config and config.theme:
                resolved_theme = config.theme.create_theme()
                renderer = ConsoleRenderer(theme=resolved_theme, verbose=True)
                indicator = SpinnerIndicator(theme=resolved_theme, stream=sys.stderr)
                streaming_handler = StreamingEventHandler(
                    renderer=renderer,
                    indicator=indicator,
                    theme=resolved_theme,
                )

        if session_id and session.id != session_id:
            print(f"Session {session_id} not found, creating new session")
        print(f"Workspace: {setup.workspace_id}")
        print(f"Session: {session.id}")

    try:
        ok = run_agent_once(
            agent_path=agent_path,
            workspace=workspace,
            user_message=user_message,
            provider=provider,
            model=model,
            session_id=session_id,
            on_event=lambda event: streaming_handler.on_event(event),
            on_setup=on_setup,
        )
    finally:
        indicator.stop()

    if not ok:
        print(f"Error: Failed to setup agent from {agent_path}", file=sys.stderr)
        return 1

    return 0


def _handle_interaction_request(
    request_payload: dict,
    interaction_registry: InteractionRegistry,
    interaction_context: InteractionContext,
    repl_input,
) -> str | None:
    """
    Handle an interaction request from the LLM.

    Args:
        request_payload: The tool arguments from request_interaction call.
        interaction_registry: Registry for validating interactions.
        interaction_context: Context for validation.
        repl_input: Input handler for collecting user response.

    Returns:
        User's response as a message to inject into next turn, or None if cancelled.
    """
    # A batched request is rendered as tabs and submitted as one response.
    question_payloads = request_payload.get("questions")
    if question_payloads:
        requests = [_interaction_request_from_payload(item) for item in question_payloads]
        for request in requests:
            errors = interaction_registry.validate(request, interaction_context)
            if errors:
                print("\n⚠ Invalid interaction request:")
                for error in errors:
                    print(f"  - {error}")
                return None
        results = select_questions(requests, interaction_registry, interaction_context)
        if not results or all(result is None for result in results):
            return None
        if any(
            request.required and result is None
            for request, result in zip(requests, results, strict=True)
        ):
            return None
        answers: list[str] = []
        for payload, result in zip(question_payloads, results, strict=True):
            if result is None:
                continue
            question_id = payload.get("id", payload.get("title", "question"))
            if isinstance(result, list):
                value = ", ".join(option.label for option in result)
            elif isinstance(result, InteractionOption):
                value = result.label
            else:
                value = str(result)
            answers.append(f"{question_id}: {value}")
        return "[User answers: " + "; ".join(answers) + "]"

    # Construct InteractionRequest
    options = [
        InteractionOption(
            id=opt.get("id", ""),
            label=opt.get("label", ""),
            description=opt.get("description", ""),
            is_default=opt.get("is_default", False),
        )
        for opt in request_payload.get("options", [])
    ]

    request = InteractionRequest(
        kind=request_payload.get("kind", "choice"),
        title=request_payload.get("title", "Interaction Required"),
        message=request_payload.get("message", ""),
        options=options,
        default_option_id=request_payload.get("default_option_id"),
        multiple=request_payload.get("multiple", False),
        source="llm",
    )

    # Validate
    errors = interaction_registry.validate(request, interaction_context)
    if errors:
        print("\n⚠ Invalid interaction request:")
        for error in errors:
            print(f"  - {error}")
        return None

    # Handle different interaction kinds
    if request.kind in ("choice", "menu"):
        # Use rich selector with arrow-key navigation
        result = select_option(request, interaction_registry, interaction_context)

        if result is None:
            return None  # User cancelled

        if isinstance(result, str):
            # User entered custom input via "Other..."
            return f"[User input: {result}]"

        if isinstance(result, list):
            labels = ", ".join(option.label for option in result)
            return f"[User selected: {labels}]"

        # User selected a predefined option
        return f"[User selected: {result.label}]" + (
            f" - {result.description}" if result.description else ""
        )

    elif request.kind == "confirm":
        # Confirm: Yes/No with "Other..." option
        # Add yes/no options if not provided
        if not request.options:
            request = InteractionRequest(
                kind="confirm",
                title=request.title,
                message=request.message,
                options=[
                    InteractionOption(
                        id="yes", label="Yes", description="Proceed", is_default=True
                    ),
                    InteractionOption(id="no", label="No", description="Cancel"),
                ],
                source="llm",
            )

        result = select_option(request, interaction_registry, interaction_context)

        if result is None:
            return None

        if isinstance(result, str):
            return f"[User input: {result}]"

        if isinstance(result, list):
            return f"[User confirmed: {', '.join(option.label for option in result)}]"

        return f"[User confirmed: {result.label}]"

    elif request.kind == "input":
        # Free-form input
        print(f"\n{request.title}")
        if request.message:
            print(request.message)
        user_input = repl_input.get_input("\n› ").strip()
        return f"[User input: {user_input}]"

    return None


def _interaction_request_from_payload(payload: dict[str, Any]) -> InteractionRequest:
    """Build a choice request from one legacy or batched tool payload."""
    options = [
        InteractionOption(
            id=option.get("id", ""),
            label=option.get("label", ""),
            description=option.get("description", ""),
            is_default=option.get("is_default", False),
        )
        for option in payload.get("options", [])
    ]
    return InteractionRequest(
        kind=payload.get("kind", "choice"),
        title=payload.get("title", payload.get("header", "Interaction Required")),
        message=payload.get("message", payload.get("question", "")),
        options=options,
        default_option_id=payload.get("default_option_id"),
        multiple=payload.get("multiple", False),
        required=payload.get("required", True),
        source="llm",
    )


def _run_interactive_turn(
    *,
    session,
    message,
    streamer: StreamingEventHandler,
    indicator: SpinnerIndicator,
    interaction_registry: InteractionRegistry,
    interaction_context: InteractionContext,
    repl_input,
    skill_activation_handler,
    before_send=None,
    max_interactions: int = 10,
) -> None:
    """Run a REPL turn, yielding to Host whenever human input is requested."""
    pending_message = message
    interactions_handled = 0

    for _ in range(max_interactions + 1):
        if before_send is not None:
            before_send()
        collector = CollectingEventHandler()
        event_handler = CompositeEventHandler([streamer, collector])
        try:
            session.send_sync(
                pending_message,
                on_event=event_handler.on_event,
                skill_activation_handler=skill_activation_handler,
            )
        finally:
            indicator.stop()

        requests = [
            event for event in collector.get_events() if isinstance(event, InteractionRequested)
        ]
        if not requests:
            return
        if interactions_handled >= max_interactions:
            raise RuntimeError(
                f"Interaction limit exceeded ({max_interactions}) in a single user turn."
            )

        response = _handle_interaction_request(
            requests[0].request,
            interaction_registry,
            interaction_context,
            repl_input,
        )
        if response is None:
            return
        pending_message = response
        interactions_handled += 1


def _is_local_path_reference(value: str) -> bool:
    """Return whether a user-input token explicitly references a local path."""
    return value.startswith(("/", "~", "./", "../"))


def run_repl(
    agent_path: Path,
    workspace: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
    theme: InterfaceTheme | None = None,
) -> int:
    """
    Run an agent in interactive REPL mode.

    Args:
        agent_path: Path to AGENT.md file.
        workspace: Workspace directory for file operations.
        provider: Model provider override.
        model: Model name override.
        session_id: Optional session ID to resume.
        theme: Interface theme configuration (overrides agent config).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    permission_manager = PermissionManager()

    # Setup agent (Host layer)
    setup = setup_agent(
        agent_path,
        workspace,
        provider=provider,
        model=model,
        permission_policy=permission_manager,
    )
    if setup is None:
        print(f"Error: Failed to setup agent from {agent_path}", file=sys.stderr)
        return 1

    agent = setup.agent
    context_builder = setup.context_builder
    provider_name = setup.provider_name
    model_name = setup.model_name
    workspace_id = setup.workspace_id

    # Resolve theme: CLI arg > agent config > default
    if theme is None:
        config = setup.agent_package.config
        if config and config.theme:
            theme = config.theme.create_theme()
        else:
            theme = InterfaceTheme()

    # Open or resume session
    if session_id:
        session = agent.load_session(session_id)
        if session is None:
            print(f"Session {session_id} not found, creating new session")
            session = agent.open_session(session_id=session_id)
    else:
        session = agent.open_session()

    permission_manager.load_state(session.state.metadata.get("permission_cache"))

    # Create command registry and load agent extensions (ADR-010)
    registry = create_default_registry()
    loaded_count = load_agent_commands(setup.agent_package.path, registry)
    if loaded_count > 0:
        print(f"   Loaded {loaded_count} custom command(s)")

    # Create ReplRuntime - encapsulates all REPL logic (Host layer)
    runtime = ReplRuntime(
        session=session,
        agent=agent,
        context_builder=context_builder,
        provider_name=provider_name,
        model_name=model_name,
        registry=registry,
        compressor=setup.compressor,
        agent_package_path=setup.agent_package.path,
        skill_discovery=setup.skill_discovery,
        skill_activator=setup.skill_activator,
        workspace_path=setup.workspace_path,
    )

    # Set host binding for /rebind command (ADR-026)
    if setup.binding:
        runtime.set_host_binding(setup.binding)

    # Create components with theme
    renderer = ConsoleRenderer(theme=theme, verbose=False)
    indicator = SpinnerIndicator(theme=theme, stream=sys.stderr)
    # Print welcome message using WelcomeProvider
    welcome_provider = DefaultWelcomeProvider(theme)
    welcome_ctx = WelcomeContext(
        agent_name=setup.agent_package.name,
        workspace_id=workspace_id,
        workspace_path=workspace,
        session_id=session.id,
        provider=provider_name,
        model=model_name,
    )
    print(welcome_provider.render(welcome_ctx))

    status_bar = get_status_bar()
    activity_handler = ActivityEventHandler(
        indicator=indicator,
        theme=theme,
        renderer=renderer,
        status_bar=status_bar,
    )
    progress_handler = ProgressEventHandler(
        renderer=renderer,
        indicator=indicator,
    )
    phase_handler = CompositeEventHandler([activity_handler, progress_handler])

    # Run REPL loop (Interface layer handles input)
    return _run_repl(
        session,
        agent,
        runtime,
        renderer,
        indicator,
        phase_handler,
        registry,
        theme,
        provider_name,
        model_name,
        workspace_id,
        permission_manager,
    )


def _run_repl(
    session,
    agent,
    runtime: ReplRuntime,
    renderer: ConsoleRenderer,
    indicator: SpinnerIndicator,
    phase_handler,
    registry,
    theme: InterfaceTheme,
    provider_name: str,
    model_name: str,
    workspace_id: str,
    permission_manager: PermissionManager,
) -> int:
    """
    Run REPL loop using interface layer for input.

    Uses prompt_toolkit if available for auto-completion and status bar,
    otherwise falls back to basic input.
    """
    from quenda.interface.status import DefaultStatusProvider, StatusContext
    from quenda.utils.interrupt import clear_interrupt

    # Create interaction registry for validating LLM interaction requests
    interaction_registry = create_default_interaction_registry()
    interaction_context = InteractionContext(session=session, agent=agent)

    # Note: ESC listener is disabled because it conflicts with prompt_toolkit
    # Use Ctrl+C to interrupt runs instead
    # from quenda.interface.activity import start_interrupt_listener
    # interrupt_listener = start_interrupt_listener()

    # Setup status bar with theme-aware provider
    status_bar = get_status_bar()
    status_bar.provider = DefaultStatusProvider(theme)
    status_bar.context = StatusContext(
        mode=session.mode,
        model=model_name,
        provider=provider_name,
        workspace_id=workspace_id,
        session_id=session.id,
    )
    status_bar.set_mode(session.mode)

    # Create input handler with runtime for two-stage command completion
    repl_input = create_repl_input(registry, status_bar=status_bar, runtime=runtime)

    def permission_prompt_handler(request: PermissionRequest) -> bool:
        """Prompt the user for a permission decision."""
        indicator.stop()
        print(
            f"\n{theme.permission_icon if hasattr(theme, 'permission_icon') else '🔐'} {format_permission_prompt(request)}"
        )

        try:
            response = repl_input.get_input("Approve? [y/N]: ").strip().lower()
            allowed = response in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            allowed = False

        if in_run:
            indicator.start()

        return allowed

    permission_manager.prompt_handler = permission_prompt_handler

    # Track whether we're in a run (for interrupt handling)
    in_run = False
    last_exit_interrupt_at: float | None = None

    try:
        while True:
            try:
                status_bar.set_mode(session.mode)
                # Clear any previous interrupt signal before getting input
                clear_interrupt()

                # Get user input (status bar is shown via bottom_toolbar)
                user_input = repl_input.get_input("> ").strip()
                last_exit_interrupt_at = None

                if not user_input:
                    continue

                # Show command menu when user types just "/"
                if user_input == "/":
                    print_command_menu(registry)
                    continue

                # Check if this is a command that needs interactive selection
                # This happens when:
                # 1. Command has no args but has candidates
                # 2. Command has partial args (resolve returns needs_input)
                if user_input.startswith("/"):
                    cmd_name, _, cmd_args = user_input[1:].partition(" ")
                    command = registry.get(cmd_name)
                    if command is not None:
                        # Check command resolution status
                        resolution = runtime.resolve_command(cmd_name, cmd_args)

                        if resolution.status in ("needs_input", "partial"):
                            # Command needs more input - trigger interactive selection
                            from quenda.host.interactions import (
                                InteractionOption,
                                InteractionRequest,
                            )
                            from quenda.interface.selector import select_option

                            # Interactive selection loop (supports multi-level)
                            current_args = cmd_args
                            candidates = (
                                resolution.candidates
                                if resolution.candidates
                                else runtime.get_command_candidates(cmd_name, current_args)
                            )

                            while candidates:
                                # Build interaction request from candidates
                                options = [
                                    InteractionOption(
                                        id=c.id,
                                        label=c.label,
                                        description=c.description,
                                        value=c.value,
                                        is_default=c.is_default,
                                    )
                                    for c in candidates
                                ]

                                request = InteractionRequest(
                                    kind="menu",
                                    title=f"Select {cmd_name}",
                                    message=f"Choose an option for /{cmd_name}:"
                                    if not current_args
                                    else f"Current: {current_args}",
                                    options=options,
                                )

                                option_result = select_option(request)

                                if option_result is None:
                                    # User cancelled
                                    break

                                if hasattr(option_result, "value"):
                                    selected_value = option_result.value
                                else:
                                    selected_value = str(option_result)

                                # Check if this is a partial selection (ends with /)
                                if selected_value.endswith("/") and selected_value.count("/") == 1:
                                    # Partial provider selection - get model candidates
                                    current_args = selected_value
                                    candidates = runtime.get_command_candidates(
                                        cmd_name, current_args
                                    )
                                    if not candidates:
                                        # No more candidates, break
                                        break
                                    # Continue loop to show next level
                                    continue
                                else:
                                    # Complete selection - execute command
                                    current_args = selected_value
                                    break

                            if current_args:
                                # Execute with selected value
                                full_command = f"/{cmd_name} {current_args}"
                                exec_result = runtime.execute_command(full_command)
                                if exec_result is not None:
                                    if runtime.is_exit_requested(exec_result):
                                        print(f"\n{render_markdown_lite(exec_result.message)}")
                                        break
                                    print(f"\n{render_markdown_lite(exec_result.message)}")
                                    status_bar.set_mode(session.mode)
                            continue

                # Delegate command handling to ReplRuntime (Host layer)
                result = runtime.execute_command(user_input)
                if result is not None:
                    if runtime.is_exit_requested(result):
                        print(f"\n{render_markdown_lite(result.message)}")
                        break
                    if result.message:
                        print(f"\n{render_markdown_lite(result.message)}")
                    status_bar.set_mode(session.mode)
                    if result.model_input is None:
                        continue
                    user_input = result.model_input

                # ADR-027: Detect and process image paths in user input
                # Only handle local file paths that user explicitly provides
                # URLs and markdown images should NOT be auto-converted - they need Router decision
                processed_input = user_input
                words = user_input.split()
                for word in words:
                    # Check if word looks like a local file path
                    is_local_path = _is_local_path_reference(word)

                    if is_local_path:
                        expanded_path = Path(word).expanduser()
                        if expanded_path.exists():
                            permission_manager.grant_user_provided_resource(
                                str(expanded_path.resolve())
                            )

                        # Check if it's an image file
                        if expanded_path.exists() and expanded_path.suffix.lower() in {
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".webp",
                        }:
                            ref = runtime.create_image_ref(word)
                            if ref:
                                # Replace path with reference marker in display
                                processed_input = processed_input.replace(
                                    word, f"[{ref.id}: {ref.display_name()}]"
                                )
                                print(f"   Loaded image: {ref.display_name()} -> [{ref.id}]")

                # Execute the user request (ADR-027: no followup phase for skill activation)
                # Skill activation is handled within the Run, not as a separate phase.
                # The tool returns a result, and the model continues with the updated context.
                in_run = True
                streamer = StreamingEventHandler(
                    renderer=renderer,
                    indicator=indicator,
                    theme=theme,
                )

                # ADR-027: Create skill activation handler for in-run skill activation
                skill_handler = runtime.create_skill_activation_handler()

                # Build multimodal message (resolve image refs if any)
                message = runtime.build_multimodal_message(processed_input)

                try:
                    _run_interactive_turn(
                        session=session,
                        message=message,
                        streamer=streamer,
                        indicator=indicator,
                        interaction_registry=interaction_registry,
                        interaction_context=interaction_context,
                        repl_input=repl_input,
                        skill_activation_handler=skill_handler,
                        before_send=runtime.refresh_context,
                    )
                finally:
                    session.state.metadata["permission_cache"] = permission_manager.to_state()
                    session.save()
                    indicator.stop()

                in_run = False

                # Note: Per Agent Skills specification, skill instructions are
                # "durable behavioral guidance" and should persist throughout the
                # session. We do NOT auto-offload transient skills after each Run.
                # Transient skills are cleared only when:
                # 1. User explicitly deactivates them
                # 2. Session ends (they're not persisted to session metadata)
                status_bar.set_mode(session.mode)

            except KeyboardInterrupt:
                # If we're in a run, interrupt it and continue
                # Otherwise, exit the REPL
                if in_run:
                    # Make sure indicator is stopped
                    indicator.stop()

                    # Reset status bar to idle state
                    status_bar.set_mode(session.mode)

                    print(f"\n{theme.interrupt_icon} Interrupted")
                    in_run = False  # Reset the flag
                    continue
                else:
                    # At the input prompt, require a quick second Ctrl+C to exit.
                    should_exit, last_exit_interrupt_at = _register_exit_interrupt(
                        last_exit_interrupt_at
                    )
                    if should_exit:
                        print("\n\n👋 Session saved. Bye!")
                        break
                    print("\nPress Ctrl+C again within 1.5s to exit.")
                    continue
            except EOFError:
                print("\n\n👋 Session saved. Bye!")
                break

    except Exception as e:
        print(f"\n{theme.error_icon} Unexpected error: {e}", file=sys.stderr)
        return 1

    return 0


def _add_agent_run_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the common arguments accepted by named Agent launchers."""
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: the Agent Home workspace)",
    )
    parser.add_argument("--provider", help="Model provider override")
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--session", help="Resume a session by ID")
    parser.add_argument(
        "--image",
        action="append",
        dest="images",
        help="Image file to attach (can be used multiple times)",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Task or question for the agent (omit for REPL mode)",
    )


def _launch_agent_home(home: AgentHome, args: argparse.Namespace) -> int:
    """Launch a named Agent Home in one-shot or interactive mode."""
    workspace = args.workspace.expanduser() if args.workspace else home.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    if args.message:
        return run_agent(
            agent_path=home.path,
            workspace=workspace,
            user_message=_build_cli_user_message(args.message, args.images),
            provider=args.provider,
            model=args.model,
            session_id=args.session,
        )
    return run_repl(
        agent_path=home.path,
        workspace=workspace,
        provider=args.provider,
        model=args.model,
        session_id=args.session,
    )


def _run_agent_shortcut(
    name: str,
    argv: Sequence[str],
    manager: AgentHomeManager,
) -> int | None:
    """Run ``quenda <name>`` when name resolves to an Agent Home."""
    home = manager.get(name)
    if home is None:
        return None
    parser = argparse.ArgumentParser(prog=f"quenda {name}")
    _add_agent_run_arguments(parser)
    return _launch_agent_home(home, parser.parse_args(list(argv)))


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    cli_args = list(sys.argv[1:] if argv is None else argv)
    agent_manager = AgentHomeManager()
    if cli_args and cli_args[0] not in _BUILTIN_COMMANDS:
        shortcut_result = _run_agent_shortcut(cli_args[0], cli_args[1:], agent_manager)
        if shortcut_result is not None:
            return shortcut_result

    parser = argparse.ArgumentParser(
        prog="quenda",
        description="Quenda Agent Framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    agent_parser = subparsers.add_parser("agent", help="Create and manage local agents")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    create_parser = agent_subparsers.add_parser("create", help="Create an Agent Home")
    create_parser.add_argument("name", help="Agent name")
    create_parser.add_argument(
        "--from",
        dest="source",
        help="Seed from an installed agent, source directory, or AGENT.md",
    )

    agent_subparsers.add_parser("list", help="List local Agent Homes")

    agent_run_parser = agent_subparsers.add_parser("run", help="Run a local Agent Home")
    agent_run_parser.add_argument("name", help="Agent name")
    _add_agent_run_arguments(agent_run_parser)

    # kora run --agent <path> [message]
    run_parser = subparsers.add_parser("run", help="Run an agent from AGENT.md")
    run_parser.add_argument(
        "--agent",
        type=Path,
        required=True,
        help="Path to AGENT.md file",
    )
    run_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace directory (default: current directory)",
    )
    run_parser.add_argument(
        "--provider",
        help="Model provider (e.g., anthropic, openai, deepseek)",
    )
    run_parser.add_argument(
        "--model",
        help="Model name (e.g., claude-sonnet-4-20250514, gpt-4o)",
    )
    run_parser.add_argument(
        "--session",
        help="Resume a session by ID",
    )
    run_parser.add_argument(
        "--image",
        action="append",
        dest="images",
        help="Image file to attach (can be used multiple times)",
    )
    run_parser.add_argument(
        "message",
        nargs="?",
        help="Task or question for the agent (omit for REPL mode)",
    )

    # kora code [message]
    code_parser = subparsers.add_parser("code", help="Run Quenda Code Agent")
    code_parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (local Agent Home default, otherwise current directory)",
    )
    code_parser.add_argument(
        "--provider",
        help="Model provider (e.g., anthropic, openai, deepseek)",
    )
    code_parser.add_argument(
        "--model",
        help="Model name (e.g., claude-sonnet-4-20250514, gpt-4o)",
    )
    code_parser.add_argument(
        "--session",
        help="Resume a session by ID",
    )
    code_parser.add_argument(
        "--image",
        action="append",
        dest="images",
        help="Image file to attach (can be used multiple times)",
    )
    code_parser.add_argument(
        "message",
        nargs="?",
        help="Task or question for the agent (omit for REPL mode)",
    )

    args = parser.parse_args(cli_args)

    if args.command == "agent":
        if args.agent_command == "create":
            try:
                home = agent_manager.create(args.name, source=args.source)
            except (FileExistsError, FileNotFoundError, ValueError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(f"Created agent: {home.name}")
            print(f"Home: {home.path}")
            print(f"Workspace: {home.workspace}")
            print(f"Run: quenda {home.name}")
            return 0

        if args.agent_command == "list":
            homes = agent_manager.list()
            if not homes:
                print("No local agents. Create one with: quenda agent create <name>")
                return 0
            for home in homes:
                source = f" (from {home.created_from})" if home.created_from else ""
                print(f"{home.name}\t{home.path}{source}")
            return 0

        if args.agent_command == "run":
            home = agent_manager.get(args.name)
            if home is None:
                print(f'Error: Agent "{args.name}" not found', file=sys.stderr)
                return 1
            return _launch_agent_home(home, args)

    if args.command == "run":
        agent_path = args.agent
        if args.message:
            user_message = _build_cli_user_message(args.message, args.images)
            return run_agent(
                agent_path=agent_path,
                workspace=args.workspace,
                user_message=user_message,
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )
        else:
            return run_repl(
                agent_path=agent_path,
                workspace=args.workspace,
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )

    elif args.command == "code":
        local_code = agent_manager.get("code")
        if local_code is not None:
            return _launch_agent_home(local_code, args)

        agent_dir = find_builtin_agent("quenda-code")
        if agent_dir is None:
            print("Error: Quenda Code Agent not found", file=sys.stderr)
            print("Install it:  pip install quenda quenda-code", file=sys.stderr)
            print("Or:          pip install quenda[code]", file=sys.stderr)
            return 1

        if args.message:
            user_message = _build_cli_user_message(args.message, args.images)
            return run_agent(
                agent_path=agent_dir,
                workspace=args.workspace or Path.cwd(),
                user_message=user_message,
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )
        else:
            return run_repl(
                agent_path=agent_dir,
                workspace=args.workspace or Path.cwd(),
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
