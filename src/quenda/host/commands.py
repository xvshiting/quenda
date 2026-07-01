"""
Slash Command system for Quenda Host.

Implements ADR-008: Slash Commands as Registered Small Commands
with Explicit State and Host Context Rebuild.

Provides:
- CommandCandidate: A single candidate for command argument
- CommandResolution: Result of resolving command arguments
- ReplAction: Enum for REPL actions (CONTINUE, EXIT)
- CommandResult: Structured command return value
- CommandContext: Context passed to command handlers
- Command: Protocol for defining commands
- CommandRegistry: Central registry for command discovery
- Built-in commands: /help, /clear, /exit, /session
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from quenda.runtime.agent import Agent, AgentConfig
    from quenda.runtime.session import Session
    from quenda.runtime.compressor import Compressor
    from quenda.kernel.model import Model
    from quenda.host.context import ContextRebuilder
    from quenda.host.storage import Storage
    from quenda.host.skill import SkillActivator, SkillDiscovery


class CommandCandidateKind(StrEnum):
    """Kind of command candidate."""

    ARGUMENT = "argument"
    SUBCOMMAND = "subcommand"
    VALUE = "value"


@dataclass(frozen=True)
class CommandCandidate:
    """
    A single candidate for command argument completion/selection.

    This is the Slash Command System's candidate abstraction, separate from
    Interaction System's InteractionRequest/InteractionOption.

    Attributes:
        id: Unique identifier for this candidate.
        label: Display label shown to user.
        value: The actual value to use when selected (e.g., for insertion).
        description: Optional description shown alongside label.
        kind: What kind of candidate this is (argument, subcommand, value).
        is_default: Whether this is the default selection.
    """

    id: str
    label: str
    value: str
    description: str = ""
    kind: str = "argument"
    is_default: bool = False


@dataclass
class CommandResolution:
    """
    Result of resolving command arguments.

    This tells the caller:
    - Whether the command is ready to execute
    - What the normalized arguments are
    - What message to show if not ready
    - What candidates are available for the next argument

    Attributes:
        status:
            - "ready": Command can be executed
            - "needs_input": Needs more input (show candidates)
            - "partial": Partial input complete, continue with next stage
            - "invalid": Invalid arguments
        normalized_args: The normalized argument string.
        partial_value: Value to insert for partial completion (e.g., "anthropic/").
        message: Optional message to display (error or guidance).
        candidates: Available candidates for the next argument.
    """

    status: Literal["ready", "needs_input", "partial", "invalid"]
    normalized_args: str = ""
    partial_value: str = ""  # Value to insert for partial completion
    message: str = ""
    candidates: list[CommandCandidate] = field(default_factory=list)


class ReplAction(Enum):
    """
    Actions the REPL should take after a command.

    This replaces sentinel strings like "EXIT_SESSION" with proper
    typed actions, making the contract between commands and CLI explicit.
    """

    CONTINUE = auto()  # Normal: continue the REPL loop
    EXIT = auto()  # Exit the REPL session
    CLEAR_SCREEN = auto()  # Clear the terminal (future use)


@dataclass
class CommandResult:
    """
    Structured result from a command handler.

    Attributes:
        status: Whether the command succeeded or failed.
        message: Short user-facing feedback message.
        state_patch: Explicit state diff to apply.
        rebuild_context: Whether Host should rebuild context for next turn.
        action: What action the REPL should take (default: CONTINUE).
    """

    status: Literal["ok", "error"]
    message: str
    state_patch: dict[str, Any] = field(default_factory=dict)
    rebuild_context: bool = False
    action: ReplAction = ReplAction.CONTINUE


@dataclass
class CommandContext:
    """
    Context passed to a command handler.

    Carries the current execution state that a command may read or modify.

    Attributes:
        session: The current session (for clearing, inspecting).
        agent: The agent configuration (for updating system prompt).
        model: The current model (for switching).
        storage: Optional storage backend (for persistence).
        context_builder: Optional ContextRebuilder for rebuilding system prompt.
        compressor: Optional Compressor for manual context compression.
        agent_package_path: Path to the agent package directory (for discovering modes).
        skill_activator: Optional SkillActivator for skill management.
        skill_discovery: Optional SkillDiscovery for listing available skills.
        workspace_path: Optional workspace path for skill discovery.
        host_binding: Optional StableHostBinding for capability rebind (ADR-026).
    """

    session: Session
    agent: Agent | None = None
    model: Model | None = None
    storage: Storage | None = None
    context_builder: ContextRebuilder | None = None
    compressor: Compressor | None = None
    agent_package_path: Path | None = None
    skill_activator: SkillActivator | None = None
    skill_discovery: SkillDiscovery | None = None
    workspace_path: Path | None = None
    host_binding: Any = None  # StableHostBinding - use Any to avoid circular import

    # -------------------------------------------------------------------------
    # Public API - Commands should use these instead of private field access
    # -------------------------------------------------------------------------

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


class Command(Protocol):
    """Protocol for slash commands."""

    @property
    def name(self) -> str:
        """The command name (without the leading slash)."""
        ...

    @property
    def description(self) -> str:
        """A short description shown in /help."""
        ...

    @property
    def usage(self) -> str:
        """Usage string, e.g. '/clear' or '/session <id>'."""
        ...

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """
        Execute the command.

        Args:
            args: The argument string after the command name.
            context: Current execution context.

        Returns:
            A CommandResult describing the outcome.
        """
        ...

    def get_candidates(
        self,
        args: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """
        Get candidates for command argument completion/selection.

        This is the primary interface for Slash Command System to provide
        structured candidates. It's consumed by CommandCompleter and other
        UI components.

        Args:
            args: The current argument string (may be partial).
            context: Current execution context.

        Returns:
            List of CommandCandidate objects for the next argument position.
        """
        ...

    def resolve(
        self,
        args: str,
        context: CommandContext,
    ) -> CommandResolution:
        """
        Resolve command arguments to determine next action.

        This tells the caller whether the command is ready to execute,
        needs more input, or has invalid arguments.

        Args:
            args: The argument string.
            context: Current execution context.

        Returns:
            A CommandResolution describing the state.
        """
        ...

    def get_completions(self, args: str) -> list[str]:
        """
        Get completions for command arguments (legacy, for backward compatibility).

        Prefer using get_candidates() for new implementations.

        Args:
            args: The partial argument string.

        Returns:
            List of completion suggestions.
        """
        ...


class CommandRegistry:
    """
    Central registry for slash commands.

    Commands are registered by name and discovered by the interactive
    surface (CLI, TUI, web chat) through this registry.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a command."""
        self._commands[command.name] = command

    def get(self, name: str) -> Command | None:
        """Get a command by name (without the leading slash)."""
        return self._commands.get(name)

    def has(self, name: str) -> bool:
        """Check if a command is registered."""
        return name in self._commands

    def list_commands(self) -> list[Command]:
        """List all registered commands."""
        return list(self._commands.values())

    def __contains__(self, name: str) -> bool:
        return name in self._commands

    def __len__(self) -> int:
        return len(self._commands)


# ---------------------------------------------------------------------------
# Built-in commands
# ---------------------------------------------------------------------------


class HelpCommand:
    """Show available commands."""

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Show available commands"

    @property
    def usage(self) -> str:
        return "/help [command]"

    def __init__(self, registry: CommandRegistry) -> None:
        self._registry = registry

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        commands = self._registry.list_commands()

        if not commands:
            return CommandResult(
                status="ok",
                message="No commands available.",
            )

        lines = ["**Available commands:**\n"]
        for cmd in sorted(commands, key=lambda c: c.name):
            lines.append(f"  `{cmd.usage}`")
            lines.append(f"        {cmd.description}")
            lines.append("")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )


class ClearCommand:
    """Clear session message history."""

    @property
    def name(self) -> str:
        return "clear"

    @property
    def description(self) -> str:
        return "Clear session message history"

    @property
    def usage(self) -> str:
        return "/clear"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        count = len(context.session)
        context.session.clear()

        # Persist the cleared state
        if context.storage:
            try:
                context.session.save()
            except ValueError:
                pass  # No storage configured, that's okay

        return CommandResult(
            status="ok",
            message=f"✅ Cleared {count} message(s) from session `{context.session.id[:8]}...`.",
        )


class ExitCommand:
    """Exit the interactive session."""

    @property
    def name(self) -> str:
        return "exit"

    @property
    def description(self) -> str:
        return "Exit the interactive session"

    @property
    def usage(self) -> str:
        return "/exit"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        return CommandResult(
            status="ok",
            message="👋 Session saved. Bye!",
            action=ReplAction.EXIT,
        )


class SessionCommand:
    """Show or switch sessions."""

    @property
    def name(self) -> str:
        return "session"

    @property
    def description(self) -> str:
        return "Show session info or list/resume sessions"

    @property
    def usage(self) -> str:
        return "/session [id|list|info]"

    def _get_subcommand_candidates(
        self,
        partial: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get subcommand candidates."""
        subcommands = [
            CommandCandidate(
                id="info",
                label="info",
                value="info",
                description="Show current session info",
                kind="subcommand",
                is_default=True,
            ),
            CommandCandidate(
                id="list",
                label="list",
                value="list",
                description="List saved sessions",
                kind="subcommand",
            ),
        ]

        # Add session ID candidates if we have agent/storage context
        if context.agent is not None:
            try:
                sessions = context.agent.list_sessions()
                for s in sessions:
                    session_id = s.id
                    if partial and not session_id.startswith(partial):
                        continue
                    date_str = s.created_at.strftime("%Y-%m-%d %H:%M")
                    subcommands.append(CommandCandidate(
                        id=session_id,
                        label=session_id[:12] + "...",
                        value=session_id,
                        description=f"{len(s)} msgs, {date_str}",
                        kind="value",
                    ))
            except (ValueError, Exception):
                pass

        # Filter by partial match
        if partial:
            subcommands = [c for c in subcommands if c.value.startswith(partial)]

        return subcommands

    def get_candidates(
        self,
        args: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get session candidates for completion/selection."""
        partial = args.strip()
        return self._get_subcommand_candidates(partial, context)

    def resolve(
        self,
        args: str,
        context: CommandContext,
    ) -> CommandResolution:
        """Resolve session command arguments."""
        if not args.strip():
            # No args: show subcommands and session list
            candidates = self._get_subcommand_candidates("", context)
            return CommandResolution(
                status="needs_input",
                message="Select a subcommand or session",
                candidates=candidates,
            )

        # Valid subcommands are ready to execute
        parts = args.strip().split()
        subcommand = parts[0]

        if subcommand in ("info", "list"):
            return CommandResolution(
                status="ready",
                normalized_args=subcommand,
            )

        # Check if it's a valid session ID
        if context.agent is not None:
            try:
                sessions = context.agent.list_sessions()
                for s in sessions:
                    if s.id == subcommand or s.id.startswith(subcommand):
                        return CommandResolution(
                            status="ready",
                            normalized_args=s.id,
                        )
            except (ValueError, Exception):
                pass

        return CommandResolution(
            status="invalid",
            message=f"Unknown subcommand or session: `{subcommand}`. Use info, list, or a session ID.",
        )

    def get_completions(self, args: str) -> list[str]:
        """Complete subcommand names (legacy, without context)."""
        partial = args.strip()
        return [s for s in ["info", "list"] if s.startswith(partial)]

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        parts = args.strip().split()
        subcommand = parts[0] if parts else "info"

        if subcommand == "info" or subcommand == "":
            msg_count = len(context.session)
            agent_name = getattr(context.session.state, "agent_name", "unknown")
            return CommandResult(
                status="ok",
                message=(
                    f"**Session:** `{context.session.id}`\n"
                    f"  Messages: {msg_count}\n"
                    f"  Agent: {agent_name}"
                ),
            )

        elif subcommand == "list":
            if context.storage is None:
                return CommandResult(
                    status="error",
                    message="No storage configured. Cannot list sessions.",
                )
            if context.agent is None:
                return CommandResult(
                    status="error",
                    message="No agent context available.",
                )
            try:
                sessions = context.agent.list_sessions()
            except ValueError as e:
                return CommandResult(status="error", message=str(e))

            if not sessions:
                return CommandResult(
                    status="ok",
                    message="No saved sessions found.",
                )

            lines = ["**Saved sessions:**\n"]
            for i, s in enumerate(sessions, 1):
                date_str = s.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(f"  {i}. `{s.id[:12]}...` ({len(s)} msgs, {date_str})")

            return CommandResult(
                status="ok",
                message="\n".join(lines),
            )

        else:
            # Try to resume a session by ID prefix
            if context.storage is None or context.agent is None:
                return CommandResult(
                    status="error",
                    message="No storage configured. Cannot switch sessions.",
                )

            # We can't easily switch sessions in the current flow without
            # rebuilding the REPL state. Return guidance instead.
            return CommandResult(
                status="ok",
                message=(
                    f"To resume session `{subcommand}`, restart with:\n"
                    f"  kora code --session {subcommand}"
                ),
            )


class ModelCommand:
    """Show or switch the current model."""

    @property
    def name(self) -> str:
        return "model"

    @property
    def description(self) -> str:
        return "Show or switch the current model"

    @property
    def usage(self) -> str:
        return "/model [provider/model]"

    def _get_provider_registry(self):
        """Get the provider registry lazily."""
        from quenda.providers import get_provider_registry
        return get_provider_registry()

    def _get_provider_candidates(
        self,
        partial: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get provider candidates."""
        registry = self._get_provider_registry()
        providers = registry.list_providers()

        candidates = []
        for provider_id in sorted(providers):
            if partial and not provider_id.startswith(partial):
                continue

            # Try to get model count and sample models
            description = ""
            sample_models = []
            try:
                spec = registry._specs.get(provider_id)
                if spec and spec.models:
                    model_count = len(spec.models)
                    # Show up to 3 sample models as hint
                    sample_models = [m.id for m in list(spec.models)[:3]]
                    if model_count <= 3:
                        description = f"{model_count} models: {', '.join(sample_models)}"
                    else:
                        description = f"{model_count} models (e.g., {', '.join(sample_models)}...)"
            except Exception:
                description = "Select to see models"

            # Label shows format hint: provider/
            # Description shows model count and samples
            candidates.append(CommandCandidate(
                id=provider_id,
                label=f"{provider_id}/",  # Show format hint
                value=f"{provider_id}/",  # Value includes / to trigger next level
                description=description,
                kind="argument",
            ))

        return candidates

    def _get_model_candidates(
        self,
        provider_id: str,
        partial: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get model candidates for a specific provider."""
        registry = self._get_provider_registry()

        try:
            provider = registry.get_provider(provider_id)
            if provider is None:
                return []
            models = provider.list_models()
        except KeyError:
            return []

        candidates = []
        for model_spec in models:
            model_id = model_spec.id
            if partial and not model_id.startswith(partial):
                continue

            # Build description with model info
            description = model_spec.name if model_spec.name else ""
            if model_spec.context_window:
                ctx = model_spec.context_window
                if ctx >= 1_000_000:
                    description += f" ({ctx // 1000}k ctx)" if description else f"{ctx // 1000}k ctx"
                else:
                    description += f" ({ctx}k ctx)" if description else f"{ctx}k ctx"

            # Full value with provider/model format
            candidates.append(CommandCandidate(
                id=f"{provider_id}/{model_id}",
                label=model_id,
                value=f"{provider_id}/{model_id}",
                description=description,
                kind="argument",
            ))

        return candidates

    def get_candidates(
        self,
        args: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """
        Get model candidates for completion/selection.

        Supports two-stage selection:
        1. Empty args or partial provider -> show providers
        2. "provider/" or "provider" (partial match) -> show models for that provider
        """
        args = args.strip()

        # Stage 1: No args -> show providers
        if not args:
            return self._get_provider_candidates("", context)

        # Check if args ends with "/" or is a complete provider name
        if "/" in args:
            # Stage 2: Provider selected, show models
            parts = args.split("/", 1)
            provider_id = parts[0]
            model_partial = parts[1] if len(parts) > 1 else ""
            return self._get_model_candidates(provider_id, model_partial, context)

        # No "/" - could be partial provider name
        # Show matching providers
        return self._get_provider_candidates(args, context)

    def resolve(
        self,
        args: str,
        context: CommandContext,
    ) -> CommandResolution:
        """Resolve model command arguments."""
        args = args.strip()

        if not args:
            # No args: needs provider selection
            candidates = self._get_provider_candidates("", context)
            return CommandResolution(
                status="needs_input",
                message="Select a provider",
                candidates=candidates,
            )

        registry = self._get_provider_registry()

        # Check if args contains "/"
        if "/" not in args:
            # Could be:
            # 1. A partial provider name -> show matching providers
            # 2. A complete provider name -> partial status, show models
            # 3. A model name -> try to find across all providers

            # Check if it's a valid provider name
            if args in registry.list_providers():
                # Complete provider name -> show models for this provider
                candidates = self._get_model_candidates(args, "", context)
                return CommandResolution(
                    status="partial",
                    partial_value=f"{args}/",  # Insert "provider/"
                    message=f"Select a model for {args}",
                    candidates=candidates,
                )

            # Check if it's a partial provider name
            matching_providers = [p for p in registry.list_providers() if p.startswith(args)]
            if matching_providers:
                candidates = self._get_provider_candidates(args, context)
                return CommandResolution(
                    status="needs_input",
                    message="Select a provider",
                    candidates=candidates,
                )

            # Try to find as a model name across all providers
            for provider_id in registry.list_providers():
                try:
                    provider = registry.get_provider(provider_id)
                    if provider:
                        for model_spec in provider.list_models():
                            if model_spec.id == args or model_spec.id.startswith(args):
                                # Found a matching model
                                return CommandResolution(
                                    status="ready",
                                    normalized_args=f"{provider_id}/{model_spec.id}",
                                )
                except KeyError:
                    continue

            return CommandResolution(
                status="invalid",
                message=f"Unknown provider or model: `{args}`",
            )

        # Has "/" - parse provider/model
        parts = args.split("/", 1)
        provider_id = parts[0]
        model_id = parts[1] if len(parts) > 1 else ""

        if not model_id:
            # Just "provider/" - needs model selection
            candidates = self._get_model_candidates(provider_id, "", context)
            if not candidates:
                return CommandResolution(
                    status="invalid",
                    message=f"Provider `{provider_id}` not found or has no models",
                )
            return CommandResolution(
                status="needs_input",
                message=f"Select a model for {provider_id}",
                candidates=candidates,
            )

        # Full provider/model specified
        try:
            registry.get_model(provider_id, model_id)
            return CommandResolution(
                status="ready",
                normalized_args=f"{provider_id}/{model_id}",
            )
        except KeyError as e:
            return CommandResolution(
                status="invalid",
                message=str(e),
            )

    def get_completions(self, args: str) -> list[str]:
        """Complete model names (legacy, without context - limited functionality)."""
        # Without context, we can't access the provider registry
        return []

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        if not args.strip():
            # Show current model
            if context.model is None:
                return CommandResult(
                    status="error",
                    message="No model is currently set.",
                )
            return CommandResult(
                status="ok",
                message=f"**Current model:** `{context.model}`",
            )

        # Parse provider/model
        parts = args.strip().split("/")
        if len(parts) == 1:
            provider = None
            model_name = parts[0]
        elif len(parts) == 2:
            provider, model_name = parts
        else:
            return CommandResult(
                status="error",
                message="Usage: `/model [provider/]model_name`",
            )

        try:
            from quenda.providers import get_provider_registry
            registry = get_provider_registry()

            if provider:
                new_model = registry.get_model(provider, model_name)
            else:
                # Try to find the model in any provider
                new_model = None
                for p in registry.list_providers():
                    try:
                        new_model = registry.get_model(p, model_name)
                        provider = p
                        break
                    except KeyError:
                        continue
                if new_model is None:
                    return CommandResult(
                        status="error",
                        message=f"Model `{model_name}` not found in any provider.",
                    )

            # Apply the model change
            # Note: providers.model.Model structurally satisfies kernel.model.Model Protocol
            context.session.set_model(new_model)  # type: ignore[arg-type]

            return CommandResult(
                status="ok",
                message=f"✅ Switched to `{provider}/{model_name}`.",
                state_patch={
                    "model_provider": provider,
                    "model_name": model_name,
                },
                rebuild_context=True,
            )

        except KeyError as e:
            return CommandResult(
                status="error",
                message=str(e),
            )
        except Exception as e:
            return CommandResult(
                status="error",
                message=f"Failed to switch model: {e}",
            )


# ---------------------------------------------------------------------------
# Mode command
# ---------------------------------------------------------------------------

# Fallback modes for legacy get_completions() which doesn't have context
VALID_MODES = frozenset({"chat", "code", "architect"})


def _discover_modes(agent_package_path: Path | None) -> dict[str, str]:
    """
    Discover available modes from agent package.

    Looks for mode-*.md files in <agent_package>/instructions/ directory.
    Returns a dict mapping mode name -> description.

    Args:
        agent_package_path: Path to agent package directory.

    Returns:
        Dict of mode_name -> description. Always includes "chat" as default.
    """
    modes: dict[str, str] = {
        "chat": "General conversation and Q&A",  # Default mode, always available
    }

    if agent_package_path is None:
        # Fallback to built-in modes
        modes["code"] = "Focused on writing and editing code"
        modes["architect"] = "Design, planning, and architecture discussions"
        return modes

    instructions_dir = agent_package_path / "instructions"
    if not instructions_dir.exists():
        return modes

    # Scan for mode-*.md files
    for mode_file in instructions_dir.glob("mode-*.md"):
        mode_name = mode_file.stem[5:]  # Remove "mode-" prefix
        if mode_name == "chat":
            continue  # Skip if somehow there's a mode-chat.md

        # Extract description from the first heading or first line
        content = mode_file.read_text(encoding="utf-8")
        description = _extract_mode_description(content, mode_name)
        modes[mode_name] = description

    return modes


def _extract_mode_description(content: str, mode_name: str) -> str:
    """
    Extract a short description from mode file content.

    Looks for the first heading content or uses a default.

    Args:
        content: The mode file content.
        mode_name: The mode name (for fallback).

    Returns:
        A short description string.
    """
    lines = content.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Look for markdown heading
        if line.startswith("## "):
            return line[3:].strip()
        if line.startswith("# "):
            return line[2:].strip()
        # Look for first non-empty line
        if line and not line.startswith("#"):
            # Take first sentence or first 50 chars
            if len(line) > 60:
                return line[:57] + "..."
            return line

    # Fallback to capitalized mode name
    return mode_name.capitalize() + " mode"


class ModeCommand:
    """Show or switch interaction mode."""

    @property
    def name(self) -> str:
        return "mode"

    @property
    def description(self) -> str:
        return "Show or switch interaction mode"

    @property
    def usage(self) -> str:
        return "/mode [mode_name]"

    def _get_available_modes(self, context: CommandContext) -> dict[str, str]:
        """Get available modes from context."""
        return _discover_modes(context.agent_package_path)

    def get_candidates(
        self,
        args: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get mode candidates for completion/selection."""
        modes = self._get_available_modes(context)
        current_mode = context.session.state.metadata.get("mode", "chat")

        candidates = []
        partial = args.strip().lower()

        for mode_name, description in sorted(modes.items()):
            # Filter by partial match if args provided
            if partial and not mode_name.startswith(partial):
                continue

            candidates.append(CommandCandidate(
                id=mode_name,
                label=mode_name,
                value=mode_name,
                description=description,
                kind="argument",
                is_default=(mode_name == current_mode),
            ))

        return candidates

    def resolve(
        self,
        args: str,
        context: CommandContext,
    ) -> CommandResolution:
        """Resolve mode command arguments."""
        modes = self._get_available_modes(context)

        if not args.strip():
            # No args: needs mode selection
            candidates = self.get_candidates(args, context)
            return CommandResolution(
                status="needs_input",
                message="Select a mode",
                candidates=candidates,
            )

        mode_name = args.strip().lower()
        if mode_name not in modes:
            # Invalid mode
            return CommandResolution(
                status="invalid",
                message=f"Invalid mode: `{mode_name}`. Available: {', '.join(sorted(modes.keys()))}",
            )

        # Valid mode: ready to execute
        return CommandResolution(
            status="ready",
            normalized_args=mode_name,
        )

    def get_completions(self, args: str) -> list[str]:
        """Complete mode names (legacy, for backward compatibility)."""
        # This is called without context, so we return a static list
        return [m for m in VALID_MODES if m.startswith(args.strip().lower())]

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """Execute the mode command."""
        modes = self._get_available_modes(context)
        current_mode = context.session.state.metadata.get("mode", "chat")

        if not args.strip():
            desc = modes.get(current_mode, "")
            available = ", ".join(f"`{m}`" for m in sorted(modes.keys()))
            return CommandResult(
                status="ok",
                message=(
                    f"**Current mode:** `{current_mode}`\n"
                    f"  {desc}\n\n"
                    f"Available modes: {available}"
                ),
            )

        new_mode = args.strip().lower()
        if new_mode not in modes:
            return CommandResult(
                status="error",
                message=(
                    f"Invalid mode: `{new_mode}`. "
                    f"Available modes: {', '.join(sorted(modes.keys()))}"
                ),
            )

        if new_mode == current_mode:
            return CommandResult(
                status="ok",
                message=f"Already in `{current_mode}` mode.",
            )

        # Store mode in session metadata for persistence
        context.session.state.metadata["mode"] = new_mode

        desc = modes.get(new_mode, "")
        return CommandResult(
            status="ok",
            message=f"✅ Switched to `{new_mode}` mode.\n  {desc}",
            state_patch={"mode": new_mode},
            rebuild_context=True,
        )
        return CommandResult(
            status="ok",
            message=f"✅ Switched to `{new_mode}` mode.\n  {desc}",
            state_patch={"mode": new_mode},
            rebuild_context=True,
        )


# ---------------------------------------------------------------------------
# Context command
# ---------------------------------------------------------------------------


class ContextCommand:
    """Show context information."""

    @property
    def name(self) -> str:
        return "context"

    @property
    def description(self) -> str:
        return "Show current context (system prompt, tools, session)"

    @property
    def usage(self) -> str:
        return "/context [show|tools|session]"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        parts = args.strip().split()
        subcommand = parts[0] if parts else "show"

        if subcommand == "show":
            return self._show(context)
        elif subcommand == "tools":
            return self._show_tools(context)
        elif subcommand == "session":
            return self._show_session(context)
        else:
            return CommandResult(
                status="error",
                message=f"Unknown subcommand: `{subcommand}`. Use `/context show`, `/context tools`, or `/context session`.",
            )

    def _show(self, context: CommandContext) -> CommandResult:
        """Show the current system prompt."""
        system_prompt = context.get_system_prompt()

        if not system_prompt:
            return CommandResult(
                status="ok",
                message="No system prompt is set.",
            )

        # Show full prompt with proper formatting
        lines = [f"**System Prompt** ({len(system_prompt)} chars):\n"]
        lines.append("```")
        lines.append(system_prompt)
        lines.append("```")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )

    def _show_tools(self, context: CommandContext) -> CommandResult:
        """Show available tools."""
        tools = context.get_tools()
        if not tools:
            return CommandResult(
                status="ok",
                message="No tools configured.",
            )

        lines = [f"**Available Tools ({len(tools)}):**\n"]
        for t in tools:
            lines.append(f"  • `{t.name}` — {t.description}")
        lines.append("")
        lines.append("Use `/context show` to see the full system prompt.")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )

    def _show_session(self, context: CommandContext) -> CommandResult:
        """Show current session info."""
        msg_count = len(context.session)
        session_id = context.session.id
        mode = context.session.state.metadata.get("mode", "chat")
        agent_name = getattr(context.session.state, "agent_name", "unknown")
        model_info = str(context.model) if context.model else "not set"

        return CommandResult(
            status="ok",
            message=(
                f"**Session Info:**\n"
                f"  ID: `{session_id}`\n"
                f"  Agent: {agent_name}\n"
                f"  Messages: {msg_count}\n"
                f"  Mode: `{mode}`\n"
                f"  Model: `{model_info}`"
            ),
        )


