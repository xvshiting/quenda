"""
Tests for Kora tools.
"""

import tempfile
from pathlib import Path

import pytest

from kora.kernel.types import ToolResult
from kora.tools import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    get_filesystem_tools,
    get_core_tools,
    tool,
)


class TestToolDecorator:
    """Tests for @tool decorator."""

    def test_simple_tool(self) -> None:
        """Test creating a simple tool."""

        @tool
        def echo(message: str) -> str:
            """Echo back the message."""
            return f"Echo: {message}"

        assert echo.name == "echo"
        assert echo.description == "Echo back the message."
        assert "message" in echo.parameters["properties"]

    def test_tool_with_default(self) -> None:
        """Test tool with default parameter."""

        @tool
        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}!"

        assert "greeting" in greet.parameters["properties"]
        assert "greeting" not in greet.parameters["required"]

    def test_tool_with_custom_name(self) -> None:
        """Test tool with custom name."""

        @tool(name="custom_echo")
        def echo(msg: str) -> str:
            """Echo."""
            return msg

        assert echo.name == "custom_echo"

    def test_tool_execute(self) -> None:
        """Test executing a tool."""

        @tool
        def add(a: int, b: int) -> str:
            """Add two numbers."""
            return str(a + b)

        result = add.execute(a=1, b=2)
        assert result.content == "3"
        assert not result.is_error

    def test_tool_error_handling(self) -> None:
        """Test tool error handling."""

        @tool
        def fail() -> str:
            """Always fails."""
            raise ValueError("Intentional error")

        result = fail.execute()
        assert result.is_error
        assert "Error" in result.content


class TestFilesystemTools:
    """Tests for file system tools."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_read_file(self, temp_dir: Path) -> None:
        """Test reading a file."""
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="test.txt")

        assert not result.is_error
        assert "Hello, World!" in result.content

    def test_read_file_not_found(self, temp_dir: Path) -> None:
        """Test reading a non-existent file."""
        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="nonexistent.txt")

        assert result.is_error
        assert "not found" in result.content.lower()

    def test_read_file_outside_workspace(self, temp_dir: Path) -> None:
        """Test reading a file outside workspace."""
        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="../outside.txt")

        assert result.is_error
        assert "access denied" in result.content.lower()

    def test_write_file(self, temp_dir: Path) -> None:
        """Test writing a file."""
        tool = WriteFileTool(temp_dir)
        result = tool.execute(path="new.txt", content="Test content")

        assert not result.is_error

        # Verify file was written
        written = (temp_dir / "new.txt").read_text()
        assert written == "Test content"

    def test_write_file_creates_directories(self, temp_dir: Path) -> None:
        """Test writing creates parent directories."""
        tool = WriteFileTool(temp_dir)
        result = tool.execute(path="sub/dir/file.txt", content="nested")

        assert not result.is_error
        assert (temp_dir / "sub/dir/file.txt").exists()

    def test_list_files(self, temp_dir: Path) -> None:
        """Test listing files."""
        # Create test structure
        (temp_dir / "file1.txt").write_text("1")
        (temp_dir / "file2.txt").write_text("2")
        (temp_dir / "subdir").mkdir()

        tool = ListFilesTool(temp_dir)
        result = tool.execute(path=".")

        assert not result.is_error
        assert "file1.txt" in result.content
        assert "file2.txt" in result.content
        assert "subdir" in result.content

    def test_list_empty_directory(self, temp_dir: Path) -> None:
        """Test listing empty directory."""
        tool = ListFilesTool(temp_dir)
        result = tool.execute(path=".")

        assert not result.is_error
        assert "empty" in result.content.lower()

    def test_get_core_tools(self, temp_dir: Path) -> None:
        """Test getting core tools."""
        tools = get_core_tools(temp_dir)

        assert len(tools) == 9
        names = [t.name for t in tools]
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names
        assert "search_text" in names
        assert "apply_patch" in names
        assert "run_shell" in names
        assert "execute_python" in names
        assert "request_interaction" in names
        assert "request_skill_activation" in names
