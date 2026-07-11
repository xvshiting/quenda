"""
Tests for CommandRunner - the unified local process execution primitive.

ADR-029 Compliance:
- CommandRunner provides process isolation and lifecycle control
- It does NOT provide filesystem or network sandboxing
"""

import sys
import tempfile
from pathlib import Path

import pytest

from quenda.tools.execution.command import (
    CommandRequest,
    CommandResult,
    CommandRunner,
    ExecutionLimits,
)


class TestExecutionLimits:
    """Tests for ExecutionLimits."""

    def test_default_values(self) -> None:
        """Test default limit values."""
        limits = ExecutionLimits()
        assert limits.default_timeout == 30
        assert limits.max_timeout == 300
        assert limits.max_output_chars == 100_000
        assert limits.max_stdin_bytes == 1_000_000

    def test_custom_values(self) -> None:
        """Test custom limit values."""
        limits = ExecutionLimits(
            default_timeout=60,
            max_timeout=600,
            max_output_chars=50_000,
            max_stdin_bytes=500_000,
        )
        assert limits.default_timeout == 60
        assert limits.max_timeout == 600
        assert limits.max_output_chars == 50_000
        assert limits.max_stdin_bytes == 500_000


class TestCommandRequest:
    """Tests for CommandRequest."""

    def test_minimal_request(self) -> None:
        """Test minimal request with required fields."""
        request = CommandRequest(
            argv=["echo", "hello"],
            cwd=Path("."),
        )
        assert request.argv == ["echo", "hello"]
        assert request.cwd == Path(".")
        assert request.stdin is None
        assert request.env is None
        assert request.timeout == 30

    def test_full_request(self) -> None:
        """Test request with all fields."""
        request = CommandRequest(
            argv=["python", "-c", "print(1)"],
            cwd=Path("/tmp"),
            stdin="input data",
            env={"MY_VAR": "value"},
            timeout=60,
        )
        assert request.argv == ["python", "-c", "print(1)"]
        assert request.cwd == Path("/tmp")
        assert request.stdin == "input data"
        assert request.env == {"MY_VAR": "value"}
        assert request.timeout == 60


class TestCommandResult:
    """Tests for CommandResult."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = CommandResult(
            exit_code=0,
            stdout="hello\n",
            stderr="",
        )
        assert result.exit_code == 0
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert not result.timed_out

    def test_error_result(self) -> None:
        """Test error result."""
        result = CommandResult(
            exit_code=1,
            stdout="",
            stderr="error message",
        )
        assert result.exit_code == 1
        assert result.stderr == "error message"

    def test_timeout_result(self) -> None:
        """Test timeout result."""
        result = CommandResult(
            exit_code=-1,
            stdout="",
            stderr="",
            timed_out=True,
        )
        assert result.timed_out


class TestCommandRunner:
    """Tests for CommandRunner."""

    @pytest.fixture
    def runner(self) -> CommandRunner:
        """Create a CommandRunner instance."""
        return CommandRunner()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_simple_command_success(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test executing a simple command."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print('hello world')"],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 0
        assert "hello world" in result.stdout
        assert not result.timed_out

    def test_stdout_capture(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test stdout is captured."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print('line1'); print('line2')"],
                cwd=temp_dir,
            )
        )

        assert "line1" in result.stdout
        assert "line2" in result.stdout

    def test_stderr_capture(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test stderr is captured."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import sys; sys.stderr.write('error\\n')"],
                cwd=temp_dir,
            )
        )

        assert "error" in result.stderr

    def test_nonzero_exit_code(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test non-zero exit code is reported."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import sys; sys.exit(42)"],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 42

    def test_stdin_input(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test stdin input is passed to the command."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print(input())"],
                cwd=temp_dir,
                stdin="test input",
            )
        )

        assert "test input" in result.stdout

    def test_stdin_multiline(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test multiline stdin input."""
        code = """
import sys
for line in sys.stdin:
    print(f"got: {line.strip()}")
"""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", code],
                cwd=temp_dir,
                stdin="line1\nline2\nline3",
            )
        )

        assert "got: line1" in result.stdout
        assert "got: line2" in result.stdout
        assert "got: line3" in result.stdout

    def test_timeout_kills_process(self, temp_dir: Path) -> None:
        """Test timeout kills the process."""
        # Use short timeout to avoid slow tests
        runner = CommandRunner(ExecutionLimits(default_timeout=1, max_timeout=10))

        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import time; time.sleep(60); print('done')"],
                cwd=temp_dir,
                timeout=1,
            )
        )

        assert result.timed_out
        assert "done" not in result.stdout

    def test_timeout_kills_child_processes(self, temp_dir: Path) -> None:
        """Test timeout kills child processes too."""
        # Script that spawns a child process
        code = """
import subprocess
import sys
import time

# Start a child process that writes to a file
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(60); open('child_done.txt', 'w').write('done')"],
)
time.sleep(60)  # Parent sleeps too
"""
        runner = CommandRunner(ExecutionLimits(default_timeout=2, max_timeout=10))

        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", code],
                cwd=temp_dir,
                timeout=2,
            )
        )

        assert result.timed_out
        # Child should have been killed too, so file shouldn't exist
        assert not (temp_dir / "child_done.txt").exists()

    def test_executable_not_found(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test error when executable not found."""
        result = runner.run(
            CommandRequest(
                argv=["nonexistent_command_xyz123", "arg"],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 127
        assert "not found" in result.stderr.lower()

    def test_cwd_not_exists(self, runner: CommandRunner) -> None:
        """Test error when cwd does not exist."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print(1)"],
                cwd=Path("/nonexistent/directory/xyz123"),
            )
        )

        assert result.exit_code != 0
        assert "does not exist" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_custom_cwd(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test command runs in specified cwd."""
        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import os; print(os.getcwd())"],
                cwd=subdir,
            )
        )

        assert str(subdir) in result.stdout

    def test_env_override(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test environment variable override."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import os; print(os.environ.get('MY_TEST_VAR', 'not set'))"],
                cwd=temp_dir,
                env={"MY_TEST_VAR": "test_value"},
            )
        )

        assert "test_value" in result.stdout

    def test_env_inherits_existing(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test environment inherits existing variables."""
        # PATH should still be available
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import os; print('PATH' in os.environ)"],
                cwd=temp_dir,
                env={"MY_TEST_VAR": "value"},  # Add custom var, don't replace PATH
            )
        )

        assert "True" in result.stdout

    def test_output_truncation(self, temp_dir: Path) -> None:
        """Test output truncation when exceeding limit."""
        limits = ExecutionLimits(max_output_chars=100)
        runner = CommandRunner(limits)

        # Generate large output
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print('x' * 1000)"],
                cwd=temp_dir,
            )
        )

        assert len(result.stdout) <= 150  # Allow some slack for truncation message
        assert "truncated" in result.stdout.lower()

    def test_stdin_size_limit(self, temp_dir: Path) -> None:
        """Test stdin size limit."""
        limits = ExecutionLimits(max_stdin_bytes=100)
        runner = CommandRunner(limits)

        large_input = "x" * 1000
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print(len(input()))"],
                cwd=temp_dir,
                stdin=large_input,
            )
        )

        assert result.exit_code != 0
        assert "exceeds" in result.stderr.lower() or "limit" in result.stderr.lower()

    def test_timeout_clamped_to_max(self, temp_dir: Path) -> None:
        """Test timeout is clamped to max_timeout."""
        limits = ExecutionLimits(max_timeout=5)
        runner = CommandRunner(limits)

        # Request 100 second timeout, should be clamped to 5
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print('quick')"],
                cwd=temp_dir,
                timeout=100,  # Should be clamped
            )
        )

        # Should succeed quickly
        assert result.exit_code == 0

    def test_empty_argv(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test error when argv is empty."""
        result = runner.run(
            CommandRequest(
                argv=[],
                cwd=temp_dir,
            )
        )

        assert result.exit_code != 0
        assert "empty" in result.stderr.lower()

    def test_argv_with_special_characters(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test argv with special characters (no shell injection)."""
        # This tests that special characters are NOT interpreted by shell
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import sys; print(sys.argv[1])", "hello $HOME world"],
                cwd=temp_dir,
            )
        )

        # $HOME should NOT be expanded (shell=False)
        assert "hello $HOME world" in result.stdout

    def test_unicode_handling(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test unicode handling in input and output."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print('你好世界 🌍')"],
                cwd=temp_dir,
            )
        )

        assert "你好世界" in result.stdout
        assert "🌍" in result.stdout


