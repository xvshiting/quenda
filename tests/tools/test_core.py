"""
Tests for core tools.

The 6 core tools:
- list_files: See what exists
- search_text: Find where things are
- read_file: See specific content
- write_file: Create new files
- apply_patch: Modify existing files
- run_shell: Execute and verify
"""

import tempfile
from pathlib import Path

import pytest

from kora.tools.filesystem import (
    ApplyPatchTool,
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
    WriteFileTool,
)
from kora.tools.execution import (
    RunShellTool,
    ShellConfig,
)
from kora.tools import get_core_tools


class TestListFilesTool:
    """Tests for ListFilesTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_list_flat(self, temp_dir: Path) -> None:
        """Test flat directory listing."""
        (temp_dir / "file1.txt").write_text("content")
        (temp_dir / "file2.py").write_text("code")
        (temp_dir / "subdir").mkdir()

        tool = ListFilesTool(temp_dir)
        result = tool.execute()

        assert not result.is_error
        assert "file1.txt" in result.content
        assert "file2.py" in result.content
        assert "subdir" in result.content

    def test_list_with_pattern(self, temp_dir: Path) -> None:
        """Test listing with glob pattern."""
        (temp_dir / "file1.txt").write_text("content")
        (temp_dir / "file2.py").write_text("code")

        tool = ListFilesTool(temp_dir)
        result = tool.execute(pattern="*.py")

        assert not result.is_error
        assert "file2.py" in result.content
        assert "file1.txt" not in result.content

    def test_list_tree(self, temp_dir: Path) -> None:
        """Test tree-style listing."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "nested.txt").write_text("content")

        tool = ListFilesTool(temp_dir)
        result = tool.execute(depth=2)

        assert not result.is_error
        assert "subdir" in result.content
        assert "nested.txt" in result.content


class TestSearchTextTool:
    """Tests for SearchTextTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_search_pattern(self, temp_dir: Path) -> None:
        """Test searching for pattern."""
        (temp_dir / "test.txt").write_text("hello world\nfoo bar\nhello again")

        tool = SearchTextTool(temp_dir)
        result = tool.execute(pattern="hello")

        assert not result.is_error
        assert "hello" in result.content

    def test_search_no_matches(self, temp_dir: Path) -> None:
        """Test search with no matches."""
        (temp_dir / "test.txt").write_text("hello world")

        tool = SearchTextTool(temp_dir)
        result = tool.execute(pattern="xyz")

        assert not result.is_error
        assert "no matches" in result.content.lower()

    def test_search_with_include(self, temp_dir: Path) -> None:
        """Test search with file filter."""
        (temp_dir / "test.txt").write_text("hello")
        (temp_dir / "test.py").write_text("hello")

        tool = SearchTextTool(temp_dir)
        result = tool.execute(pattern="hello", include="*.py")

        assert not result.is_error
        assert "test.py" in result.content
        assert "test.txt" not in result.content


class TestReadFileTool:
    """Tests for ReadFileTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_read_entire_file(self, temp_dir: Path) -> None:
        """Test reading entire file."""
        (temp_dir / "test.txt").write_text("line1\nline2\nline3")

        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="test.txt")

        assert not result.is_error
        assert "line1" in result.content
        assert "line2" in result.content
        assert "line3" in result.content

    def test_read_line_range(self, temp_dir: Path) -> None:
        """Test reading specific line range."""
        lines = [f"line{i}" for i in range(1, 101)]
        (temp_dir / "test.txt").write_text("\n".join(lines))

        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="test.txt", start=1, end=10)

        assert not result.is_error
        assert "line1" in result.content
        assert "line10" in result.content
        assert "line11" not in result.content

    def test_read_last_n_lines(self, temp_dir: Path) -> None:
        """Test reading last N lines with negative start."""
        lines = [f"line{i}" for i in range(1, 101)]
        (temp_dir / "test.txt").write_text("\n".join(lines))

        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="test.txt", start=-10)

        assert not result.is_error
        assert "line91" in result.content
        assert "line100" in result.content
        assert "line90" not in result.content

    def test_read_file_not_found(self, temp_dir: Path) -> None:
        """Test reading non-existent file."""
        tool = ReadFileTool(temp_dir)
        result = tool.execute(path="nonexistent.txt")

        assert result.is_error
        assert "not found" in result.content.lower()


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_write_new_file(self, temp_dir: Path) -> None:
        """Test writing a new file."""
        tool = WriteFileTool(temp_dir)
        result = tool.execute(path="new.txt", content="Hello, World!")

        assert not result.is_error
        assert (temp_dir / "new.txt").exists()
        assert (temp_dir / "new.txt").read_text() == "Hello, World!"

    def test_write_creates_directories(self, temp_dir: Path) -> None:
        """Test writing creates parent directories."""
        tool = WriteFileTool(temp_dir)
        result = tool.execute(path="sub/dir/file.txt", content="nested")

        assert not result.is_error
        assert (temp_dir / "sub/dir/file.txt").exists()


