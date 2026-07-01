"""
Agent definition for Kora.

An Agent is defined by:
- A name
- A system prompt (optional)
- A set of tools

This module provides both the protocol and convenience implementations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from kora.runtime.session import Session, SessionState

if TYPE_CHECKING:
    from kora.kernel.model import Model
    from kora.kernel.tool import Tool
    from kora.runtime.compressor import Compressor
    from kora.runtime.events import AnyEvent
    from kora.host.compression_policy import CompressionPolicy
    from kora.host.storage import Storage
    from kora.runtime.tool_policy import ToolSelectionPolicy, ToolResultProcessingPolicy
    from kora.runtime.termination import TerminationPolicy
    from kora.runtime.trace import TraceSink


@runtime_checkable
class AgentDefinition(Protocol):
    """
    Protocol for agent definitions.

    An agent definition provides the static configuration for an agent.
    This is the "blueprint" - sessions and runs are created from this.
    """

    @property
    def name(self) -> str:
        """The unique name of the agent."""
        ...

    @property
    def system_prompt(self) -> str | None:
        """The system prompt for the agent, or None if not needed."""
        ...

    @property
    def tools(self) -> list[Tool]:
        """The tools available to this agent."""
        ...


@dataclass(frozen=True)
class AgentConfig:
    """
    Immutable configuration for an agent.

    This is the default implementation of AgentDefinition.
    Use this for programmatic agent creation.
    """

    name: str
    system_prompt: str | None = None
    tools: list[Tool] = field(default_factory=list)


class Agent:
    """
    An agent with tools and optional model.

    Provides two execution modes:
    - run(): One-shot execution (creates temporary session)
    - open_session(): Persistent conversation session

    Example:
        ```python
        from kora import Agent, tool

        @tool
        def echo(msg: str) -> str:
            '''Echo a message.'''
            return msg

        agent = Agent(name="assistant", tools=[echo], model=model)

        # One-shot
        result = await agent.run("Hello!")

        # Persistent session
        session = agent.open_session()
        result = await session.send("Hello!")
        result = await session.send("Continue...")
        ```
    """

    def __init__(
        self,
        name: str,
        *,
        system_prompt: str | None = None,
        tools: list[Tool] | None = None,
        model: Model | None = None,
        storage: Storage | None = None,
        compression_policy: CompressionPolicy | None = None,
        compressor: Compressor | None = None,
        tool_selection_policy: ToolSelectionPolicy | None = None,
        tool_result_processing_policy: ToolResultProcessingPolicy | None = None,
        termination_policy: TerminationPolicy | None = None,
        trace_sink: TraceSink | None = None,
    ) -> None:
        """
        Create an agent.

        Args:
            name: The agent name.
            system_prompt: Optional system prompt.
            tools: List of tools available to the agent.
            model: The model to use. If not provided, must set when running.
            storage: Optional storage for session/run persistence.
            compression_policy: Optional compression policy (ADR-015).
            compressor: Optional compressor for context compression (ADR-015).
            tool_selection_policy: Optional tool selection policy (ADR-023).
            tool_result_processing_policy: Optional tool result processing policy (ADR-023).
            termination_policy: Optional termination policy (ADR-021).
            trace_sink: Optional trace sink for event recording (ADR-016).
        """
        self._config = AgentConfig(
            name=name,
            system_prompt=system_prompt,
            tools=tools or [],
        )
        self._model = model
        self._storage = storage
        self._compression_policy = compression_policy
        self._compressor = compressor
        self._tool_selection_policy = tool_selection_policy
        self._tool_result_processing_policy = tool_result_processing_policy
        self._termination_policy = termination_policy
        self._trace_sink = trace_sink

    @property
    def name(self) -> str:
        """The agent name."""
        return self._config.name

    @property
    def config(self) -> AgentConfig:
        """The underlying agent configuration."""
        return self._config

    @property
    def model(self) -> Model | None:
        """The default model for this agent."""
        return self._model

    @property
    def storage(self) -> Storage | None:
        """The storage backend."""
        return self._storage

    @property
    def system_prompt(self) -> str | None:
        """The agent's system prompt."""
        return self._config.system_prompt

    @property
    def tools(self) -> list[Tool]:
        """The agent's tools."""
        return self._config.tools

    @property
    def tool_selection_policy(self) -> ToolSelectionPolicy | None:
        """The tool selection policy (ADR-023)."""
        return self._tool_selection_policy

    @property
    def tool_result_processing_policy(self) -> ToolResultProcessingPolicy | None:
        """The tool result processing policy (ADR-023)."""
        return self._tool_result_processing_policy

    @property
    def termination_policy(self) -> TerminationPolicy | None:
        """The termination policy (ADR-021)."""
        return self._termination_policy

    @property
    def trace_sink(self) -> TraceSink | None:
        """The trace sink (ADR-016)."""
        return self._trace_sink

    def set_model(self, model: Model) -> None:
        """Set the default model for this agent."""
        self._model = model

    def set_system_prompt(self, system_prompt: str | None) -> None:
        """
        Update the agent's system prompt at runtime.

        This is used by ContextRebuilder to re-render template variables
        after state changes like model switching.

        Args:
            system_prompt: The new system prompt text, or None to clear.
        """
        from dataclasses import replace
        self._config = replace(self._config, system_prompt=system_prompt)

    def set_storage(self, storage: Storage) -> None:
        """Set the storage backend."""
        self._storage = storage

    def open_session(self, *, session_id: str | None = None) -> Session:
        """
        Open a persistent session for multi-turn conversation.

        Args:
            session_id: Optional custom session ID.

        Returns:
            A Session with execution context (can call send()).
        """
        state = SessionState.create(self._config.name, session_id=session_id)
        return Session(
            state=state,
            agent=self._config,
            model=self._model,
            storage=self._storage,
            compression_policy=self._compression_policy,
            compressor=self._compressor,
            tool_selection_policy=self._tool_selection_policy,
            tool_result_processing_policy=self._tool_result_processing_policy,
            termination_policy=self._termination_policy,
            trace_sink=self._trace_sink,
        )

    def load_session(self, session_id: str) -> Session | None:
        """
        Resume a previous session from storage.

        Args:
            session_id: The session ID to load.

        Returns:
            A Session instance, or None if not found.

        Raises:
            ValueError: If no storage is configured.
        """
        if self._storage is None:
            raise ValueError("No storage configured. Pass storage to Agent.")
        return Session.load(
            session_id,
            self._storage,
            self._config,
            self._model,
            compression_policy=self._compression_policy,
            compressor=self._compressor,
            tool_selection_policy=self._tool_selection_policy,
            tool_result_processing_policy=self._tool_result_processing_policy,
            termination_policy=self._termination_policy,
            trace_sink=self._trace_sink,
        )

    def list_sessions(self) -> list[SessionState]:
        """
        List all sessions for this agent.

        Returns:
            List of session states.

        Raises:
            ValueError: If no storage is configured.
        """
        if self._storage is None:
            raise ValueError("No storage configured. Pass storage to Agent.")
        return self._storage.list_sessions(agent_name=self._config.name)

    async def run(
        self,
        message: str,
        *,
        model: Model | None = None,
        on_event: Callable[[AnyEvent], None] | None = None,
    ) -> str:
        """
        One-shot execution (creates temporary session).

        Args:
            message: The user message.
            model: Optional model override.
            on_event: Optional callback for events.

        Returns:
            The agent's response text.

        Raises:
            ValueError: If no model is configured.
        """
        # Create temporary session
        state = SessionState.create(self._config.name)
        session = Session(state=state, agent=self._config, model=model or self._model)

        return await session.send(message, on_event=on_event)

    def run_sync(
        self,
        message: str,
        *,
        model: Model | None = None,
        on_event: Callable[[AnyEvent], None] | None = None,
    ) -> str:
        """
        Synchronous one-shot execution.

        Args:
            message: The user message.
            model: Optional model override.
            on_event: Optional callback for events.

        Returns:
            The agent's response text.
        """
        return asyncio.run(self.run(message, model=model, on_event=on_event))