# ---------------------------------------------------------------------------
# Reset command
# ---------------------------------------------------------------------------


class ResetCommand:
    """Reset the session: clear messages and restore original system prompt."""

    @property
    def name(self) -> str:
        return "reset"

    @property
    def description(self) -> str:
        return "Reset session: clear messages and restore system prompt"

    @property
    def usage(self) -> str:
        return "/reset"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        count = len(context.session)
        context.session.clear()

        # Persist the cleared state
        if context.storage:
            try:
                context.session.save()
            except ValueError:
                pass

        # Signal rebuild to restore original system prompt
        return CommandResult(
            status="ok",
            message=f"✅ Reset session `{context.session.id[:8]}...`. Cleared {count} message(s) and restored system prompt.",
            state_patch={"reset": True},
            rebuild_context=True,
        )


# ---------------------------------------------------------------------------
# Compress command (ADR-015)
# ---------------------------------------------------------------------------


class CompressCommand:
    """Manually trigger context compression."""

    @property
    def name(self) -> str:
        return "compress"

    @property
    def description(self) -> str:
        return "Compress conversation history to reduce context size"

    @property
    def usage(self) -> str:
        return "/compress [force]"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        # Check if compressor is available
        if context.compressor is None:
            return CommandResult(
                status="error",
                message="Context compression is not enabled. Configure compression in agent config.",
            )

        # Get session state
        session_state = context.session.state

        # Count messages before compression
        before_count = len(session_state.messages)

        if before_count == 0:
            return CommandResult(
                status="ok",
                message="No messages to compress. Session is empty.",
            )

        # Create compression decision (force compression)
        from quenda.runtime.compression import CompressionDecision

        force = args.strip().lower() == "force"
        decision = CompressionDecision(
            compress=True,
            keep_last_n_messages=10,
            target_budget_tokens=None,
            archive_raw_messages=True,
            summarizer_id="default",
            reason="manual trigger" + (" (forced)" if force else ""),
        )

        # Execute compression
        try:
            result = context.compressor.compress(session_state, decision)

            # Apply result to session state
            from quenda.runtime.session import SummaryBlock
            from datetime import datetime

            for msg in result.summary_messages:
                session_state.summary_blocks.append(SummaryBlock(
                    content=msg.content,
                    message_range=(0, result.archived_message_count),
                    created_at=datetime.now(),
                    token_count=result.summary_token_count,
                ))

            session_state.archive_refs.extend(result.archive_refs)
            session_state.usage.compression_count += 1
            session_state.usage.last_compressed_at = datetime.now()

            # Persist session
            if context.storage:
                context.storage.save_session(session_state)

            return CommandResult(
                status="ok",
                message=(
                    f"✅ Compressed session.\n"
                    f"  Archived: {result.archived_message_count} messages\n"
                    f"  Summary: ~{result.summary_token_count} tokens\n"
                    f"  Archive refs: {len(result.archive_refs)}\n"
                    f"  Remaining: {len(session_state.messages)} messages"
                ),
            )

        except Exception as e:
            return CommandResult(
                status="error",
                message=f"Compression failed: {e}",
            )


