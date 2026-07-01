"""
Tests for Host layer agent loader.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from kora.host import load_agent_from_markdown
from kora.runtime import AgentConfig


class TestLoadAgentFromMarkdown:
    """Tests for load_agent_from_markdown."""

    def test_load_basic_agent(self) -> None:
        """Test loading a basic agent from markdown."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: test-agent
---

You are a helpful assistant.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert isinstance(agent, AgentConfig)
            assert agent.name == "test-agent"
            assert agent.system_prompt == "You are a helpful assistant."

    def test_load_agent_with_tools_list(self) -> None:
        """Test loading agent with tools list in frontmatter."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: my-agent
tools: [echo, calculate]
---

You are a calculator.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "my-agent"
            # Note: tools are not loaded by the loader, must be added separately
            assert agent.tools == []

    def test_load_agent_without_name_uses_directory(self) -> None:
        """Test that agent name defaults to directory name if not specified."""
        with TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir) / "my-cool-agent"
            agent_dir.mkdir()
            agent_path = agent_dir / "AGENT.md"
            agent_path.write_text("""---
---

You are helpful.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "my-cool-agent"

    def test_load_agent_with_empty_system_prompt(self) -> None:
        """Test loading agent with empty system prompt."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: empty-agent
---
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "empty-agent"
            assert agent.system_prompt is None

    def test_load_agent_with_multiline_prompt(self) -> None:
        """Test loading agent with multiline system prompt."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: complex-agent
---

You are a helpful assistant.

## Instructions

1. Be polite
2. Be accurate
3. Be concise

## Tools

- Use the echo tool for testing
- Use the calculate tool for math
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "complex-agent"
            assert "## Instructions" in agent.system_prompt
            assert "1. Be polite" in agent.system_prompt

    def test_load_agent_file_not_found(self) -> None:
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_agent_from_markdown("/nonexistent/path/AGENT.md")

    def test_load_agent_missing_frontmatter(self) -> None:
        """Test error when file doesn't have frontmatter."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""You are a helpful assistant.

This file has no frontmatter.
""", encoding="utf-8")

            with pytest.raises(ValueError, match="must start with '---'"):
                load_agent_from_markdown(agent_path)

    def test_load_agent_invalid_frontmatter(self) -> None:
        """Test error when frontmatter is incomplete."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: test-agent

You are helpful.
""", encoding="utf-8")

            with pytest.raises(ValueError, match="Invalid agent file format"):
                load_agent_from_markdown(agent_path)

    def test_load_agent_with_quoted_name(self) -> None:
        """Test loading agent with quoted name in frontmatter."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: "my-special-agent"
---

You are helpful.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "my-special-agent"

    def test_load_agent_with_single_quoted_name(self) -> None:
        """Test loading agent with single-quoted name."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: 'my-agent'
---

You are helpful.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "my-agent"

    def test_load_agent_accepts_string_path(self) -> None:
        """Test that loader accepts string path as well as Path."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: string-path-agent
---

You are helpful.
""", encoding="utf-8")

            # Pass string instead of Path
            agent = load_agent_from_markdown(str(agent_path))

            assert agent.name == "string-path-agent"

    def test_load_agent_with_extra_fields(self) -> None:
        """Test that extra fields in frontmatter are ignored."""
        with TemporaryDirectory() as tmpdir:
            agent_path = Path(tmpdir) / "AGENT.md"
            agent_path.write_text("""---
name: extra-fields-agent
version: 1.0
author: Test Author
description: A test agent
---

You are helpful.
""", encoding="utf-8")

            agent = load_agent_from_markdown(agent_path)

            assert agent.name == "extra-fields-agent"
            assert agent.system_prompt == "You are helpful."
