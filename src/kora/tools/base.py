"""
Base class for Kora tools with common functionality.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from kora.kernel.types import ToolResult


class BaseTool(ABC):
    """
    Base class for all tools with common functionality.

    Provides:
    - Workspace path validation
    - Output truncation
    """

    def __init__(self, workspace: Path | str | None = None) -> None:
        """
        Initialize with optional workspace.

        Args:
            workspace: The root directory for file operations.
                      If None, uses current working directory.
        """
        self.workspace = Path(workspace).resolve() if workspace else Path.cwd()

    def _validate_workspace_path(self, path: str) -> Path:
        """
        Validate that a path is within the workspace boundary.

        Args:
            path: Relative or absolute path to validate.

        Returns:
            Resolved absolute path within workspace.

        Raises:
            ValueError: If path escapes workspace boundary.
        """
        resolved = (self.workspace / path).resolve()

        # Security check: ensure path is within workspace
        if not str(resolved).startswith(str(self.workspace)):
            raise ValueError(f"Path escapes workspace: {path}")

        return resolved

    def _truncate_output(
        self, output: str, max_bytes: int = 1_000_000
    ) -> tuple[str, bool]:
        """
        Truncate output to prevent memory issues.

        Args:
            output: The output string to truncate.
            max_bytes: Maximum size in bytes.

        Returns:
            Tuple of (truncated output, was_truncated).
        """
        encoded = output.encode("utf-8", errors="replace")
        if len(encoded) > max_bytes:
            truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
            return truncated + "\n... [output truncated]", True
        return output, False

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what the tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, object]:
        """JSON Schema for the tool's parameters."""
        ...

    @abstractmethod
    def execute(self, **kwargs: object) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...
