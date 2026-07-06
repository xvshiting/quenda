"""
CLI for Quenda Agent Framework.

Provides commands to run agents:
- quenda run --agent <path> "message"  # One-shot execution
- quenda code "message"                 # One-shot with quenda-code agent
- quenda code                           # Interactive REPL mode
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from quenda.host import (
    setup_agent,
    refresh_run_context,
    find_builtin_agent,
    load_agent_commands,
    ReplRuntime,
    create_default_registry,
    create_default_interaction_registry,
    InteractionContext,
    InteractionRequest,
    InteractionOption,
    InteractionRegistry,
)
from quenda.interface import (
    ActivityEventHandler,
    ConsoleRenderer,
    ProgressEventHandler,
    SpinnerIndicator,
    get_status_bar,
    print_command_menu,
    create_repl_input,
    render_markdown_lite,
    select_option,
    # Theme and providers
    InterfaceTheme,
    WelcomeContext,
    DefaultWelcomeProvider,
    # Event handling
    StreamingEventHandler,
    CollectingEventHandler,
    CompositeEventHandler,
)
from quenda.kernel.types import ImageContent, TextContent
from quenda.runtime.multimodal import build_user_message, load_images
from quenda.runtime.events import ModelResponded, AnyEvent
from quenda.runtime.permission import PermissionRequest
from quenda.host.permission_manager import PermissionManager, format_permission_prompt


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
    # Setup agent (Host layer)
    setup = setup_agent(agent_path, workspace, provider=provider, model=model)
    if setup is None:
        print(f"Error: Failed to setup agent from {agent_path}", file=sys.stderr)
        return 1

    agent = setup.agent

    # Pass MCP manager to agent (connection happens lazily in session.send)
    if setup.binding.mcp_manager is not None:
        mcp_config = None
        if setup.agent_package.config and setup.agent_package.config.mcp:
            mcp_config = setup.agent_package.config.mcp
        agent.set_mcp(setup.binding.mcp_manager, mcp_config)

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

    print(f"Workspace: {setup.workspace_id}")
    print(f"Session: {session.id}")

    # Create components with theme
    renderer = ConsoleRenderer(theme=theme, verbose=True)
    indicator = SpinnerIndicator(theme=theme, stream=sys.stderr)
    # Use StreamingEventHandler to show model responses
    from quenda.interface.events import StreamingEventHandler
    streaming_handler = StreamingEventHandler(
        renderer=renderer,
        indicator=indicator,
        theme=theme,
    )

    # Create skill activation handler (ADR-027)
    def skill_activation_handler(skill_names: list[str]) -> str | None:
        if not skill_names or setup.skill_activator is None:
            return None

        activated: list[str] = []
        for name in skill_names:
            if setup.skill_activator.is_active(name):
                continue
            skill = setup.skill_activator.activate_skill(name, transient=True)
            if skill is not None:
                activated.append(name)

        if not activated:
            return None

        # Update binding and refresh context
        setup.binding.active_skill_names = setup.skill_activator.list_persistent()
        setup.binding.transient_skill_names = setup.skill_activator.list_transient()
        snapshot = refresh_run_context(setup.binding, session_id=session.id)
        setup.context_snapshot = snapshot
        setup.instruction_sources = snapshot.instruction_sources
        session.set_system_prompt(snapshot.composed_prompt)
        agent.set_system_prompt(snapshot.composed_prompt)

        return snapshot.composed_prompt

    try:
        session.send_sync(
            user_message,
            on_event=streaming_handler.on_event,
            skill_activation_handler=skill_activation_handler,
        )
    finally:
        indicator.stop()

    # Save session after execution
    session.save()

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

        # User selected a predefined option
        return f"[User selected: {result.label}]" + (f" - {result.description}" if result.description else "")

    elif request.kind == "confirm":
        # Confirm: Yes/No with "Other..." option
        # Add yes/no options if not provided
        if not request.options:
            request = InteractionRequest(
                kind="confirm",
                title=request.title,
                message=request.message,
                options=[
                    InteractionOption(id="yes", label="Yes", description="Proceed", is_default=True),
                    InteractionOption(id="no", label="No", description="Cancel"),
                ],
                source="llm",
            )

        result = select_option(request, interaction_registry, interaction_context)

        if result is None:
            return None

        if isinstance(result, str):
            return f"[User input: {result}]"

        return f"[User confirmed: {result.label}]"

    elif request.kind == "input":
        # Free-form input
        user_input = repl_input.get_input("\nInput: ").strip()
        return f"[User input: {user_input}]"

    return None


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

    # Pass MCP manager to agent (connection happens lazily in session.send)
    if setup.binding.mcp_manager is not None:
        mcp_config = None
        if setup.agent_package.config and setup.agent_package.config.mcp:
            mcp_config = setup.agent_package.config.mcp
        agent.set_mcp(setup.binding.mcp_manager, mcp_config)

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
        session, agent, runtime, renderer, indicator, phase_handler, registry, theme,
        provider_name, model_name, workspace_id, permission_manager
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
        print(f"\n{theme.permission_icon if hasattr(theme, 'permission_icon') else '🔐'} {format_permission_prompt(request)}")

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

    try:
        while True:
            try:
                status_bar.set_mode(session.mode)
                # Clear any previous interrupt signal before getting input
                clear_interrupt()

                # Get user input (status bar is shown via bottom_toolbar)
                user_input = repl_input.get_input("> ").strip()

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
                            from quenda.host.interactions import InteractionRequest, InteractionOption
                            from quenda.interface.selector import select_option

                            # Interactive selection loop (supports multi-level)
                            current_args = cmd_args
                            candidates = resolution.candidates if resolution.candidates else runtime.get_command_candidates(cmd_name, current_args)

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
                                    message=f"Choose an option for /{cmd_name}:" if not current_args else f"Current: {current_args}",
                                    options=options,
                                )

                                result = select_option(request)

                                if result is None:
                                    # User cancelled
                                    break

                                if hasattr(result, 'value'):
                                    selected_value = result.value
                                else:
                                    selected_value = str(result)

                                # Check if this is a partial selection (ends with /)
                                if selected_value.endswith("/") and selected_value.count("/") == 1:
                                    # Partial provider selection - get model candidates
                                    current_args = selected_value
                                    candidates = runtime.get_command_candidates(cmd_name, current_args)
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
                    print(f"\n{render_markdown_lite(result.message)}")
                    status_bar.set_mode(session.mode)
                    continue

                # ADR-027: Detect and process image paths in user input
                # Only handle local file paths that user explicitly provides
                # URLs and markdown images should NOT be auto-converted - they need Router decision
                processed_input = user_input
                words = user_input.split()
                for word in words:
                    # Check if word looks like a local file path
                    is_local_path = word.startswith("/") or word.startswith("~") or word.startswith("./")

                    if is_local_path:
                        expanded_path = Path(word).expanduser()
                        if expanded_path.exists():
                            permission_manager.grant_user_provided_resource(str(expanded_path.resolve()))

                        # Check if it's an image file
                        if expanded_path.exists() and expanded_path.suffix.lower() in {
                            ".png", ".jpg", ".jpeg", ".gif", ".webp"
                        }:
                            ref = runtime.create_image_ref(word)
                            if ref:
                                # Replace path with reference marker in display
                                processed_input = processed_input.replace(word, f"[{ref.id}: {ref.display_name()}]")
                                print(f"   Loaded image: {ref.display_name()} -> [{ref.id}]")

                # Execute the user request (ADR-027: no followup phase for skill activation)
                # Skill activation is handled within the Run, not as a separate phase.
                # The tool returns a result, and the model continues with the updated context.
                in_run = True
                collector = CollectingEventHandler()
                streamer = StreamingEventHandler(
                    renderer=renderer,
                    indicator=indicator,
                    theme=theme,
                )
                event_handler = CompositeEventHandler([streamer, collector])

                # ADR-027: Create skill activation handler for in-run skill activation
                skill_handler = runtime.create_skill_activation_handler()

                # Build multimodal message (resolve image refs if any)
                message = runtime.build_multimodal_message(processed_input)

                try:
                    session.send_sync(
                        message,
                        on_event=event_handler.on_event,
                        skill_activation_handler=skill_handler,
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
                    # Signal interrupt to kernel thread
                    from quenda.utils.interrupt import interrupt
                    interrupt()

                    # Make sure indicator is stopped
                    indicator.stop()

                    # Reset status bar to idle state
                    status_bar.set_mode(session.mode)

                    print(f"\n{theme.interrupt_icon} Interrupted")
                    clear_interrupt()
                    in_run = False  # Reset the flag
                    continue
                else:
                    # Not in a run - Ctrl+C at input stage, exit REPL
                    print(f"\n\n👋 Session saved. Bye!")
                    break
            except EOFError:
                print(f"\n\n👋 Session saved. Bye!")
                break

    except Exception as e:
        print(f"\n{theme.error_icon} Unexpected error: {e}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="quenda",
        description="Quenda Agent Framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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
        default=Path.cwd(),
        help="Workspace directory (default: current directory)",
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

    args = parser.parse_args()

    if args.command == "run":
        agent_path = args.agent
        if args.message:
            # Load images if provided
            images = load_images(args.images) if args.images else None
            if args.images and len(images) != len(args.images):
                missing = [path for path in args.images if not Path(path).expanduser().exists()]
                for path in missing:
                    print(f"Error: Image file not found: {path}", file=sys.stderr)
            user_message = build_user_message(args.message, images)
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
        agent_dir = find_builtin_agent("quenda-code")
        if agent_dir is None:
            print("Error: Quenda Code Agent not found", file=sys.stderr)
            print("Install it:  pip install quenda quenda-code", file=sys.stderr)
            print("Or:          pip install quenda[code]", file=sys.stderr)
            return 1

        if args.message:
            # Load images if provided
            images = load_images(args.images) if args.images else None
            if args.images and len(images) != len(args.images):
                missing = [path for path in args.images if not Path(path).expanduser().exists()]
                for path in missing:
                    print(f"Error: Image file not found: {path}", file=sys.stderr)
            user_message = build_user_message(args.message, images)
            return run_agent(
                agent_path=agent_dir,
                workspace=args.workspace,
                user_message=user_message,
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )
        else:
            return run_repl(
                agent_path=agent_dir,
                workspace=args.workspace,
                provider=args.provider,
                model=args.model,
                session_id=args.session,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