class TestCommandRunnerIntegration:
    """Integration tests for CommandRunner with realistic scenarios."""

    @pytest.fixture
    def runner(self) -> CommandRunner:
        """Create a CommandRunner instance."""
        return CommandRunner()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_python_subprocess_real_behavior(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test that Python behaves like real Python (sys, os available)."""
        # This would fail in the old sandbox
        code = """
import sys
import os
print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
print(f"CWD: {os.getcwd()}")
"""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", code],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 0
        assert "Python:" in result.stdout
        assert "CWD:" in result.stdout

    def test_python_can_use_requests_if_installed(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test that Python can import requests if available."""
        # Skip if requests not installed
        pytest.importorskip("requests")

        code = """
import requests
print("requests imported successfully")
"""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", code],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 0
        assert "requests imported successfully" in result.stdout

    def test_bash_command_via_argv(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test running bash command via explicit argv."""
        result = runner.run(
            CommandRequest(
                argv=["bash", "-lc", "echo hello from bash"],
                cwd=temp_dir,
            )
        )

        # May fail if bash not available, skip in that case
        if result.exit_code == 127:
            pytest.skip("bash not available")

        assert "hello from bash" in result.stdout

    def test_pip_list_via_argv(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test running pip list via argv."""
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-m", "pip", "list", "--format=freeze"],
                cwd=temp_dir,
                timeout=30,
            )
        )

        # pip should be available
        assert result.exit_code == 0


class TestCommandRunnerEdgeCases:
    """Edge case tests for CommandRunner."""

    @pytest.fixture
    def runner(self) -> CommandRunner:
        """Create a CommandRunner instance."""
        return CommandRunner()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_very_long_argv(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test handling of very long argv."""
        # Create a long string argument
        long_arg = "x" * 10000
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "import sys; print(len(sys.argv[1]))", long_arg],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 0
        assert "10000" in result.stdout

    def test_binary_output(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test handling of binary-like output."""
        # Python will decode as text, so we just test that it doesn't crash
        result = runner.run(
            CommandRequest(
                argv=[sys.executable, "-c", "print(bytes(range(256))[:100])"],
                cwd=temp_dir,
            )
        )

        assert result.exit_code == 0

    def test_concurrent_execution(self, runner: CommandRunner, temp_dir: Path) -> None:
        """Test that multiple commands can run sequentially."""
        for i in range(3):
            result = runner.run(
                CommandRequest(
                    argv=[sys.executable, "-c", f"print({i})"],
                    cwd=temp_dir,
                )
            )
            assert result.exit_code == 0
            assert str(i) in result.stdout
