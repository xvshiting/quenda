"""
request_interaction tool - Ask human for a decision.

This is a framework-reserved tool that allows the LLM to request
structured user interaction (choice, confirm, input, menu).

The tool is special:
- Semantically: it's not "acting on the world", it's "asking human to decide"
- Implementation: it uses tool call's structured, extensible nature
- Execution: returns a placeholder result; Host intercepts after Kernel completes

See ADR-012 for design rationale.
"""

from __future__ import annotations

from typing import override

from kora.kernel.tool import Tool
from kora.kernel.types import ToolResult


class RequestInteractionTool(Tool):
    """
    Framework-reserved tool for requesting user interaction.

    When the LLM calls this tool, the Host layer will:
    1. Detect the tool call after Kernel completes
    2. Construct an InteractionRequest
    3. Have Interface render the choice
    4. Collect user response
    5. Inject response as user message for next round
    """

    @property
    @override
    def name(self) -> str:
        return "request_interaction"

    @property
    @override
    def description(self) -> str:
        return """Request user interaction when you need a human decision.

Use this tool when you should not guess blindly and need the user to:
- Choose between multiple valid next steps
- Confirm a risky action
- Provide free-form input
- Select from a menu of candidates

The user's choice will be provided as a response in the next turn."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["choice", "confirm", "input", "menu"],
                    "description": "Type of interaction: choice (pick one), confirm (yes/no), input (free text), menu (list selection).",
                },
                "title": {
                    "type": "string",
                    "description": "Short title for the interaction.",
                },
                "message": {
                    "type": "string",
                    "description": "Explanation of what the user is being asked to decide.",
                },
                "options": {
                    "type": "array",
                    "description": "Available choices (for choice/menu kinds).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier for this option.",
                            },
                            "label": {
                                "type": "string",
                                "description": "Display label for this option.",
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional longer description.",
                            },
                            "is_default": {
                                "type": "boolean",
                                "description": "Whether this is the default selection.",
                            },
                        },
                        "required": ["id", "label"],
                    },
                },
                "default_option_id": {
                    "type": "string",
                    "description": "ID of the default option (alternative to is_default on option).",
                },
            },
            "required": ["kind", "title"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        """
        Execute the interaction request.

        Returns a placeholder result. The actual interaction happens at
        the Host layer after Kernel completes this turn.
        """
        kind = kwargs.get("kind", "choice")
        title = kwargs.get("title", "Interaction Required")

        # Return placeholder - Host will intercept and handle the actual interaction
        return ToolResult(
            call_id="",
            name=self.name,
            content=f"[Interaction request queued: {kind} - {title}. Waiting for user response...]",
        )


__all__ = ["RequestInteractionTool"]
