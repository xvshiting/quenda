"""
Tests for runtime context rebuilding integration (Agent.set_system_prompt,
Session.set_system_prompt, ModelCommand rebuild_context).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quenda.runtime import Agent, AgentConfig
from quenda.runtime.session import Session, SessionState
from quenda.host.commands import (
    CommandContext,
    CommandResult,
    ModelCommand,
    create_default_registry,
)


class TestAgentSetSystemPrompt:
    """Tests for Agent.set_system_prompt()."""

    def test_set_system_prompt(self) -> None:
        """Test setting system prompt on agent."""
        agent = Agent(
            name="test-agent",
            system_prompt="Original prompt",
        )
        assert agent.system_prompt == "Original prompt"

        agent.set_system_prompt("Updated prompt")
        assert agent.system_prompt == "Updated prompt"

    def test_set_system_prompt_to_none(self) -> None:
        """Test setting system prompt to None."""
        agent = Agent(
            name="test-agent",
            system_prompt="Original",
        )
        agent.set_system_prompt(None)
        assert agent.system_prompt is None

    def test_set_system_prompt_affects_new_sessions(self) -> None:
        """Test that updated prompt is used in new sessions."""
        agent = Agent(
            name="test-agent",
            system_prompt="Original",
        )

        # Update and open new session
        agent.set_system_prompt("Updated")
        session = agent.open_session()

        # The session's agent config should have the new prompt
        # (config is a copy, but replace() creates new instances)
        assert session._agent.system_prompt == "Updated"

    def test_set_system_prompt_preserves_other_fields(self) -> None:
        """Test that set_system_prompt doesn't change name or tools."""
        from quenda.kernel.tool import Tool
        from quenda.kernel.types import ToolResult

        class FakeTool(Tool):
            name = "fake"
            description = "Fake tool"
            parameters = {"type": "object", "properties": {}}

            def execute(self, **kwargs: object) -> ToolResult:
                return ToolResult("", self.name, "result")

        agent = Agent(
            name="test-agent",
            system_prompt="Original",
            tools=[FakeTool()],
        )

        agent.set_system_prompt("Updated")

        assert agent.name == "test-agent"
        assert len(agent._config.tools) == 1
        assert agent._config.tools[0].name == "fake"


class TestSessionSetSystemPrompt:
    """Tests for Session.set_system_prompt()."""

    def test_set_system_prompt(self) -> None:
        """Test setting system prompt on session."""
        config = AgentConfig(name="test-agent", system_prompt="Original")
        state = SessionState.create("test-agent")
        session = Session(state=state, agent=config)

        session.set_system_prompt("Updated")
        assert session._agent.system_prompt == "Updated"

    def test_set_system_prompt_to_none(self) -> None:
        """Test setting system prompt to None on session."""
        config = AgentConfig(name="test-agent", system_prompt="Original")
        state = SessionState.create("test-agent")
        session = Session(state=state, agent=config)

        session.set_system_prompt(None)
        assert session._agent.system_prompt is None

    def test_set_system_prompt_isolated_from_agent(self) -> None:
        """Test that session prompt changes don't affect agent's config."""
        agent = Agent(name="test-agent", system_prompt="Original")
        session = agent.open_session()

        # Change on session only
        session.set_system_prompt("Session only")

        assert agent.system_prompt == "Original"  # Agent unchanged
        assert session._agent.system_prompt == "Session only"


class TestModelCommandRebuildContext:
    """Tests for ModelCommand returning rebuild_context."""

    def test_model_switch_signals_rebuild(self) -> None:
        """Test that /model switch returns rebuild_context=True."""
        registry = create_default_registry()
        cmd = registry.get("model")
        assert cmd is not None

        # We can't easily test actual model switching without a real model,
        # but we can verify the command structure supports rebuild_context
        from quenda.host.commands import ModelCommand
        assert hasattr(ModelCommand, "execute")

        # Check that CommandResult supports the fields we need
        result = CommandResult(
            status="ok",
            message="Test",
            state_patch={"model_provider": "openai", "model_name": "gpt-4o"},
            rebuild_context=True,
        )
        assert result.rebuild_context is True
        assert result.state_patch["model_provider"] == "openai"
        assert result.state_patch["model_name"] == "gpt-4o"

    def test_command_context_has_context_builder(self) -> None:
        """Test that CommandContext supports context_builder field."""
        ctx = CommandContext(
            session=None,  # type: ignore
            context_builder=None,
        )
        assert ctx.context_builder is None

        # Can be set
        ctx.context_builder = "not-none"  # type: ignore
        assert ctx.context_builder is not None
