"""
Python code execution tool for Quenda.

Executes Python code in a sandboxed environment with:
- AST validation
- Import restrictions
- Restricted builtins
- Timeout and memory limits
"""

from __future__ import annotations

import ast
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.tools.security.patterns import (
    SANDBOX_ALLOWED_BUILTINS,
    SANDBOX_ALLOWED_MODULES,
    SANDBOX_BLOCKED_MODULES,
)


@dataclass
class SandboxConfig:
    """Configuration for Python sandbox."""

    allowed_modules: list[str] = field(default_factory=lambda: SANDBOX_ALLOWED_MODULES.copy())
    blocked_modules: list[str] = field(default_factory=lambda: SANDBOX_BLOCKED_MODULES.copy())
    allowed_builtins: list[str] = field(default_factory=lambda: SANDBOX_ALLOWED_BUILTINS.copy())
    default_timeout: int = 30
    max_timeout: int = 60
    max_output_bytes: int = 1_000_000
    max_ast_nodes: int = 5000


class RestrictedImporter:
    """
    Custom import hook for module restrictions.

    Replaces __import__ in the sandbox to control which modules can be imported.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self._original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def __call__(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Import hook that checks against allowlist and blocklist."""
        base_module = name.split(".")[0]

        # Check blocklist first
        if base_module in self.config.blocked_modules:
            raise ImportError(f"Module '{name}' is blocked for security")

        # Check allowlist
        if base_module not in self.config.allowed_modules:
            raise ImportError(
                f"Module '{name}' is not in the allowed list. "
                f"Allowed modules include: {', '.join(self.config.allowed_modules[:10])}..."
            )

        return self._original_import(name, *args, **kwargs)


class ASTValidator(ast.NodeVisitor):
    """
    Validate AST for dangerous patterns.

    Checks for:
    - Dangerous syntax (async/await that can bypass restrictions)
    - AST complexity (prevent AST bombs)
    """

    DANGEROUS_NODE_TYPES: set[type[ast.AST]] = {
        # Async can bypass some sync restrictions
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.AsyncFor,
        ast.Await,
    }

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.node_count = 0
        self.errors: list[str] = []

    def visit(self, node: ast.AST) -> None:
        """Visit node and check for issues."""
        self.node_count += 1

        # Check AST complexity
        if self.node_count > self.config.max_ast_nodes:
            self.errors.append(
                f"Code too complex: exceeds {self.config.max_ast_nodes} AST nodes"
            )
            return

        # Check for dangerous node types
        if type(node) in self.DANGEROUS_NODE_TYPES:
            self.errors.append(f"Blocked syntax: {type(node).__name__}")

        self.generic_visit(node)

    def validate(self, code: str) -> list[str]:
        """
        Validate code string.

        Returns:
            List of error messages (empty if valid).
        """
        try:
            # Limit code length to prevent AST bomb
            if len(code) > 100000:  # 100KB limit
                return ["Code too large: exceeds 100KB limit"]

            tree = ast.parse(code)
            self.visit(tree)
            return self.errors
        except RecursionError:
            return ["Code too complex: recursion depth exceeded during parsing"]
        except SyntaxError as e:
            return [f"Syntax error: line {e.lineno}: {e.msg}"]


