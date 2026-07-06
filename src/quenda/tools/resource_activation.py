"""
activate_resource tool - Request temporary attachment of a session resource.

This framework-reserved tool lets the model ask Runtime to attach a historical
resource, such as an image, when the lightweight resource placeholder is not
enough to answer the user.
"""

from __future__ import annotations

from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class ActivateResourceTool(Tool):
    """Framework-reserved tool for lazy session resource activation."""

    @property
    @override
    def name(self) -> str:
        return "activate_resource"

    @property
    @override
    def description(self) -> str:
        return """Attach a historical session resource for the next model step.

Use this when the conversation contains a resource placeholder such as [Resource img0]
and the user asks about visual or raw details that are not available from the
placeholder or prior summary. Pass the exact resource_id shown in context.

Do not use this for files in the workspace; use file tools for those."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Exact resource id from the session resource placeholder, such as img0.",
                },
                "purpose": {
                    "type": "string",
                    "description": "Short reason why raw resource content is needed.",
                },
            },
            "required": ["resource_id"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        resource_id = str(kwargs.get("resource_id", "")).strip()
        purpose = str(kwargs.get("purpose", "")).strip()

        if not resource_id:
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: resource_id is required.",
                is_error=True,
            )

        content = f"Resource '{resource_id}' activation requested."
        if purpose:
            content += f" Purpose: {purpose}"

        return ToolResult(
            call_id="",
            name=self.name,
            content=content,
            is_error=False,
            result_summary=f"resource_activation:{resource_id}",
        )


__all__ = ["ActivateResourceTool"]
