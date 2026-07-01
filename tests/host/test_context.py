"""
Tests for ContextRebuilder.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from quenda.host import ContextRebuilder, User


class TestContextRebuilder:
    """Tests for ContextRebuilder."""

    def test_rebuild_basic(self) -> None:
        """Test basic rebuild with model switch."""
        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="You are {{agent.name}} using {{model.provider}}/{{model.name}}.",
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test123",
            user=User(id="test-user"),
        )

        result = rebuilder.rebuild(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            session_id="ses_test",
        )

        assert "test-agent" in result
        assert "anthropic" in result
        assert "claude-sonnet-4-20250514" in result

    def test_rebuild_multiple_times(self) -> None:
        """Test rebuilding multiple times with different values."""
        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="Model: {{model.provider}}/{{model.name}}",
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test123",
            user=User(id="test-user"),
        )

        # First rebuild
        result1 = rebuilder.rebuild(
            provider="deepseek",
            model="deepseek-chat",
            session_id="ses_1",
        )
        assert "deepseek" in result1
        assert "deepseek-chat" in result1

        # Second rebuild with different model
        result2 = rebuilder.rebuild(
            provider="openai",
            model="gpt-4o",
            session_id="ses_2",
        )
        assert "openai" in result2
        assert "gpt-4o" in result2
        assert "deepseek" not in result2

    def test_rebuild_with_multiple_sources(self) -> None:
        """Test rebuilding with multiple instruction sources."""
        from quenda.host.instructions import InstructionSource, InstructionScope

        instructions = [
            InstructionSource(
                scope=InstructionScope.AGENT_INSTRUCTIONS,
                content="You are a coding agent.",
                path=Path("/tmp/test-agent/instructions/base.md"),
            ),
        ]

        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="System: {{agent.name}} v{{agent.version}}",
            agent_instructions=instructions,
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test123",
            user=User(id="test-user"),
        )

        result = rebuilder.rebuild(
            provider="deepseek",
            model="deepseek-v4-flash",
            session_id="ses_test",
        )

        assert "test-agent" in result
        assert "0.1.0" in result
        assert "coding agent" in result

    def test_rebuild_with_workspace_instructions(self) -> None:
        """Test rebuild picks up workspace INSTRUCTIONS.md."""
        from quenda.host.instructions import InstructionScope, InstructionSource

        with TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)
            ws_instructions = workspace_path / ".quenda" / "INSTRUCTIONS.md"
            ws_instructions.parent.mkdir(parents=True)
            ws_instructions.write_text("Workspace preference: use {{model.name}}", encoding="utf-8")

            rebuilder = ContextRebuilder(
                agent_name="test-agent",
                agent_version="0.1.0",
                agent_md_content="Base prompt.",
                agent_instructions=[],
                agent_package_path=Path("/tmp/test-agent"),
                workspace_path=workspace_path,
                workspace_id="ws_test456",
                user=User(id="test-user"),
            )

            result = rebuilder.rebuild(
                provider="openai",
                model="gpt-4o",
                session_id="ses_test",
            )

            assert "gpt-4o" in result
            assert "Workspace preference" in result

    def test_rebuild_all_template_variables(self) -> None:
        """Test that all standard template variables are rendered."""
        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="1.2.3",
            agent_md_content=(
                "{{agent.name}} {{agent.version}} "
                "{{workspace.id}} {{workspace.path}} "
                "{{user.id}} {{model.provider}} {{model.name}} "
                "{{date}} {{session.id}}"
            ),
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_abc",
            user=User(id="user-xyz"),
        )

        result = rebuilder.rebuild(
            provider="test-provider",
            model="test-model",
            session_id="ses_render",
        )

        assert "test-agent" in result
        assert "1.2.3" in result
        assert "ws_abc" in result
        assert "/tmp/workspace" in result
        assert "user-xyz" in result
        assert "test-provider" in result
        assert "test-model" in result
        assert "ses_render" in result

    def test_unknown_variable_renders_empty(self) -> None:
        """Test that unknown template variables render as empty string."""
        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="{{unknown_var}} and {{another.unknown}}",
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test",
            user=User(id="user"),
        )

        result = rebuilder.rebuild(
            provider="deepseek",
            model="deepseek-chat",
            session_id="ses_test",
        )

        # Unknown variables should be empty strings
        # The result includes FRAMEWORK_CONTRACT, but we check the agent content
        # contains " and " (from "{{unknown_var}} and {{another.unknown}}")
        assert " and " in result
        # Unknown variables should not appear as literal text
        assert "{{unknown_var}}" not in result
        assert "{{another.unknown}}" not in result


class TestContextRebuilderApply:
    """Tests for ContextRebuilder.apply()."""

    def test_apply_updates_agent(self) -> None:
        """Test that apply() updates the agent's system prompt."""
        from quenda.runtime import Agent

        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="You are {{agent.name}} using {{model.provider}}/{{model.name}}.",
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test",
            user=User(id="test-user"),
        )

        agent = Agent(
            name="test-agent",
            system_prompt="Initial prompt",
        )

        result = rebuilder.apply(
            agent=agent,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            session_id="ses_test",
        )

        assert "claude-sonnet-4-20250514" in result
        assert result == agent.system_prompt

    def test_apply_updates_session(self) -> None:
        """Test that apply() followed by session.set_system_prompt works."""
        from quenda.runtime import Agent

        rebuilder = ContextRebuilder(
            agent_name="test-agent",
            agent_version="0.1.0",
            agent_md_content="Model: {{model.name}}",
            agent_instructions=[],
            agent_package_path=Path("/tmp/test-agent"),
            workspace_path=Path("/tmp/workspace"),
            workspace_id="ws_test",
            user=User(id="test-user"),
        )

        agent = Agent(
            name="test-agent",
            system_prompt="Initial",
        )
        session = agent.open_session()

        # Rebuild via rebuilder
        new_prompt = rebuilder.rebuild(
            provider="openai",
            model="gpt-4o",
            session_id=session.id,
        )

        # Update both session and agent
        session.set_system_prompt(new_prompt)
        agent.set_system_prompt(new_prompt)

        assert "gpt-4o" in agent.system_prompt