# ---------------------------------------------------------------------------
# Status command (ADR-015)
# ---------------------------------------------------------------------------


class StatusCommand:
    """Show session status including compression info."""

    @property
    def name(self) -> str:
        return "status"

    @property
    def description(self) -> str:
        return "Show session status: messages, tokens, compression info"

    @property
    def usage(self) -> str:
        return "/status"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        session_state = context.session.state
        usage = session_state.usage

        # Build status message
        lines = ["**Session Status:**\n"]

        # Basic info
        lines.append(f"  Session ID: `{context.session.id[:12]}...`")
        lines.append(f"  Messages: {len(session_state.messages)}")
        lines.append(f"  Mode: `{context.session.state.metadata.get('mode', 'chat')}`")

        if context.model:
            lines.append(f"  Model: `{context.model}`")

        # Token usage
        lines.append("\n**Token Usage:**")
        lines.append(f"  Total input: {usage.total_input_tokens}")
        lines.append(f"  Total output: {usage.total_output_tokens}")
        lines.append(f"  Total: {usage.total_tokens}")

        if usage.total_cached_input_tokens:
            lines.append(f"  Cached: {usage.total_cached_input_tokens}")

        if usage.total_reasoning_tokens:
            lines.append(f"  Reasoning: {usage.total_reasoning_tokens}")

        # Compression info
        if usage.compression_count > 0:
            lines.append("\n**Compression:**")
            lines.append(f"  Count: {usage.compression_count}")
            if usage.last_compressed_at:
                lines.append(f"  Last: {usage.last_compressed_at.strftime('%Y-%m-%d %H:%M')}")

            summary_count = len(session_state.summary_blocks)
            if summary_count > 0:
                summary_tokens = sum(b.token_count for b in session_state.summary_blocks)
                lines.append(f"  Summary blocks: {summary_count} (~{summary_tokens} tokens)")

            archive_count = len(session_state.archive_refs)
            if archive_count > 0:
                lines.append(f"  Archive refs: {archive_count}")
        else:
            lines.append("\n**Compression:** Not yet compressed")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )


