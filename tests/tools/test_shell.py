"""
Tests for shell execution tool.
"""

import tempfile
from pathlib import Path

import pytest

from quenda.tools.execution import RunShellTool, ShellConfig


class TestRunShellTool:
    """Tests for RunShellTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_simple_command_success(self, temp_dir: Path) -> None:
        """Test executing a simple command."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="echo 'hello world'")

        assert not result.is_error
        assert "hello world" in result.content

    def test_command_with_output(self, temp_dir: Path) -> None:
        """Test command that produces output."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="ls")

        assert not result.is_error

    def test_command_in_working_directory(self, temp_dir: Path) -> None:
        """Test command runs in specified directory."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file.txt").write_text("content")

        tool = RunShellTool(temp_dir)
        result = tool.execute(command="ls", cwd="subdir")

        assert not result.is_error
        assert "file.txt" in result.content

    def test_command_timeout(self, temp_dir: Path) -> None:
        """Test command timeout."""
        tool = RunShellTool(temp_dir, ShellConfig(default_timeout=1))
        result = tool.execute(command="sleep 10", timeout=1)

        assert result.is_error
        assert "timed out" in result.content.lower()

    def test_blocked_command_rm_rf(self, temp_dir: Path) -> None:
        """Test rm -rf / is blocked."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="rm -rf /")

        assert result.is_error
        assert "blocked" in result.content.lower()

    def test_blocked_command_fork_bomb(self, temp_dir: Path) -> None:
        """Test fork bomb is blocked."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command=":(){ :|:& };:")

        assert result.is_error

    def test_blocked_command_mkfs(self, temp_dir: Path) -> None:
        """Test mkfs is blocked."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="mkfs.ext4 /dev/sda1")

        assert result.is_error

    def test_working_directory_escape_blocked(self, temp_dir: Path) -> None:
        """Test working directory outside workspace is blocked."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="ls", cwd="../..")

        assert result.is_error

    def test_nonzero_exit_code_is_error(self, temp_dir: Path) -> None:
        """Test non-zero exit code is treated as error."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="exit 1")

        assert result.is_error

    def test_command_not_found(self, temp_dir: Path) -> None:
        """Test command not found."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="nonexistent_command_xyz")

        assert result.is_error

    def test_stderr_captured(self, temp_dir: Path) -> None:
        """Test stderr is captured."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="echo 'error' >&2")

        assert "stderr" in result.content or "error" in result.content


class TestShellConfig:
    """Tests for ShellConfig."""

    def test_default_timeout(self) -> None:
        """Test default timeout value."""
        config = ShellConfig()
        assert config.default_timeout == 30

    def test_max_timeout(self) -> None:
        """Test max timeout value."""
        config = ShellConfig()
        assert config.max_timeout == 300

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ShellConfig(
            default_timeout=10,
            max_timeout=60,
            max_output_chars=500000,
        )
        assert config.default_timeout == 10
        assert config.max_timeout == 60
        assert config.max_output_chars == 500000