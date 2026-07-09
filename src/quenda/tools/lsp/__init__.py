"""
LSP (Language Server Protocol) tool for Quenda.

Provides code intelligence features through LSP servers:
- Go to definition
- Find references
- Hover information (documentation, type info)
- Document symbols
- Workspace symbols
- Go to implementation
- Call hierarchy

Inspired by Claude Code's LSPTool.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class LSPOperation(str, Enum):
    """Supported LSP operations."""
    GO_TO_DEFINITION = "goToDefinition"
    FIND_REFERENCES = "findReferences"
    HOVER = "hover"
    DOCUMENT_SYMBOL = "documentSymbol"
    WORKSPACE_SYMBOL = "workspaceSymbol"
    GO_TO_IMPLEMENTATION = "goToImplementation"
    PREPARE_CALL_HIERARCHY = "prepareCallHierarchy"
    INCOMING_CALLS = "incomingCalls"
    OUTGOING_CALLS = "outgoingCalls"


@dataclass
class LSPResult:
    """Result from an LSP operation."""
    operation: LSPOperation
    file_path: str
    line: int
    character: int
    content: str
    locations: list[dict] | None = None  # For definition/reference results
    symbol_info: dict | None = None  # For hover/symbol results
    call_hierarchy: list[dict] | None = None  # For call hierarchy results


class LSPTool(Tool):
    """
    Tool for interacting with Language Server Protocol servers.

    Provides code intelligence features that help with:
    - Navigating code (go to definition, find references)
    - Understanding code (hover info, type information)
    - Exploring codebase (document/workspace symbols)
    - Analyzing code flow (call hierarchy)
    """

    @property
    @override
    def name(self) -> str:
        return "lsp"

    @property
    @override
    def description(self) -> str:
        return """Interact with Language Server Protocol (LSP) servers to get code intelligence features.

Supported operations:
- goToDefinition: Find where a symbol is defined
- findReferences: Find all references to a symbol
- hover: Get hover information (documentation, type info) for a symbol
- documentSymbol: Get all symbols (functions, classes, variables) in a document
- workspaceSymbol: Search for symbols across the entire workspace
- goToImplementation: Find implementations of an interface or abstract method
- prepareCallHierarchy: Get call hierarchy item at a position (functions/methods)
- incomingCalls: Find all functions/methods that call the function at a position
- outgoingCalls: Find all functions/methods called by the function at a position

All operations require:
- filePath: The file to operate on
- line: The line number (1-based, as shown in editors)
- character: The character offset (1-based, as shown in editors)

Note: LSP servers must be configured for the file type. If no server is available, an error will be returned.

Usage examples:
- Jump to definition: operation="goToDefinition", filePath="src/main.py", line=42, character=15
- Find all usages: operation="findReferences", filePath="src/utils.ts", line=10, character=7
- Get type info: operation="hover", filePath="src/app.js", line=25, character=12"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [op.value for op in LSPOperation],
                    "description": "The LSP operation to perform.",
                },
                "filePath": {
                    "type": "string",
                    "description": "The file path to operate on (absolute path preferred).",
                },
                "line": {
                    "type": "integer",
                    "description": "The line number (1-based, as shown in editors).",
                },
                "character": {
                    "type": "integer",
                    "description": "The character offset (1-based, as shown in editors).",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for workspaceSymbol operation.",
                },
            },
            "required": ["operation", "filePath", "line", "character"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        operation_str = str(kwargs.get("operation", ""))
        file_path = str(kwargs.get("filePath", ""))
        line = int(kwargs.get("line", 0))
        character = int(kwargs.get("character", 0))
        query = kwargs.get("query", "")

        # Parse operation
        try:
            operation = LSPOperation(operation_str)
        except ValueError:
            valid_ops = [op.value for op in LSPOperation]
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Invalid operation: {operation_str}. Valid operations: {', '.join(valid_ops)}",
                is_error=True,
            )

        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            # Try to resolve relative to workspace
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"File not found: {file_path}",
                is_error=True,
            )

        # Determine language from file extension
        language = self._detect_language(file_path)
        if not language:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Unsupported file type: {file_path}",
                is_error=True,
            )

        # Signal to Host layer to perform LSP operation
        # The actual LSP communication happens at the Host layer
        lsp_request = {
            "operation": operation.value,
            "filePath": file_path,
            "line": line,
            "character": character,
            "language": language,
            "query": str(query) if query else None,
        }

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"[LSP request: {operation.value} at {file_path}:{line}:{character}]",
            result_summary=f"lsp:{operation.value}:{file_path}:{line}:{character}",
        )

    def _detect_language(self, file_path: str) -> str | None:
        """Detect language from file extension."""
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".kt": "kotlin",
            ".scala": "scala",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".m": "objective-c",
            ".mm": "objective-cpp",
            ".lua": "lua",
            ".r": "r",
            ".sql": "sql",
            ".sh": "bash",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".vue": "vue",
            ".svelte": "svelte",
        }

        ext = Path(file_path).suffix.lower()
        return ext_to_lang.get(ext)


class LSPConfig:
    """Configuration for LSP servers."""

    # Common LSP server commands by language
    SERVER_COMMANDS = {
        "python": ["pylsp", "pyright", "jedi-language-server"],
        "typescript": ["typescript-language-server", "--stdio"],
        "javascript": ["typescript-language-server", "--stdio"],
        "go": ["gopls"],
        "rust": ["rust-analyzer"],
        "java": ["jdtls"],
        "csharp": ["omnisharp", "-lsp"],
        "ruby": ["solargraph", "stdio"],
        "php": ["intelephense", "--stdio"],
        "c": ["clangd"],
        "cpp": ["clangd"],
    }

    @classmethod
    def get_server_command(cls, language: str) -> list[str] | None:
        """Get the LSP server command for a language."""
        return cls.SERVER_COMMANDS.get(language)


def get_lsp_tools() -> list[Tool]:
    """Get all LSP-related tools."""
    return [LSPTool()]


__all__ = [
    "LSPOperation",
    "LSPResult",
    "LSPTool",
    "LSPConfig",
    "get_lsp_tools",
]