# ---------------------------------------------------------------------------
# Rebind command (ADR-026)
# ---------------------------------------------------------------------------


class RebindCommand:
    """Rebind capability-level configuration (model, tools, sandbox, policies).

    ADR-026: Capability rebind requires explicit user action.
    Text refresh happens automatically at each turn boundary.
    """

    @property
    def name(self) -> str:
        return "rebind"

    @property
    def description(self) -> str:
        return "Rebind capability configuration: model, tools, sandbox (requires restart)"

    @property
    def usage(self) -> str:
        return "/rebind"

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """Show rebind information.

        Note: Full rebind requires session restart because it affects
        model binding, tool grants, and sandbox configuration.
        """
        # Get current binding info if available
        binding = context.host_binding

        if binding is None:
            return CommandResult(
                status="ok",
                message=(
                    "**Capability Rebind (ADR-026)**\n\n"
                    "Rebind refreshes capability-level configuration:\n"
                    "  • Model/provider binding\n"
                    "  • Tool grants (bundles and includes)\n"
                    "  • Sandbox configuration\n"
                    "  • Policy bindings\n\n"
                    "**Note:** Full rebind requires restarting the session.\n"
                    "Exit the REPL and start a new session to pick up config changes.\n\n"
                    "Text-level context (AGENT.md, instructions, skills) refreshes\n"
                    "automatically on each new message - no need to rebind."
                ),
            )

        # Show current binding status
        lines = ["**Current Capability Binding:**\n"]
        lines.append(f"  Provider: `{binding.provider_name}`")
        lines.append(f"  Model: `{binding.model_name}`")
        lines.append(f"  Tools: {len(binding.tools)} granted")
        lines.append(f"  Sandbox: {len(binding.sandbox_config.allowed_modules)} allowed modules")
        lines.append(f"  Active skills: {len(binding.active_skill_names)}")

        lines.append("\n**To Rebind:**")
        lines.append("  Exit the REPL and start a new session.")
        lines.append("  This will re-read `config.yaml` and rebuild bindings.")
        lines.append("\n  Text context (AGENT.md, instructions, skills)")
        lines.append("  refreshes automatically each turn.")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )


