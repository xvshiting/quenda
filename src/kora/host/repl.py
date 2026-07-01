"""
REPL runtime for Kora Host layer.

Encapsulates all REPL state management and command dispatch,
keeping the CLI layer thin and focused on I/O.

This follows the architecture:
- Host (ReplRuntime) → orchestrates context rebuilding
- Session/Agent → store state, expose interfaces
- Runtime → execution
- Kernel → model-tool loop
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kora.host.commands import (
    CommandCandidate,
    CommandContext,
    CommandRegistry,
    CommandResolution,
    CommandResult,
    ReplAction,
    create_default_registry,
)
from kora.host.runner import refresh_run_context

if TYPE_CHECKING:
    from kora.runtime.agent import Agent
    from kora.runtime.session import Session
    from kora.runtime.compressor import Compressor
    from kora.host.context import ContextRebuilder
    from kora.host.skill import SkillActivator, SkillDiscovery
    from kora.kernel.model import Model


@dataclass(frozen=True)
class ReplState:
    """
    Immutable snapshot of REPL runtime state.

    This captures the current provider/model/mode configuration
    that affects context rebuilding.
    """

    provider_name: str
    model_name: str
    mode: str


class ReplRuntime:
    """
    Encapsulates REPL state management and command dispatch.

    The CLI layer calls into this runtime for:
    - Command execution and result handling
    - State patch application
    - Context rebuilding (via Host's ContextRebuilder)
    - Tab completion hints

    This keeps the CLI thin and moves orchestration to Host layer.
    """

    def __init__(
        self,
        *,
        session: Session,
        agent: Agent,
        context_builder: ContextRebuilder,
        provider_name: str,
        model_name: str,
        registry: CommandRegistry | None = None,
        compressor: Compressor | None = None,
        agent_package_path: Path | None = None,
        skill_discovery: SkillDiscovery | None = None,
        skill_activator: SkillActivator | None = None,
        workspace_path: Path | None = None,
    ) -> None:
        """
        Initialize REPL runtime.

        Args:
            session: The current session.
            agent: The agent instance.
            context_builder: Host's ContextRebuilder for prompt orchestration.
            provider_name: Current provider name.
            model_name: Current model name.
            registry: Optional command registry (defaults to built-in commands).
            compressor: Optional compressor for manual context compression (ADR-015).
            agent_package_path: Path to agent package directory (for mode discovery).
            skill_discovery: Optional SkillDiscovery for skill management.
            skill_activator: Optional SkillActivator for active skill management.
            workspace_path: Optional workspace path for skill discovery.
        """
        self._session = session
        self._agent = agent
        self._context_builder = context_builder
        self._provider_name = provider_name
        self._model_name = model_name
        self._registry = registry or create_default_registry()
        self._compressor = compressor
        self._agent_package_path = agent_package_path
        self._skill_discovery = skill_discovery
        self._skill_activator = skill_activator
        self._workspace_path = workspace_path
        self._host_binding = None  # For /rebind command (ADR-026)

    def set_host_binding(self, binding: Any) -> None:
        """Set the StableHostBinding for capability rebind (ADR-026)."""
        self._host_binding = binding

    @property
    def session(self) -> Session:
        """Get the current session."""
        return self._session

    @property
    def state(self) -> ReplState:
        """Get a snapshot of current REPL state."""
        return ReplState(
            provider_name=self._provider_name,
            model_name=self._model_name,
            mode=self._session.mode,
        )

    def _build_command_context(self) -> CommandContext:
        """Build a CommandContext with current state."""
        return CommandContext(
            session=self._session,
            agent=self._agent,
            model=self._agent.model,
            storage=self._agent.storage,
            context_builder=self._context_builder,
            compressor=self._compressor,
            agent_package_path=self._agent_package_path,
            skill_discovery=self._skill_discovery,
            skill_activator=self._skill_activator,
            workspace_path=self._workspace_path,
            host_binding=self._host_binding,
        )

    def get_command_candidates(
        self,
        command_name: str,
        args: str,
    ) -> list[CommandCandidate]:
        """
        Get candidates for a command's arguments.

        This is the primary interface for CommandCompleter to get structured
        candidates from the Slash Command System.

        Args:
            command_name: The command name (without slash).
            args: Current argument string.

        Returns:
            List of CommandCandidate objects for the next argument position.
        """
        command = self._registry.get(command_name)
        if command is None:
            return []

        # Try the new get_candidates method first
        if hasattr(command, "get_candidates"):
            context = self._build_command_context()
            try:
                return command.get_candidates(args, context)
            except Exception:
                # Fall back to empty on error
                return []

        return []

    def resolve_command(
        self,
        command_name: str,
        args: str,
    ) -> CommandResolution:
        """
        Resolve command arguments to determine next action.

        Args:
            command_name: The command name (without slash).
            args: Current argument string.

        Returns:
            A CommandResolution describing the state.
        """
        command = self._registry.get(command_name)
        if command is None:
            return CommandResolution(
                status="invalid",
                message=f"Unknown command: `{command_name}`",
            )

        if hasattr(command, "resolve"):
            context = self._build_command_context()
            try:
                return command.resolve(args, context)
            except Exception as e:
                return CommandResolution(
                    status="invalid",
                    message=str(e),
                )

        # Default: assume ready if args provided
        return CommandResolution(
            status="ready" if args.strip() else "needs_input",
        )

    def execute_command(self, input_text: str) -> CommandResult | None:
        """
        Execute a slash command or return None if not a command.

        This handles:
        - Slash command parsing and dispatch
        - State patch application
        - Context rebuilding (Host layer responsibility)

        Args:
            input_text: User input (may or may not be a slash command).

        Returns:
            CommandResult if input was a command, None otherwise.
        """
        if not input_text.startswith("/"):
            return None

        # Parse command name and arguments
        cmd_name, _, cmd_args = input_text[1:].partition(" ")
        command = self._registry.get(cmd_name)

        if command is None:
            return CommandResult(
                status="error",
                message=f"❌ Unknown command: `{input_text}`. Type `/help` for available commands.",
            )

        # Build command context
        cmd_context = self._build_command_context()

        # Execute command
        result = command.execute(cmd_args, cmd_context)

        # Apply state changes (Host layer responsibility)
        if result.state_patch:
            self._apply_state_patch(result.state_patch)

        # Rebuild context if needed (Host layer responsibility)
        if result.rebuild_context:
            self._rebuild_context()

        return result

    def _apply_state_patch(self, patch: dict) -> None:
        """
        Apply a state patch to session and runtime.

        This is Host layer logic - deciding what to store where.
        Action flags (reset, exit) are filtered out.
        Model/provider changes are tracked in runtime state.
        """
        for key, value in patch.items():
            # Action flags, not actual state to store
            if key in ("reset", "exit"):
                continue

            # Store in session metadata (persistent)
            self._session.state.metadata[key] = value

            # Track provider/model changes in runtime state
            if key == "model_provider":
                self._provider_name = value
            elif key == "model_name":
                self._model_name = value
            elif key == "mode":
                # Mode is already stored via metadata above
                pass
            elif key == "skills" and self._host_binding is not None:
                self._host_binding.active_skill_names = list(value)

    def _rebuild_context(self) -> None:
        """
        Rebuild the system prompt with current state.

        This is Host layer orchestration:
        - ContextRebuilder handles the composition logic
        - Session.set_system_prompt() handles the state update
        """
        if self._host_binding is not None:
            self._host_binding.provider_name = self._provider_name
            self._host_binding.model_name = self._model_name
            snapshot = refresh_run_context(self._host_binding, session_id=self._session.id)
            new_prompt = snapshot.composed_prompt

            # Keep the in-memory skill managers aligned with the fresh snapshot.
            if self._skill_activator is not None:
                self._skill_activator.active_skill_names = list(self._host_binding.active_skill_names)
                self._skill_activator.transient_active_skill_names = list(
                    self._host_binding.transient_skill_names
                )
        else:
            # Fallback to the older context builder path when no host binding exists.
            new_prompt = self._context_builder.rebuild(
                provider=self._provider_name,
                model=self._model_name,
                session_id=self._session.id,
                mode=self._session.mode,
            )

        # Apply to session (session stores it)
        self._session.set_system_prompt(new_prompt)

        # Also apply to agent for consistency
        self._agent.set_system_prompt(new_prompt)

    def activate_skills(self, skill_names: list[str], *, transient: bool = True) -> list[str]:
        """
        Activate discovered skills and rebuild prompt context.

        Returns the subset of requested names that were newly activated.
        """
        if self._skill_activator is None:
            return []

        activated: list[str] = []
        for name in skill_names:
            if self._skill_activator.is_active(name):
                continue
            skill = self._skill_activator.activate_skill(name, transient=transient)
            if skill is not None:
                activated.append(name)

        if not activated:
            return []

        if self._host_binding is not None:
            self._host_binding.active_skill_names = self._skill_activator.list_persistent()
            self._host_binding.transient_skill_names = self._skill_activator.list_transient()

        self._session.state.metadata["skills"] = self._skill_activator.list_persistent()
        self._rebuild_context()
        return activated

    def clear_transient_skills(self) -> bool:
        """Clear transient skills and rebuild context if anything changed."""
        if self._skill_activator is None or not self._skill_activator.list_transient():
            return False

        self._skill_activator.clear_transient()
        if self._host_binding is not None:
            self._host_binding.active_skill_names = self._skill_activator.list_persistent()
            self._host_binding.transient_skill_names = []
        self._session.state.metadata["skills"] = self._skill_activator.list_persistent()
        self._rebuild_context()
        return True

    def list_available_skill_names(self) -> set[str]:
        """List discovered skill names from the current discovery sources."""
        if self._skill_discovery is None:
            return set()
        return {skill.name for skill in self._skill_discovery.discover_skills()}

    def list_active_skill_names(self) -> set[str]:
        """List active skill names."""
        if self._skill_activator is None:
            return set()
        return set(self._skill_activator.list_active())

    def create_skill_activation_handler(self):
        """
        Create a skill activation handler for Run (ADR-027).

        Returns a callable that can be passed to Run.skill_activation_handler.
        When called, it activates the requested skills and returns the updated
        system prompt.

        Returns:
            A callable that takes a list of skill names and returns the updated
            system prompt, or None if no update is needed.
        """
        def handler(skill_names: list[str]) -> str | None:
            if not skill_names or self._skill_activator is None:
                return None

            # Activate the skills
            activated = self.activate_skills(skill_names, transient=True)

            if not activated:
                return None

            # Rebuild context with new skills
            self._rebuild_context()

            # Return the updated system prompt
            return self._session.system_prompt

        return handler

    def get_completions(self, prefix: str) -> list[str]:
        """
        Get command completions for a prefix.

        Args:
            prefix: The partial input (e.g., "/mod").

        Returns:
            List of completion suggestions.
        """
        if not prefix.startswith("/"):
            return []

        cmd_name, _, args = prefix[1:].partition(" ")

        # If we have a space, delegate to command for argument completion
        if " " in prefix[1:]:
            # Try new candidate system first
            candidates = self.get_command_candidates(cmd_name, args)
            if candidates:
                # Return the value field for insertion
                return [c.value for c in candidates]

            # Fall back to legacy get_completions
            command = self._registry.get(cmd_name)
            if command is not None:
                arg_completions = getattr(command, "get_completions", lambda x: [])(args)
                return [f"/{cmd_name} {c}" for c in arg_completions]
            return []

        # Complete command names
        completions = []
        for cmd in self._registry.list_commands():
            if cmd.name.startswith(cmd_name.lower()):
                completions.append(f"/{cmd.name}")
        return completions

    def is_command(self, input_text: str) -> bool:
        """Check if input is a slash command."""
        return input_text.startswith("/")

    def is_exit_requested(self, result: CommandResult) -> bool:
        """Check if a command result requests exit."""
        return result.action == ReplAction.EXIT


__all__ = [
    "ReplState",
    "ReplRuntime",
]
