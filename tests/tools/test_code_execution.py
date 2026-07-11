"""
Tests for Python code execution tool.

ADR-029 Compliance:
- Python executes in subprocess (not in-process)
- Real Python behavior (sys, os, subprocess work normally)
- No module whitelist or AST validation
- Skill Python path available via PYTHONPATH
"""

import sys
import tempfile
from pathlib import Path

import pytest

from quenda.tools.execution import (
    PythonExecutionTool,
    SandboxConfig,
    build_python_env,
)
from quenda.tools.execution.command import ExecutionLimits


class TestPythonExecutionTool:
    """Tests for PythonExecutionTool."""

    def test_simple_code_success(self) -> None:
        """Test executing simple code."""
        tool = PythonExecutionTool()
        result = tool.execute(code="print('hello world')")

        assert not result.is_error
        assert "hello world" in result.content

    def test_math_operations(self) -> None:
        """Test math operations."""
        tool = PythonExecutionTool()
        result = tool.execute(code="result = 2 + 2; print(result)")

        assert not result.is_error
        assert "4" in result.content

    def test_sys_module_works(self) -> None:
        """Test that sys module works (was blocked in old sandbox)."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import sys; print(sys.version_info.major)")

        assert not result.is_error
        assert str(sys.version_info.major) in result.content

    def test_os_module_works(self) -> None:
        """Test that os module works (was blocked in old sandbox)."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import os; print(os.getcwd())")

        assert not result.is_error

    def test_subprocess_module_works(self) -> None:
        """Test that subprocess module works (was blocked in old sandbox)."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="import subprocess; result = subprocess.run(['echo', 'hello'], capture_output=True, text=True); print(result.stdout)"
        )

        assert not result.is_error
        assert "hello" in result.content

    def test_file_operations_work(self) -> None:
        """Test that file operations work (open was blocked in old sandbox)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = PythonExecutionTool(workspace=tmpdir)
            result = tool.execute(
                code=f"""
import os
with open('test.txt', 'w') as f:
    f.write('hello')
with open('test.txt', 'r') as f:
    print(f.read())
"""
            )

            assert not result.is_error
            assert "hello" in result.content

    def test_async_code_works(self) -> None:
        """Test that async code works (was blocked in old sandbox)."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="""
import asyncio

async def main():
    print('async works')

asyncio.run(main())
"""
        )

        assert not result.is_error
        assert "async works" in result.content

    def test_syntax_error_reported(self) -> None:
        """Test syntax error is reported."""
        tool = PythonExecutionTool()
        result = tool.execute(code="print('unclosed")

        assert result.is_error
        assert "syntax" in result.content.lower() or "error" in result.content.lower()

    def test_runtime_error_reported(self) -> None:
        """Test runtime error is reported."""
        tool = PythonExecutionTool()
        result = tool.execute(code="1/0")

        assert result.is_error
        assert "zero" in result.content.lower() or "division" in result.content.lower() or "error" in result.content.lower()

    def test_timeout(self) -> None:
        """Test execution timeout."""
        tool = PythonExecutionTool(config=SandboxConfig(default_timeout=1))
        result = tool.execute(code="import time; time.sleep(60); print('done')", timeout=1)

        assert result.is_error
        assert "timed out" in result.content.lower()

    def test_no_output(self) -> None:
        """Test code with no output."""
        tool = PythonExecutionTool()
        result = tool.execute(code="x = 1 + 1")

        assert not result.is_error
        assert "no output" in result.content.lower()

    def test_multiline_code(self) -> None:
        """Test multiline code."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="""
x = [1, 2, 3, 4, 5]
total = sum(x)
print(f"Sum: {total}")
"""
        )

        assert not result.is_error
        assert "Sum: 15" in result.content

    def test_json_operations(self) -> None:
        """Test JSON module works."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="""
import json
data = {"key": "value"}
print(json.dumps(data))
"""
        )

        assert not result.is_error
        assert '{"key": "value"}' in result.content

    def test_io_module_works(self) -> None:
        """Test in-memory IO helpers work."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="""
