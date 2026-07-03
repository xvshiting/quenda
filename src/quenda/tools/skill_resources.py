"""
Skill resource tools - Tools for accessing skill resources.

These tools allow the model to:
- Read resource content from active skills
- List available resources from active skills
- Execute executable skill assets (scripts)

All resources are accessed via skill:// URIs for stable identification.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
from quenda.host.skill.uri import SkillResourceURI

if TYPE_CHECKING:
    from quenda.host.skill.resources import ResourceResolver


class ReadSkillResourceTool(Tool):
    """
    Read content from a skill resource using a skill:// URI.

    Skill resources include reference documents, templates, and guides
    provided by active skills. Use list_skill_resources to discover
    available resources.

    Example:
        read_skill_resource(uri="skill://code-review/checklist.md")
    """

    def __init__(self, resolver: ResourceResolver) -> None:
        self._resolver = resolver

    @property
    @override
    def name(self) -> str:
        return "read_skill_resource"

    @property
    @override
    def description(self) -> str:
        return """Read content from a skill resource using a skill:// URI.

Skill resources include reference documents, templates, and guides provided by active skills.
Use list_skill_resources to discover available resources.

Example: read_skill_resource(uri="skill://code-review/checklist.md")"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Skill resource URI (skill://<skill-name>/<resource-path>)",
                    "pattern": "^skill://[a-z0-9-_]+/.+$",
                },
            },
            "required": ["uri"],
        }

    @override
    def execute(self, **kwargs) -> ToolResult:
        uri = kwargs.get("uri", "")
        if not isinstance(uri, str):
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: uri must be a string",
                is_error=True,
            )

        loaded = self._resolver.resolve_uri(uri)
        if loaded is None:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: Resource not found: {uri}\n\nUse list_skill_resources to see available resources.",
                is_error=True,
            )

        return ToolResult(
            call_id="",
            name=self.name,
            content=loaded.content,
            display_hint=f"{loaded.skill_name}/{loaded.resource_path}",
            result_summary=f"{len(loaded.content)} chars from {loaded.uri()}",
        )


class ListSkillResourcesTool(Tool):
    """
    List available resources from active skills.

    Returns skill:// URIs that can be used with read_skill_resource
    and execute_skill_asset.
    """

    def __init__(self, resolver: ResourceResolver) -> None:
        self._resolver = resolver

    @property
    @override
    def name(self) -> str:
        return "list_skill_resources"

    @property
    @override
    def description(self) -> str:
        return """List resources available from active skills.

Returns skill:// URIs that can be used with read_skill_resource.
Executable assets are marked with [executable]."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Filter to a specific skill (optional)",
                },
                "type": {
                    "type": "string",
                    "enum": ["reference", "asset", "all"],
                    "description": "Filter by resource type (default: all)",
                },
            },
        }

    @override
    def execute(self, **kwargs) -> ToolResult:
        skill_name = kwargs.get("skill_name")
        resource_type = kwargs.get("type", "all")

        resources = self._resolver.list_resources()

        # Filter
        if skill_name:
            resources = [r for r in resources if r.skill_name == skill_name]
        if resource_type != "all":
            resources = [r for r in resources if r.resource_type == resource_type]

        if not resources:
            active_skills = list(set(r.skill_name for r in self._resolver.list_resources()))
            if not active_skills:
                return ToolResult(
                    call_id="",
                    name=self.name,
                    content="No active skills. Use /skill activate <name> to activate a skill.",
                )
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"No resources found matching the criteria.\n\nActive skills: {', '.join(active_skills)}",
            )

        lines = ["## Available Skill Resources\n"]
        for r in resources:
            safe_marker = " [executable]" if r.safe_to_execute else ""
            lines.append(f"- `{r.uri()}` ({r.resource_type}){safe_marker}")
            if r.description:
                lines.append(f"  {r.description}")

        lines.append("")
        lines.append("Use `read_skill_resource(uri)` to read content.")
        lines.append("Use `execute_skill_asset(uri, args)` to run executable assets.")

        return ToolResult(
            call_id="",
            name=self.name,
            content="\n".join(lines),
        )


class ExecuteSkillAssetTool(Tool):
    """
    Execute a skill asset (script) with safety controls.

    SECURITY:
    - Only assets marked safe_to_execute=True can run
    - Script receives arguments via command line
    - Output is captured and returned

    The script should be a Python script that:
    - Reads arguments from sys.argv[1:]
    - Prints results to stdout
    - Returns exit code 0 on success
    """

    def __init__(self, resolver: ResourceResolver) -> None:
        self._resolver = resolver

    @property
    @override
    def name(self) -> str:
        return "execute_skill_asset"

    @property
    @override
    def description(self) -> str:
        return """Execute a skill asset script.

Only assets marked as 'safe' by the skill author can be executed.
Use list_skill_resources to see which assets are executable (marked with [executable]).

Arguments are passed as command-line arguments to the script."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Skill asset URI (must be marked executable)",
                    "pattern": "^skill://[a-z0-9-_]+/.+\\.py$",
                },
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments to pass to the script",
                },
            },
            "required": ["uri"],
        }

    @override
    def execute(self, **kwargs) -> ToolResult:
        uri = kwargs.get("uri", "")
        arguments = kwargs.get("arguments", [])

        if not isinstance(uri, str):
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: uri must be a string",
                is_error=True,
            )

        if not isinstance(arguments, list):
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: arguments must be an array of strings",
                is_error=True,
            )

        # Resolve the resource info first to check safe_to_execute
        info = self._resolver.resolve_uri_to_info(uri)
        if info is None:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: Asset not found: {uri}\n\nUse list_skill_resources to see available assets.",
                is_error=True,
            )

        # SECURITY: Check safe_to_execute flag
        if not info.safe_to_execute:
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: Asset not executable.\n\nOnly assets marked 'safe: true' in SKILL.md can be executed.\n"
                        "This is a security measure to prevent accidental execution of untrusted scripts.",
                is_error=True,
            )

        # Load the content
        loaded = self._resolver.resolve_uri(uri)
        if loaded is None:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error: Could not load asset: {uri}",
                is_error=True,
            )

        # Execute the script
        try:
            result = subprocess.run(
                [sys.executable, str(loaded.path)] + [str(arg) for arg in arguments],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            if result.returncode != 0:
                return ToolResult(
                    call_id="",
                    name=self.name,
                    content=f"Script exited with code {result.returncode}:\n{output}",
                    is_error=True,
                )

            return ToolResult(
                call_id="",
                name=self.name,
                content=output.strip() if output.strip() else "(no output)",
                result_summary=f"Executed {loaded.uri()}",
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: Script execution timed out (30s limit)",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Error executing script: {e}",
                is_error=True,
            )


__all__ = [
    "ReadSkillResourceTool",
    "ListSkillResourcesTool",
    "ExecuteSkillAssetTool",
]
