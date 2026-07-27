"""
File editing tools - write_file and apply_patch.

write_file: Create new files or completely overwrite existing ones.
apply_patch: Modify existing files with targeted patches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.runtime.permission import (
    DenyPermissionPolicy,
    PermissionKind,
    PermissionLifetime,
    PermissionPolicy,
    PermissionRequest,
    PermissionScope,
)


@dataclass
class EditingConfig:
    """Configuration for editing tools."""

    max_content_chars: int = 1000000  # 1MB max content


def _leading_whitespace(line: str) -> str:
    """Return the leading spaces and tabs from a line."""
    return line[: len(line) - len(line.lstrip(" \t"))]


def _indentation_signature(lines: list[str]) -> tuple[str, list[tuple[str, str]]] | None:
    """Represent a block independently of its common leading indentation."""
    non_empty = [line for line in lines if line.strip(" \t")]
    if not non_empty:
        return None

    base_indent = _leading_whitespace(non_empty[0])
    signature: list[tuple[str, str]] = []
    for line in lines:
        if not line.strip(" \t"):
            signature.append(("", ""))
            continue

        indent = _leading_whitespace(line)
        if not indent.startswith(base_indent):
            return None
        signature.append((indent[len(base_indent):], line[len(indent):].rstrip(" \t")))

    return base_indent, signature


def _find_indentation_equivalent_spans(
    content: str,
    old_text: str,
) -> list[tuple[int, int, str, str]]:
    """Find unique-location candidates that differ only by common indentation."""
    old_lines = old_text.splitlines()
    old_signature = _indentation_signature(old_lines)
    if not old_lines or old_signature is None:
        return []

    supplied_indent, expected = old_signature
    content_lines_with_endings = content.splitlines(keepends=True)
    content_lines = [line.rstrip("\r\n") for line in content_lines_with_endings]
    window_size = len(old_lines)
    offsets = [0]
    for line in content_lines_with_endings:
        offsets.append(offsets[-1] + len(line))

    matches: list[tuple[int, int, str, str]] = []
    for index in range(len(content_lines) - window_size + 1):
        candidate_lines = content_lines[index:index + window_size]
        candidate_signature = _indentation_signature(candidate_lines)
        if candidate_signature is None:
            continue

        actual_indent, candidate = candidate_signature
        if candidate != expected:
            continue

        start = offsets[index]
        end = offsets[index + window_size]
        if not old_text.endswith(("\n", "\r")):
            end -= len(content_lines_with_endings[index + window_size - 1])
            end += len(content_lines[index + window_size - 1])
        matches.append((start, end, supplied_indent, actual_indent))

    return matches


def _rebase_indentation(text: str, supplied_indent: str, actual_indent: str) -> str:
    """Move replacement text from the supplied block indent to the matched indent."""
    if supplied_indent == actual_indent:
        return text

    rebased: list[str] = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        if body.strip(" \t") and body.startswith(supplied_indent):
            body = actual_indent + body[len(supplied_indent):]
        rebased.append(body + ending)
    return "".join(rebased)


def _validate_path(workspace: Path, path: str) -> tuple[Path, str | None]:
    """Validate path is within workspace. Returns (resolved_path, error_message)."""
    try:
        resolved = (workspace / path).resolve()
        if not str(resolved).startswith(str(workspace.resolve())):
            return resolved, "Access denied - path outside workspace"
        return resolved, None
    except Exception as e:
        return Path(path), f"Invalid path: {e}"


def _generate_diff_preview(old_content: str, new_content: str, max_lines: int = 0) -> str:
    """
    Generate a diff preview for file modifications.

    Format (Claude Code style):
        398 ### Phase 1: 事件增强
        399 -1. 创建 `src/kora/interface/console.py`
        400 -2. 实现 `ConsoleRenderer` 类
        399 +1. ✅ 创建 `src/kora/interface/console.py`
        400 +2. ✅ 实现 `ConsoleRenderer` 类
        402
        403 ### Phase 2: ConsoleRenderer

    Features:
    - Line numbers for all lines (padded for alignment)
    - Space after line number
    - Content starting with "-" = removed (red background)
    - Content starting with "+" = added (green background)
    - Otherwise = context line (no background)
    - 2 context lines before and after each change block

    Args:
        old_content: Original file content.
        new_content: New file content.
        max_lines: Ignored, shows full diff.

    Returns:
        A diff string with context lines.
    """
    import difflib

    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    context_lines = 2  # Lines of context before/after changes

    diff_lines = []
    last_end_old = 0
    last_end_new = 0

    for group in difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes():
        tag, i1, i2, j1, j2 = group

        if tag == 'equal':
            last_end_old = i2
            last_end_new = j2
            continue

        # Show context lines before the change
        context_start_old = max(0, i1 - context_lines)
        context_start_new = max(0, j1 - context_lines)
        # Use the last position to avoid duplicate context
        context_start_old = max(context_start_old, last_end_old)
        context_start_new = max(context_start_new, last_end_new)

        # Show context from old file (they should be same content)
        for idx in range(context_start_old, i1):
            line_num = idx + 1  # 1-indexed
            line_content = old_lines[idx]
            diff_lines.append(f"{line_num} {line_content}")

        # Show removed lines
        for idx in range(i1, i2):
            line_num = idx + 1
            line_content = old_lines[idx]
            diff_lines.append(f"{line_num} -{line_content}")

        # Show added lines
        for idx in range(j1, j2):
            line_num = idx + 1
            line_content = new_lines[idx]
            diff_lines.append(f"{line_num} +{line_content}")

        # Show context lines after the change
        context_end_old = min(len(old_lines), i2 + context_lines)
        context_end_new = min(len(new_lines), j2 + context_lines)

        for idx in range(i2, context_end_old):
            line_num = idx + 1
            line_content = old_lines[idx]
            diff_lines.append(f"{line_num} {line_content}")

        last_end_old = context_end_old
        last_end_new = context_end_new

    return "\n".join(diff_lines)


# =============================================================================
# write_file - Create new files
# =============================================================================


class WriteFileTool(Tool):
    """
    Create a new file or completely overwrite an existing one.

    Use this for:
    - Creating new files
    - Completely replacing file content

    For partial modifications, use apply_patch instead.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: EditingConfig | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or EditingConfig()
        self.permission_policy = permission_policy

    @property
    @override
    def name(self) -> str:
        return "write_file"

    @property
    @override
    def description(self) -> str:
        return "Create a new file or completely overwrite an existing file. Creates parent directories automatically."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write.",
                },
            },
            "required": ["path", "content"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if not isinstance(path, str) or not isinstance(content, str):
            return ToolResult("", self.name, "Error: path and content must be strings", is_error=True)

        file_path, error = _validate_path(self.workspace, path)
        if error:
            policy = self.permission_policy or DenyPermissionPolicy()
            request = PermissionRequest(
                kind=PermissionKind.FILESYSTEM_WRITE,
                resource=str(file_path.parent),
                scope=PermissionScope.DIRECTORY,
                reason=f"Writing files under directory outside workspace: {file_path.parent}",
                lifetime=PermissionLifetime.SESSION,
                tool_name=self.name,
                tool_args={"path": path, "content": content},
            )
            decision = policy.decide(request)
            if not decision.allowed:
                return ToolResult("", self.name, f"Error: {decision.reason or error}", is_error=True)

        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file already exists
            existed = file_path.exists()
            old_content = file_path.read_text(encoding="utf-8") if existed else ""

            # Write file
            file_path.write_text(content, encoding="utf-8")

            action = "Updated" if existed else "Created"
            display_hint = path if len(path) <= 40 else "..." + path[-37:]
            result_summary = f"{len(content)} chars" + (" (new)" if not existed else "")

            # Generate change_preview for existing files
            change_preview = ""
            if existed and old_content != content:
                change_preview = _generate_diff_preview(old_content, content, max_lines=10)

            return ToolResult(
                "",
                self.name,
                f"{action} {path} ({len(content)} chars)",
                display_hint=display_hint,
                result_summary=result_summary,
                change_preview=change_preview,
            )

        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)


