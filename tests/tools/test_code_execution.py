"""
Tests for Python code execution tool.
"""

import pytest

from quenda.tools.execution import PythonExecutionTool, SandboxConfig


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

    def test_allowed_module_import(self) -> None:
        """Test importing allowed module."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import math; print(math.pi)")

        assert not result.is_error
        assert "3.14" in result.content

    def test_allowed_module_datetime(self) -> None:
        """Test importing datetime."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import datetime; print(datetime.date.today())")

        assert not result.is_error

    def test_blocked_module_os(self) -> None:
        """Test importing blocked module os."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import os")

        assert result.is_error
        assert "blocked" in result.content.lower() or "not in" in result.content.lower()

    def test_blocked_module_subprocess(self) -> None:
        """Test importing blocked module subprocess."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import subprocess")

        assert result.is_error

    def test_blocked_module_sys(self) -> None:
        """Test importing blocked module sys."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import sys")

        assert result.is_error

    def test_blocked_module_socket(self) -> None:
        """Test importing blocked module socket."""
        tool = PythonExecutionTool()
        result = tool.execute(code="import socket")

        assert result.is_error

    def test_blocked_builtin_open(self) -> None:
        """Test blocked builtin open."""
        tool = PythonExecutionTool()
        result = tool.execute(code="open('/tmp/test.txt', 'w')")

        assert result.is_error

    def test_syntax_error_reported(self) -> None:
        """Test syntax error is reported."""
        tool = PythonExecutionTool()
        result = tool.execute(code="print('unclosed")

        assert result.is_error
        assert "syntax" in result.content.lower()

    def test_runtime_error_reported(self) -> None:
        """Test runtime error is reported."""
        tool = PythonExecutionTool()
        result = tool.execute(code="1/0")

        assert result.is_error
        assert "zerodivision" in result.content.lower() or "division" in result.content.lower() or "error" in result.content.lower()

    def test_timeout(self) -> None:
        """Test execution timeout."""
        tool = PythonExecutionTool(config=SandboxConfig(default_timeout=1))
        result = tool.execute(code="while True: pass", timeout=1)

        assert result.is_error
        assert "timed out" in result.content.lower()

    def test_ast_bomb_blocked(self) -> None:
        """Test AST bomb is blocked."""
        tool = PythonExecutionTool()
        # Generate deeply nested AST
        code = "x = " + "+".join(["1"] * 10000)
        result = tool.execute(code=code)

        assert result.is_error
        assert "complex" in result.content.lower() or "large" in result.content.lower() or "recursion" in result.content.lower()

    def test_async_blocked(self) -> None:
        """Test async syntax is blocked."""
        tool = PythonExecutionTool()
        result = tool.execute(code="async def f(): pass")

        assert result.is_error
        assert "async" in result.content.lower() or "blocked" in result.content.lower()

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
        """Test JSON module is allowed."""
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

    def test_io_module_allowed(self) -> None:
        """Test in-memory IO helpers are allowed."""
        tool = PythonExecutionTool()
        result = tool.execute(
            code="""
import io
buffer = io.StringIO()
buffer.write("image search helper")
print(buffer.getvalue())
"""
        )

        assert not result.is_error
        assert "image search helper" in result.content


class TestSandboxConfig:
    """Tests for SandboxConfig."""

    def test_default_timeout(self) -> None:
        """Test default timeout value."""
        config = SandboxConfig()
        assert config.default_timeout == 30

    def test_max_timeout(self) -> None:
        """Test max timeout value."""
        config = SandboxConfig()
        assert config.max_timeout == 60

    def test_max_ast_nodes(self) -> None:
        """Test max AST nodes value."""
        config = SandboxConfig()
        assert config.max_ast_nodes == 5000

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SandboxConfig(
            default_timeout=10,
            max_timeout=30,
            max_ast_nodes=1000,
        )
        assert config.default_timeout == 10
        assert config.max_timeout == 30
        assert config.max_ast_nodes == 1000


class TestASTValidator:
    """Tests for AST validation."""

    def test_valid_code(self) -> None:
        """Test valid code passes validation."""
        from quenda.tools.execution.code import ASTValidator

        validator = ASTValidator(SandboxConfig())
        errors = validator.validate("print('hello')")
        assert len(errors) == 0

    def test_syntax_error_detected(self) -> None:
        """Test syntax error is detected."""
        from quenda.tools.execution.code import ASTValidator

        validator = ASTValidator(SandboxConfig())
        errors = validator.validate("print('unclosed")
        assert len(errors) > 0
        assert "syntax" in errors[0].lower()

    def test_async_blocked(self) -> None:
        """Test async is blocked."""
        from quenda.tools.execution.code import ASTValidator

        validator = ASTValidator(SandboxConfig())
        errors = validator.validate("async def f(): pass")
        assert len(errors) > 0
        assert "async" in errors[0].lower() or "blocked" in errors[0].lower()
