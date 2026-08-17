"""Publish a workspace file as a durable Web-session attachment."""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.web.models.session import SessionAttachment


class PublishAttachmentTool(Tool):
    """A narrow, workspace-scoped adapter for returning files to Web users."""

    def __init__(
        self,
        workspace: Path,
        destination: Path,
        *,
        max_files: int = 8,
        max_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.workspace = workspace.resolve()
        self.destination = destination
        self.max_files = max_files
        self.max_bytes = max_bytes
        self.published: list[SessionAttachment] = []

    @property
    @override
    def name(self) -> str:
        return "publish_attachment"

    @property
    @override
    def description(self) -> str:
        return """Send a file or image from the current workspace to the user.

Use this after creating a report, archive, document, image, video, or other
artifact the user should be able to preview or download in the Web chat. The
path must refer to a file inside the current workspace. The file is copied into
durable session storage, so later workspace changes do not alter the attachment."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace-relative path of the file to send.",
                },
                "name": {
                    "type": "string",
                    "description": "Optional download filename. Defaults to the source filename.",
                },
            },
            "required": ["path"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        if len(self.published) >= self.max_files:
            return self._error(f"At most {self.max_files} files can be published in one turn.")

        raw_path = str(kwargs.get("path", "")).strip()
        if not raw_path:
            return self._error("path is required.")
        candidate = Path(raw_path)
        source = (self.workspace / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not source.is_relative_to(self.workspace):
            return self._error("Only files inside the current workspace can be published.")
        if not source.is_file():
            return self._error(f"File not found: {raw_path}")
        size = source.stat().st_size
        if size > self.max_bytes:
            return self._error(f"File exceeds the {self.max_bytes // (1024 * 1024)} MB limit.")

        requested_name = Path(str(kwargs.get("name") or source.name)).name
        if not requested_name or requested_name in {".", ".."}:
            requested_name = source.name
        attachment_id = uuid.uuid4().hex[:8]
        self.destination.mkdir(parents=True, exist_ok=True)
        target = self.destination / f"{attachment_id}-{requested_name}"
        shutil.copy2(source, target)
        media_type = mimetypes.guess_type(requested_name)[0] or "application/octet-stream"
        attachment = SessionAttachment(
            id=attachment_id,
            name=requested_name,
            media_type=media_type,
            size=size,
            path=str(target),
        )
        self.published.append(attachment)
        return ToolResult(
            call_id="",
            name=self.name,
            content=f"Published '{requested_name}' to the Web chat.",
            display_hint=requested_name,
            result_summary=f"published_attachment:{attachment_id}",
        )

    def _error(self, message: str) -> ToolResult:
        return ToolResult(
            call_id="",
            name=self.name,
            content=f"Error: {message}",
            is_error=True,
        )
