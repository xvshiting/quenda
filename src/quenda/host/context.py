"""
Context rebuilding for Quenda Host layer.

Provides ContextRebuilder that re-composes the Agent's system prompt
when runtime state changes (model switch, etc.).

This connects the Instruction Layer (ADR-007) with runtime state changes.
When the model changes, template variables like {{model.provider}} and
{{model.name}} need to be re-rendered into the composed instructions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from quenda.host.instructions import (
    InstructionComposer,
    InstructionScope,
    InstructionSource,
    TemplateContext,
    resolve_instruction_sources,
)

if TYPE_CHECKING:
    from quenda.host.identity import User
    from quenda.runtime.agent import Agent


class ContextRebuilder:
    """
    Rebuilds the Agent's system prompt when state changes.

    This connects the Instruction Layer (ADR-007) with runtime state changes
    like model switching. When the model changes, template variables like
    ``{{model.provider}}`` and ``{{model.name}}`` need to be re-rendered.

    The rebuilder is initialized with the static pieces of the instruction
    puzzle (agent package, workspace identity) and called with the dynamic
    pieces (current model, session) each time a rebuild is needed.

    Usage:
        rebuilder = ContextRebuilder(
            agent_name="quenda-code",
            agent_version="0.1.0",
            agent_md_content="You are...",
            agent_instructions=[...],
            agent_package_path=Path("agents/quenda-code"),
            workspace_path=Path("."),
            workspace_id="ws_abc123",
            user=user,
        )

        # Rebuild after /model switch
        rebuilder.apply(agent, provider="anthropic", model="claude-sonnet-4-20250514")
    """

    def __init__(
        self,
        *,
        agent_name: str,
        agent_version: str,
        agent_md_content: str,
        agent_instructions: list[InstructionSource],
        agent_package_path: Path,
        workspace_path: Path,
        workspace_id: str,
        user: User,
    ) -> None:
        """
        Initialize the ContextRebuilder with static context.

        Args:
            agent_name: Agent name (e.g., "quenda-code").
            agent_version: Agent version (e.g., "0.1.0").
            agent_md_content: The base prompt from AGENT.md.
            agent_instructions: Included instructions from agent package.
            agent_package_path: Path to agent package directory.
            workspace_path: Workspace root directory.
            workspace_id: Resolved workspace binding ID.
            user: The current user identity.
        """
        self._agent_name = agent_name
        self._agent_version = agent_version
        self._agent_md_content = agent_md_content
        self._agent_instructions = list(agent_instructions)
        self._agent_package_path = agent_package_path
        self._workspace_path = workspace_path
        self._workspace_id = workspace_id
        self._user = user

    def rebuild(
        self,
        *,
        provider: str,
        model: str,
        session_id: str,
        mode: str = "chat",
    ) -> str:
        """
        Re-compose the system prompt with current state values.

        Re-resolves instruction sources (to pick up any changed workspace
        or user override files) and re-renders template variables with
        the provided values.

        Args:
            provider: Current model provider (e.g., "anthropic").
            model: Current model name (e.g., "claude-sonnet-4-20250514").
            session_id: Current session ID.
            mode: Current interaction mode ("chat", "code", "architect").

        Returns:
            The newly composed system prompt text.
        """
        # 1. Re-resolve instruction sources (picks up file changes)
        sources = resolve_instruction_sources(
            agent_package_path=self._agent_package_path,
            agent_name=self._agent_name,
            agent_md_content=self._agent_md_content,
            agent_instructions=self._agent_instructions,
            workspace_path=self._workspace_path,
            user=self._user,
        )

        # 2. Resolve mode-specific instructions from agent package
        mode_instructions = self._resolve_mode_instructions(mode)
        sources.extend(mode_instructions)

        # 3. Build fresh template context with current state
        context = TemplateContext(
            agent_name=self._agent_name,
            agent_version=self._agent_version,
            workspace_id=self._workspace_id,
            workspace_path=str(self._workspace_path),
            user_id=self._user.id,
            model_provider=provider,
            model_name=model,
            date=datetime.now().strftime("%Y-%m-%d"),
            session_id=session_id,
            mode=mode,
        )

        # 4. Re-compose
        composer = InstructionComposer(context)
        return composer.compose(sources)

    def _resolve_mode_instructions(self, mode: str) -> list[InstructionSource]:
        """
        Resolve mode-specific instructions from the agent package.

        Looks for <agent_package>/instructions/mode-<mode>.md files.

        Args:
            mode: The current mode name.

        Returns:
            List of instruction sources for the mode, or empty list.
        """
        mode_file = self._agent_package_path / "instructions" / f"mode-{mode}.md"
        if mode_file.exists():
            return [
                InstructionSource(
                    scope=InstructionScope.AGENT_INSTRUCTIONS,
                    content=mode_file.read_text(encoding="utf-8"),
                    path=mode_file,
                )
            ]
        return []

    def apply(
        self,
        agent: Agent,
        *,
        provider: str,
        model: str,
        session_id: str,
        mode: str = "chat",
    ) -> str:
        """
        Rebuild context and apply it to an Agent.

        This is a convenience method that combines rebuild() with
        agent.set_system_prompt().

        Args:
            agent: The Agent instance to update.
            provider: Current model provider.
            model: Current model name.
            session_id: Current session ID.
            mode: Current interaction mode.

        Returns:
            The newly composed system prompt (already set on the agent).
        """
        new_prompt = self.rebuild(
            provider=provider,
            model=model,
            session_id=session_id,
            mode=mode,
        )
        agent.set_system_prompt(new_prompt)
        return new_prompt


__all__ = [
    "ContextRebuilder",
]