import io
buffer = io.StringIO()
buffer.write("hello from StringIO")
print(buffer.getvalue())
"""
        )

        assert not result.is_error
        assert "hello from StringIO" in result.content

    def test_requests_if_installed(self) -> None:
        """Test that requests works if installed (was not in whitelist)."""
        pytest.importorskip("requests")
        tool = PythonExecutionTool()
        result = tool.execute(code="import requests; print('requests imported')")

        assert not result.is_error
        assert "requests imported" in result.content

    def test_stdin_input_via_dash(self) -> None:
        """Test that code is passed via stdin."""
        tool = PythonExecutionTool()
        result = tool.execute(code="print('stdin test')")

        assert not result.is_error
        assert "stdin test" in result.content

    def test_unicode_handling(self) -> None:
        """Test unicode handling."""
        tool = PythonExecutionTool()
        result = tool.execute(code="print('你好世界 🌍')")

        assert not result.is_error
        assert "你好世界" in result.content
        assert "🌍" in result.content

    def test_empty_code_error(self) -> None:
        """Test error for empty code."""
        tool = PythonExecutionTool()
        result = tool.execute(code="")

        assert result.is_error
        assert "empty" in result.content.lower()

    def test_non_string_code_error(self) -> None:
        """Test error for non-string code."""
        tool = PythonExecutionTool()
        result = tool.execute(code=123)  # type: ignore

        assert result.is_error
        assert "string" in result.content.lower()


class TestSandboxConfig:
    """Tests for SandboxConfig (backward compatibility)."""

    def test_default_timeout(self) -> None:
        """Test default timeout value."""
        config = SandboxConfig()
        assert config.default_timeout == 30

    def test_max_timeout(self) -> None:
        """Test max timeout value."""
        config = SandboxConfig()
        assert config.max_timeout == 60

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SandboxConfig(
            default_timeout=10,
            max_timeout=30,
        )
        assert config.default_timeout == 10
        assert config.max_timeout == 30

    def test_to_limits(self) -> None:
        """Test conversion to ExecutionLimits."""
        config = SandboxConfig(
            default_timeout=15,
            max_timeout=45,
            max_output_bytes=50_000,
        )
        limits = config.to_limits()

        assert limits.default_timeout == 15
        assert limits.max_timeout == 45
        assert limits.max_output_chars == 50_000

    def test_legacy_fields_ignored(self) -> None:
        """Test that legacy whitelist fields are accepted but ignored."""
        config = SandboxConfig(
            allowed_modules=["os", "sys"],
            blocked_modules=["subprocess"],
            allowed_builtins=["print", "open"],
            max_ast_nodes=10000,
        )
        # These should be accepted (no error) but ignored
        assert config.allowed_modules == ["os", "sys"]
        assert config.blocked_modules == ["subprocess"]
        # The tool should still allow all modules
        tool = PythonExecutionTool(config=config)
        result = tool.execute(code="import subprocess; print('ok')")
        assert not result.is_error


class TestBuildPythonEnv:
    """Tests for build_python_env helper."""

    def test_no_skills(self) -> None:
        """Test environment without skills."""
        env = build_python_env()
        assert "PYTHONPATH" not in env or env.get("PYTHONPATH") == ""

    def test_with_skills(self, tmp_path: Path) -> None:
        """Test environment with skills."""
        # Create mock skill
        skill_dir = tmp_path / "test_skill"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create mock SkillPackage-like object
        class MockSkill:
            def __init__(self, path: Path):
                self.path = path

        skill = MockSkill(skill_dir)
        env = build_python_env(active_skills=[skill])  # type: ignore

        assert "PYTHONPATH" in env
        assert str(scripts_dir) in env["PYTHONPATH"]

    def test_merges_existing_pythonpath(self, tmp_path: Path) -> None:
        """Test that existing PYTHONPATH is preserved."""
        skill_dir = tmp_path / "test_skill"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)

        class MockSkill:
            def __init__(self, path: Path):
                self.path = path

        skill = MockSkill(skill_dir)
        base_env = {"PYTHONPATH": "/existing/path"}
        env = build_python_env(active_skills=[skill], base_env=base_env)  # type: ignore

        assert "/existing/path" in env["PYTHONPATH"]
        assert str(scripts_dir) in env["PYTHONPATH"]

    def test_skill_without_scripts_dir(self, tmp_path: Path) -> None:
        """Test skill without scripts directory."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()

        class MockSkill:
            def __init__(self, path: Path):
                self.path = path

        skill = MockSkill(skill_dir)
        env = build_python_env(active_skills=[skill])  # type: ignore

        # Should not add anything to PYTHONPATH
        assert "PYTHONPATH" not in env or str(skill_dir) not in env.get("PYTHONPATH", "")


class TestSkillPythonImport:
    """Tests for Skill Python import functionality."""

    def test_import_from_skill(self, tmp_path: Path) -> None:
        """Test importing Python code from Skill."""
        # Create mock skill with Python package
        skill_dir = tmp_path / "test_skill"
        scripts_dir = skill_dir / "scripts"
        pkg_dir = scripts_dir / "test_pkg"
        pkg_dir.mkdir(parents=True)

        # Create __init__.py
        (pkg_dir / "__init__.py").write_text("VERSION = '1.0'")

        # Create module
        (pkg_dir / "utils.py").write_text(
            """
def greet(name):
    return f"Hello, {name}!"
"""
        )

        # Create mock SkillPackage
        class MockSkill:
            def __init__(self, path: Path):
                self.path = path

        skill = MockSkill(skill_dir)

        # Create tool with skill
        tool = PythonExecutionTool(
            workspace=tmp_path,
            active_skills=[skill],  # type: ignore
        )

        result = tool.execute(
            code="""
from test_pkg.utils import greet
print(greet("World"))
"""
        )

        assert not result.is_error
        assert "Hello, World!" in result.content

    def test_multiple_skills(self, tmp_path: Path) -> None:
        """Test multiple skills with different packages."""
        # Create two skills
        for skill_name, pkg_name, func_name in [
            ("skill_a", "pkg_a", "func_a"),
            ("skill_b", "pkg_b", "func_b"),
        ]:
            skill_dir = tmp_path / skill_name
            scripts_dir = skill_dir / "scripts"
            pkg_dir = scripts_dir / pkg_name
            pkg_dir.mkdir(parents=True)

            (pkg_dir / "__init__.py").write_text("")
            (pkg_dir / "module.py").write_text(
                f"""
def {func_name}():
    return "{func_name} called"
"""
            )

        class MockSkill:
            def __init__(self, path: Path):
                self.path = path

        skills = [MockSkill(tmp_path / "skill_a"), MockSkill(tmp_path / "skill_b")]

        tool = PythonExecutionTool(
            workspace=tmp_path,
            active_skills=skills,  # type: ignore
        )

        result = tool.execute(
            code="""
from pkg_a.module import func_a
from pkg_b.module import func_b
print(func_a())
print(func_b())
"""
        )

        assert not result.is_error
        assert "func_a called" in result.content
        assert "func_b called" in result.content