class TestApplyPatchTool:
    """Tests for ApplyPatchTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_apply_patch(self, temp_dir: Path) -> None:
        """Test applying a patch."""
        (temp_dir / "test.txt").write_text("Hello, World!")

        tool = ApplyPatchTool(temp_dir)
        result = tool.execute(
            path="test.txt",
            old_text="World",
            new_text="Kora",
        )

        assert not result.is_error
        assert (temp_dir / "test.txt").read_text() == "Hello, Kora!"

    def test_apply_patch_dry_run(self, temp_dir: Path) -> None:
        """Test dry run mode."""
        (temp_dir / "test.txt").write_text("Hello, World!")

        tool = ApplyPatchTool(temp_dir)
        result = tool.execute(
            path="test.txt",
            old_text="World",
            new_text="Kora",
            dry_run=True,
        )

        assert not result.is_error
        assert "dry run" in result.content.lower()
        # File should not be modified
        assert (temp_dir / "test.txt").read_text() == "Hello, World!"

    def test_apply_patch_not_found(self, temp_dir: Path) -> None:
        """Test patch when old_text not found."""
        (temp_dir / "test.txt").write_text("Hello, World!")

        tool = ApplyPatchTool(temp_dir)
        result = tool.execute(
            path="test.txt",
            old_text="xyz",
            new_text="abc",
        )

        assert result.is_error
        assert "not found" in result.content.lower()


class TestRunShellTool:
    """Tests for RunShellTool."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_simple_command(self, temp_dir: Path) -> None:
        """Test executing a simple command."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="echo 'hello'")

        assert not result.is_error
        assert "hello" in result.content

    def test_command_timeout(self, temp_dir: Path) -> None:
        """Test command timeout."""
        tool = RunShellTool(temp_dir, ShellConfig(default_timeout=1))
        result = tool.execute(command="sleep 10", timeout=1)

        assert result.is_error
        assert "timed out" in result.content.lower()

    def test_blocked_command(self, temp_dir: Path) -> None:
        """Test blocked dangerous command."""
        tool = RunShellTool(temp_dir)
        result = tool.execute(command="rm -rf /")

        assert result.is_error
        assert "blocked" in result.content.lower()

    def test_working_directory(self, temp_dir: Path) -> None:
        """Test command in specific directory."""
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file.txt").write_text("content")

        tool = RunShellTool(temp_dir)
        result = tool.execute(command="ls", cwd="subdir")

        assert not result.is_error
        assert "file.txt" in result.content


class TestGetCoreTools:
    """Tests for get_core_tools helper."""

    def test_returns_nine_tools(self) -> None:
        """Test that exactly 9 tools are returned."""
        tools = get_core_tools("/tmp")

        assert len(tools) == 9
        names = [t.name for t in tools]
        assert "list_files" in names
        assert "search_text" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "apply_patch" in names
        assert "run_shell" in names
        assert "execute_python" in names
        assert "request_interaction" in names
        assert "request_skill_activation" in names