# =============================================================================
# apply_patch - Modify existing files
# =============================================================================


class ApplyPatchTool(Tool):
    """
    Apply a patch to modify an existing file.

    Safer than write_file for modifications because:
    - Shows exactly what changed
    - Can preview changes with dry_run
    - Fails if context doesn't match
    """

    def __init__(
        self,
        workspace_root: Path | str,
        config: EditingConfig | None = None,
        permission_policy: PermissionPolicy | None = None,
    ) -> None:
        self.workspace = Path(workspace_root).resolve()
        self.config = config or EditingConfig()
        self.permission_policy = permission_policy

    @property
    @override
    def name(self) -> str:
        return "apply_patch"

    @property
    @override
    def description(self) -> str:
        return "Apply a patch to modify an existing file. Safer than write_file for partial changes."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to modify.",
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find and replace. Must match exactly.",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text.",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying the file.",
                    "default": False,
                },
            },
            "required": ["path", "old_text", "new_text"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        path = kwargs.get("path", "")
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")
        dry_run = bool(kwargs.get("dry_run", False))

        if not isinstance(path, str) or not isinstance(old_text, str) or not isinstance(new_text, str):
            return ToolResult("", self.name, "Error: path, old_text, and new_text must be strings", is_error=True)

        file_path, error = _validate_path(self.workspace, path)
        if error:
            policy = self.permission_policy or DenyPermissionPolicy()
            request = PermissionRequest(
                kind=PermissionKind.FILESYSTEM_WRITE,
                resource=str(file_path.parent),
                scope=PermissionScope.DIRECTORY,
                reason=f"Patching files under directory outside workspace: {file_path.parent}",
                lifetime=PermissionLifetime.SESSION,
                tool_name=self.name,
                tool_args={"path": path, "old_text": old_text, "new_text": new_text},
            )
            decision = policy.decide(request)
            if not decision.allowed:
                return ToolResult("", self.name, f"Error: {decision.reason or error}", is_error=True)

        if not file_path.exists():
            return ToolResult("", self.name, f"Error: File not found: {path}", is_error=True)

        try:
            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                equivalent_matches = _find_indentation_equivalent_spans(content, old_text)
                if len(equivalent_matches) > 1:
                    return ToolResult(
                        "",
                        self.name,
                        (
                            "Error: old_text matches multiple blocks after normalizing "
                            "indentation. Please provide more context to make it unique."
                        ),
                        is_error=True,
                    )
                if not equivalent_matches:
                    return ToolResult(
                        "",
                        self.name,
                        (
                            "Error: old_text not found in the current file, even after "
                            "normalizing indentation. Re-read the target section and retry "
                            "with a unique, up-to-date block."
                        ),
                        is_error=True,
                    )

                start, end, supplied_indent, actual_indent = equivalent_matches[0]
                replacement = _rebase_indentation(
                    new_text,
                    supplied_indent,
                    actual_indent,
                )
                new_content = content[:start] + replacement + content[end:]
            else:
                # Count occurrences
                count = content.count(old_text)
                if count > 1:
                    return ToolResult(
                        "",
                        self.name,
                        f"Error: old_text appears {count} times. Please provide more context to make it unique.",
                        is_error=True,
                    )

                new_content = content.replace(old_text, new_text, 1)

            if dry_run:
                # Show diff
                old_lines = old_text.split("\n")
                new_lines = new_text.split("\n")

                diff = ["Dry run - changes that would be made:\n"]
                diff.append(f"File: {path}\n")
                diff.append("--- old")
                diff.append("+++ new")

                for line in old_lines:
                    diff.append(f"- {line}")
                for line in new_lines:
                    diff.append(f"+ {line}")

                return ToolResult("", self.name, "\n".join(diff))

            # Generate change_preview before applying
            change_preview = _generate_diff_preview(content, new_content, max_lines=10)

            # Apply the patch
            file_path.write_text(new_content, encoding="utf-8")

            display_hint = path if len(path) <= 40 else "..." + path[-37:]
            result_summary = "1 change applied"

            return ToolResult(
                "",
                self.name,
                f"Applied patch to {path}",
                display_hint=display_hint,
                result_summary=result_summary,
                change_preview=change_preview,
            )

        except Exception as e:
            return ToolResult("", self.name, f"Error: {e}", is_error=True)