# ---------------------------------------------------------------------------
# Skill command (ADR-002)
# ---------------------------------------------------------------------------


class SkillCommand:
    """Manage skills: list, activate, deactivate, view resources."""

    @property
    def name(self) -> str:
        return "skill"

    @property
    def description(self) -> str:
        return "Manage skills: list, activate, deactivate, view resources"

    @property
    def usage(self) -> str:
        return "/skill [list|activate|deactivate|resources] [name]"

    def _get_subcommand_candidates(
        self,
        partial: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get subcommand candidates."""
        subcommands = [
            CommandCandidate(
                id="list",
                label="list",
                value="list",
                description="List available and active skills",
                kind="subcommand",
                is_default=True,
            ),
            CommandCandidate(
                id="activate",
                label="activate",
                value="activate",
                description="Activate a skill",
                kind="subcommand",
            ),
            CommandCandidate(
                id="deactivate",
                label="deactivate",
                value="deactivate",
                description="Deactivate a skill",
                kind="subcommand",
            ),
            CommandCandidate(
                id="resources",
                label="resources",
                value="resources",
                description="List resources from active skills",
                kind="subcommand",
            ),
        ]

        # Filter by partial match
        if partial:
            subcommands = [c for c in subcommands if c.value.startswith(partial)]

        return subcommands

    def _get_skill_candidates(
        self,
        partial: str,
        context: CommandContext,
        active_only: bool = False,
    ) -> list[CommandCandidate]:
        """Get skill name candidates."""
        if context.skill_discovery is None:
            return []

        candidates = []

        if active_only:
            # Only show active skills
            if context.skill_activator is None:
                return []
            for name in context.skill_activator.list_active():
                if partial and not name.startswith(partial):
                    continue
                skill = context.skill_discovery.get_skill(name)
                description = skill.description if skill else ""
                candidates.append(CommandCandidate(
                    id=name,
                    label=name,
                    value=name,
                    description=description,
                    kind="argument",
                    is_default=True,
                ))
        else:
            # Show all available skills
            skills = context.skill_discovery.discover_skills()
            active_names = set(context.skill_activator.list_active()) if context.skill_activator else set()

            for skill in skills:
                if partial and not skill.name.startswith(partial):
                    continue
                status = " (active)" if skill.name in active_names else ""
                candidates.append(CommandCandidate(
                    id=skill.name,
                    label=skill.name,
                    value=skill.name,
                    description=skill.description + status,
                    kind="argument",
                    is_default=(skill.name in active_names),
                ))

        return candidates

    def get_candidates(
        self,
        args: str,
        context: CommandContext,
    ) -> list[CommandCandidate]:
        """Get skill candidates for completion/selection."""
        parts = args.strip().split(maxsplit=1)

        if not parts:
            # No args: show subcommands
            return self._get_subcommand_candidates("", context)

        subcommand = parts[0]

        # Check if partial subcommand
        if subcommand not in ("list", "activate", "deactivate", "resources"):
            matching = [c for c in self._get_subcommand_candidates(subcommand, context) if c.value.startswith(subcommand)]
            if matching:
                return matching
            # If no matching subcommand, might be skill name for activate
            if context.skill_discovery:
                return self._get_skill_candidates(subcommand, context)

        # Subcommand complete, need skill name for activate/deactivate
        if len(parts) == 1:
            if subcommand in ("activate",):
                return self._get_skill_candidates("", context, active_only=False)
            elif subcommand in ("deactivate",):
                return self._get_skill_candidates("", context, active_only=True)

        # Skill name partial
        if len(parts) >= 2:
            skill_partial = parts[1]
            if subcommand == "activate":
                return self._get_skill_candidates(skill_partial, context, active_only=False)
            elif subcommand == "deactivate":
                return self._get_skill_candidates(skill_partial, context, active_only=True)

        return []

    def resolve(
        self,
        args: str,
        context: CommandContext,
    ) -> CommandResolution:
        """Resolve skill command arguments."""
        parts = args.strip().split(maxsplit=1)

        if not parts:
            # No args: show subcommands
            candidates = self._get_subcommand_candidates("", context)
            return CommandResolution(
                status="needs_input",
                message="Select a subcommand",
                candidates=candidates,
            )

        subcommand = parts[0]

        # Valid subcommands without args
        if subcommand in ("list", "resources"):
            return CommandResolution(
                status="ready",
                normalized_args=subcommand,
            )

        # Subcommands needing skill name
        if subcommand in ("activate", "deactivate"):
            if len(parts) < 2:
                # Need skill name
                active_only = subcommand == "deactivate"
                candidates = self._get_skill_candidates("", context, active_only=active_only)
                return CommandResolution(
                    status="needs_input",
                    message=f"Select a skill to {subcommand}",
                    candidates=candidates,
                )

            skill_name = parts[1]
            active_only = subcommand == "deactivate"
            candidates = self._get_skill_candidates(skill_name, context, active_only=active_only)

            # Check if exact match
            matching = [c for c in candidates if c.value == skill_name]
            if matching:
                return CommandResolution(
                    status="ready",
                    normalized_args=f"{subcommand} {skill_name}",
                )

            # Partial match
            if candidates:
                return CommandResolution(
                    status="needs_input",
                    message=f"Select a skill to {subcommand}",
                    candidates=candidates,
                )

            return CommandResolution(
                status="invalid",
                message=f"Unknown skill: `{skill_name}`",
            )

        # Unknown subcommand
        return CommandResolution(
            status="invalid",
            message=f"Unknown subcommand: `{subcommand}`. Use list, activate, deactivate, or resources.",
        )

    def get_completions(self, args: str) -> list[str]:
        """Complete subcommands (legacy, without context)."""
        subcommands = ["list", "activate", "deactivate", "resources"]
        partial = args.strip()
        return [s for s in subcommands if s.startswith(partial)]

    def execute(self, args: str, context: CommandContext) -> CommandResult:
        """Execute the skill command."""
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0] if parts else "list"

        if subcommand == "list":
            return self._list_skills(context)
        elif subcommand == "activate":
            if len(parts) < 2:
                return CommandResult(
                    status="error",
                    message="Usage: `/skill activate <name>`",
                )
            return self._activate_skill(parts[1], context)
        elif subcommand == "deactivate":
            if len(parts) < 2:
                return CommandResult(
                    status="error",
                    message="Usage: `/skill deactivate <name>`",
                )
            return self._deactivate_skill(parts[1], context)
        elif subcommand == "resources":
            return self._list_resources(context)
        else:
            return CommandResult(
                status="error",
                message=f"Unknown subcommand: `{subcommand}`. Use list, activate, deactivate, or resources.",
            )

    def _list_skills(self, context: CommandContext) -> CommandResult:
        """List available and active skills."""
        if context.skill_discovery is None:
            return CommandResult(
                status="ok",
                message="No skills configured for this workspace.",
            )

        skills = context.skill_discovery.discover_skills()
        if not skills:
            return CommandResult(
                status="ok",
                message="No skills found in this workspace.\n\n"
                        "Create a skill by adding `.quenda/skills/<name>/SKILL.md`",
            )

        active_names = set(context.skill_activator.list_active()) if context.skill_activator else set()

        lines = ["**Available Skills:**\n"]
        for skill in sorted(skills, key=lambda s: s.name):
            status = " ✓" if skill.name in active_names else ""
            lines.append(f"  • `{skill.name}`{status}")
            if skill.description:
                lines.append(f"      {skill.description}")
            if skill.commands:
                lines.append(f"      Triggers: {', '.join(skill.commands)}")

        lines.append("")
        active_count = len(active_names)
        lines.append(f"**Active:** {active_count}/{len(skills)}")
        lines.append("")
        lines.append("Use `/skill activate <name>` to activate a skill.")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )

    def _activate_skill(self, name: str, context: CommandContext) -> CommandResult:
        """Activate a skill."""
        if context.skill_activator is None:
            return CommandResult(
                status="error",
                message="Skill system not initialized.",
            )

        # Check if already active
        if context.skill_activator.is_active(name):
            return CommandResult(
                status="ok",
                message=f"Skill `{name}` is already active.",
            )

        skill = context.skill_activator.activate_skill(name)
        if skill is None:
            return CommandResult(
                status="error",
                message=f"Skill `{name}` not found. Use `/skill list` to see available skills.",
            )

        return CommandResult(
            status="ok",
            message=f"✅ Activated skill `{name}`.\n  {skill.description}",
            state_patch={"skills": context.skill_activator.list_persistent()},
            rebuild_context=True,
        )

    def _deactivate_skill(self, name: str, context: CommandContext) -> CommandResult:
        """Deactivate a skill."""
        if context.skill_activator is None:
            return CommandResult(
                status="error",
                message="Skill system not initialized.",
            )

        if not context.skill_activator.is_active(name):
            return CommandResult(
                status="error",
                message=f"Skill `{name}` is not active. Use `/skill list` to see active skills.",
            )

        context.skill_activator.deactivate_skill(name)

        return CommandResult(
            status="ok",
            message=f"✅ Deactivated skill `{name}`.",
            state_patch={"skills": context.skill_activator.list_persistent()},
            rebuild_context=True,
        )

    def _list_resources(self, context: CommandContext) -> CommandResult:
        """List resources from active skills."""
        if context.skill_activator is None:
            return CommandResult(
                status="ok",
                message="No skills active. Use `/skill activate <name>` to activate skills.",
            )

        active_skills = context.skill_activator.active_skills
        if not active_skills:
            return CommandResult(
                status="ok",
                message="No skills active. Use `/skill activate <name>` to activate skills.",
            )

        from quenda.host.skill import ResourceResolver
        resolver = ResourceResolver(active_skills)
        resources = resolver.list_resources()

        if not resources:
            return CommandResult(
                status="ok",
                message="Active skills have no declared resources.",
            )

        lines = ["**Skill Resources:**\n"]
        for r in sorted(resources, key=lambda x: (x.skill_name, x.resource_name)):
            status = "" if r.exists else " (missing)"
            lines.append(f"  • `{r.skill_name}/{r.resource_name}` [{r.resource_type}]{status}")
            if r.description:
                lines.append(f"      {r.description}")

        return CommandResult(
            status="ok",
            message="\n".join(lines),
        )


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------


def create_default_registry() -> CommandRegistry:
    """
    Create a CommandRegistry with all built-in commands registered.

    Returns:
        A CommandRegistry instance with default commands.
    """
    registry = CommandRegistry()
    registry.register(HelpCommand(registry))
    registry.register(ClearCommand())
    registry.register(ExitCommand())
    registry.register(SessionCommand())
    registry.register(ModelCommand())
    registry.register(ModeCommand())
    registry.register(ContextCommand())
    registry.register(ResetCommand())
    registry.register(CompressCommand())
    registry.register(StatusCommand())
    registry.register(RebindCommand())
    registry.register(SkillCommand())
    return registry


__all__ = [
    "CommandCandidateKind",
    "CommandCandidate",
    "CommandResolution",
    "ReplAction",
    "CommandResult",
    "CommandContext",
    "Command",
    "CommandRegistry",
    "HelpCommand",
    "ClearCommand",
    "ExitCommand",
    "SessionCommand",
    "ModelCommand",
    "ModeCommand",
    "ContextCommand",
    "ResetCommand",
    "CompressCommand",
    "StatusCommand",
    "SkillCommand",
    "VALID_MODES",
    "create_default_registry",
    "_discover_modes",
]