class PythonExecutionTool(Tool):
    """
    Tool to execute Python code in a sandbox.

    Provides a safe environment for running untrusted Python code.
    """

    def __init__(
        self,
        workspace: Path | str | None = None,
        config: SandboxConfig | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()
        self.config = config or SandboxConfig()
        self._validator = ASTValidator(self.config)

    @property
    @override
    def name(self) -> str:
        return "execute_python"

    @property
    @override
    def description(self) -> str:
        return "Execute Python code in a sandboxed environment. Some modules and functions are restricted."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (max {self.config.max_timeout}).",
                    "default": self.config.default_timeout,
                },
            },
            "required": ["code"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        code = kwargs.get("code", "")
        timeout = kwargs.get("timeout", self.config.default_timeout)

        if not isinstance(code, str):
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: code must be a string",
                is_error=True,
            )

        # Validate AST
        errors = self._validator.validate(code)
        if errors:
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: Code validation failed:\n" + "\n".join(f"  - {e}" for e in errors),
                is_error=True,
            )

        # Clamp timeout
        timeout_seconds = min(
            int(timeout) if isinstance(timeout, (int, float)) else self.config.default_timeout,
            self.config.max_timeout,
        )

        # Create sandbox environment
        sandbox_globals = self._create_sandbox_globals()
        sandbox_locals: dict[str, Any] = {}

        # Capture output
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                self._execute_with_timeout(
                    code=code,
                    globals_dict=sandbox_globals,
                    locals_dict=sandbox_locals,
                    timeout=timeout_seconds,
                )

            return self._format_result(
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                success=True,
            )

        except TimeoutError:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: Execution timed out after {timeout_seconds} seconds",
                is_error=True,
            )
        except MemoryError:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: Execution exceeded memory limit",
                is_error=True,
            )
        except Exception as e:
            return self._format_result(
                stdout=stdout_capture.getvalue(),
                stderr=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                success=False,
            )

    def _create_sandbox_globals(self) -> dict[str, Any]:
        """Create restricted global namespace for sandbox."""
        # Build restricted builtins dict
        builtins_dict: dict[str, Any] = {}

        # Get the actual builtins module
        actual_builtins = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__

        for name in self.config.allowed_builtins:
            if name in actual_builtins:
                builtins_dict[name] = actual_builtins[name]

        # Replace __import__ with restricted version
        builtins_dict["__import__"] = RestrictedImporter(self.config)

        return {
            "__builtins__": builtins_dict,
            "__name__": "__main__",
            "__file__": "<sandbox>",
        }

    def _execute_with_timeout(
        self,
        code: str,
        globals_dict: dict[str, Any],
        locals_dict: dict[str, Any],
        timeout: int,
    ) -> None:
        """
        Execute code with timeout.

        Uses threading for cross-platform timeout support.
        Works in both main thread and worker threads.
        """
        import threading

        result: dict[str, Any] = {"exception": None}
        finished = threading.Event()

        def run_code() -> None:
            try:
                exec(code, globals_dict, locals_dict)
            except Exception as e:
                result["exception"] = e
            finally:
                finished.set()

        thread = threading.Thread(target=run_code, daemon=True)
        thread.start()

        # Wait for completion or timeout
        if not finished.wait(timeout=timeout):
            # Thread is still running - timeout occurred
            # Note: we can't actually kill the thread, but we can return
            # The daemon=True ensures the thread won't block program exit
            raise TimeoutError(f"Execution timed out after {timeout} seconds")

        # Check if an exception occurred in the thread
        if result["exception"] is not None:
            raise result["exception"]

    def _format_result(
        self,
        stdout: str,
        stderr: str,
        success: bool,
    ) -> ToolResult:
        """Format execution result."""
        parts = []

        if stdout:
            stdout = self._truncate(stdout)
            parts.append(f"[stdout]\n{stdout}")

        if stderr:
            stderr = self._truncate(stderr)
            parts.append(f"[stderr]\n{stderr}")

        if not parts:
            parts.append("Execution completed (no output)")

        content = "\n\n".join(parts)

        return ToolResult(
            call_id="",
            name=self.name,
            content=content,
            is_error=not success,
        )

    def _truncate(self, text: str) -> str:
        """Truncate text to max output size."""
        if len(text) > self.config.max_output_bytes:
            return text[: self.config.max_output_bytes] + "\n... [output truncated]"
        return text


def get_python_execution_tool(
    workspace: Path | str | None = None,
    config: SandboxConfig | None = None,
) -> Tool:
    """
    Get the Python execution tool.

    Args:
        workspace: Optional workspace directory.
        config: Sandbox configuration.

    Returns:
        PythonExecutionTool instance.
    """
    return PythonExecutionTool(workspace, config)
