"""
request_skill_activation tool - Ask Host to activate a discovered skill.

This tool allows the model to request skill activation within the same Run.
The activation is processed immediately, and the skill's instructions become
available for the next model step.

Architecture (ADR-027):
- Tool returns a result indicating the activation request
- Runtime/Host processes the activation within the same Run
- No rollback, no new Run, no followup message
- Skill instructions apply from the next Step
"""

from __future__ import annotations

from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


class RequestSkillActivationTool(Tool):
    """
    Framework-reserved tool for requesting skill activation.

    When executed, this tool signals that a skill should be activated.
    The actual activation is handled by the Runtime/Host layer after
    the tool batch completes, within the same Run.

    The skill's instructions will be available in the next model step,
    without creating a new Run or rolling back any tool results.
    """

    @property
    @override
    def name(self) -> str:
        return "request_skill_activation"

    @property
    @override
    def description(self) -> str:
        return """Request activation of a discovered skill by exact name.

Use this only when:
- The prompt shows an Available Skills catalog
- You need the full instructions for one of those skills
- The skill is not already active

The skill will be activated immediately, and its instructions will be
available for your next response. You can continue using other tools
in the same response - their results will not be lost."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Exact skill name from the Available Skills catalog.",
                },
                "reason": {
                    "type": "string",
                    "description": "Short explanation of why this skill is needed for the current task.",
                },
            },
            "required": ["skill_name"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        """
        Execute the skill activation request.

        Returns a ToolResult that signals to the Runtime/Host layer
        which skill should be activated. The activation happens after
        the entire tool batch completes, within the same Run.

        The result_summary field is used to communicate the skill name
        to the Runtime layer for processing.
        """
        skill_name = str(kwargs.get("skill_name", "")).strip()
        reason = str(kwargs.get("reason", "")).strip()

        if not skill_name:
            return ToolResult(
                call_id="",
                name=self.name,
                content="Error: skill_name is required.",
                is_error=True,
            )

        # Return a result that signals skill activation
        # The Runtime layer will detect this and process the activation
        return ToolResult(
            call_id="",
            name=self.name,
            content=f"Skill '{skill_name}' activation requested.",
            is_error=False,
            # Use result_summary as a signal to Runtime layer
            # Format: "skill_activation:<skill_name>"
            result_summary=f"skill_activation:{skill_name}",
        )


__all__ = ["RequestSkillActivationTool"]
