"""
Plan Mode tools for Quenda.

Plan mode allows the agent to:
1. Thoroughly explore the codebase
2. Understand existing patterns and architecture
3. Design an implementation approach
4. Present the plan to the user for approval
5. Exit plan mode when ready to implement

Inspired by Claude Code's EnterPlanModeTool and ExitPlanModeTool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult
import json 


class PlanModeState(str, Enum):
    """State of plan mode."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class Plan:
    """A plan created during plan mode."""
    id: str
    title: str
    description: str
    steps: list[dict]
    files_to_modify: list[str]
    dependencies: list[str]
    risks: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    approved: bool = False
    approved_at: datetime | None = None


class EnterPlanModeTool(Tool):
    """
    Tool for entering plan mode.

    Use this tool proactively when you're about to start a non-trivial
    implementation task. Getting user sign-off on your approach before
    writing code prevents wasted effort and ensures alignment.
    """

    @property
    @override
    def name(self) -> str:
        return "enter_plan_mode"

    @property
    @override
    def description(self) -> str:
        return """Use this tool when a task has genuine ambiguity about the right approach
and getting user input before coding would prevent significant rework.

This tool transitions you into plan mode where you can:
1. Thoroughly explore the codebase using Glob, Grep, and Read tools
2. Understand existing patterns and architecture
3. Design an implementation approach
4. Present your plan to the user for approval
5. Exit plan mode when ready to implement

## When to Use This Tool

Plan mode is valuable when the implementation approach is genuinely unclear:

1. **Significant Architectural Ambiguity**: Multiple reasonable approaches exist
   - Example: "Add caching to the API" - Redis vs in-memory vs file-based
   - Example: "Add real-time updates" - WebSockets vs SSE vs polling

2. **Unclear Requirements**: You need to explore and clarify before proceeding
   - Example: "Make the app faster" - need to profile and identify bottlenecks
   - Example: "Refactor this module" - need to understand target architecture

3. **High-Impact Restructuring**: Significant code changes with risk
   - Example: "Redesign the authentication system"
   - Example: "Migrate from one state management approach to another"

4. **Multi-File Changes**: Task will touch more than 2-3 files
   - Example: "Refactor the authentication system"
   - Example: "Add a new API endpoint with tests"

## When NOT to Use This Tool

Skip plan mode when:
- The task is straightforward even if it touches multiple files
- The user's request is specific enough that the implementation path is clear
- You're adding a feature with an obvious implementation pattern
- Bug fixes where the fix is clear once you understand the bug
- Research/exploration tasks (use the Agent tool instead)
- The user says "let's do X" or "can we work on X" — just get started

## Important Notes

- This tool REQUIRES user approval - they must consent to entering plan mode"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why plan mode is needed for this task.",
                },
                "initial_thoughts": {
                    "type": "string",
                    "description": "Optional initial thoughts or hypotheses about the approach.",
                },
            },
            "required": ["reason"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        reason = str(kwargs.get("reason", ""))
        initial_thoughts = kwargs.get("initial_thoughts", "")

        # Signal to Host layer to enter plan mode
        return ToolResult(
            call_id="",
            name=self.name,
            content=f"[Plan mode requested: {reason}]\n\nI'll explore the codebase and design an implementation approach for your approval.",
            result_summary="enter_plan_mode",
        )


class ExitPlanModeTool(Tool):
    """
    Tool for exiting plan mode with a completed plan.

    Present your implementation plan to the user for approval.
    """

    @property
    @override
    def name(self) -> str:
        return "exit_plan_mode"

    @property
    @override
    def description(self) -> str:
        return """Exit plan mode and present your implementation plan for user approval.

After exploring the codebase and designing an approach, use this tool to:
1. Present your complete plan
2. Get user approval or feedback
3. Transition back to implementation mode

The plan should include:
- Clear description of the approach
- Files that will be modified
- Step-by-step implementation sequence
- Potential risks and mitigations

If the user approves, you'll proceed with implementation.
If they have feedback, you'll revise the plan."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "plan_title": {
                    "type": "string",
                    "description": "Brief title for the plan.",
                },
                "plan_description": {
                    "type": "string",
                    "description": "Detailed description of the implementation approach.",
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered list of implementation steps.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What this step accomplishes.",
                            },
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files modified in this step.",
                            },
                        },
                        "required": ["description"],
                    },
                },
                "files_to_modify": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "All files that will be modified.",
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Potential risks and how they'll be mitigated.",
                },
            },
            "required": ["plan_title", "plan_description", "steps"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        plan_title = str(kwargs.get("plan_title", ""))
        plan_description = str(kwargs.get("plan_description", ""))
        steps = kwargs.get("steps", [])
        files_to_modify = kwargs.get("files_to_modify", [])
        risks = kwargs.get("risks", [])

        # Build plan summary
        steps_list = steps if isinstance(steps, list) else []
        steps_text = "\n".join([
            f"  {i+1}. {s.get('description', '')}"
            for i, s in enumerate(steps_list)
        ])

        files_text = ""
        if files_to_modify:
            files_list = files_to_modify if isinstance(files_to_modify, list) else []
            files_text = f"\n\n**Files to modify:**\n" + "\n".join([f"  - {f}" for f in files_list])

        risks_text = ""
        if risks:
            risks_list = risks if isinstance(risks, list) else []
            risks_text = f"\n\n**Potential risks:**\n" + "\n".join([f"  - {r}" for r in risks_list])

        content = f"""## Plan: {plan_title}

{plan_description}

**Implementation steps:**
{steps_text}
{files_text}
{risks_text}

---
Awaiting your approval to proceed with implementation."""

        return ToolResult(
            call_id="",
            name=self.name,
            content=content,
            result_summary="exit_plan_mode",
        )


class PlanStorage:
    """Storage for plans during a session."""

    def __init__(self, session_dir: Path | None = None) -> None:
        self.session_dir = session_dir
        self.plans_file = session_dir / "plans.json" if session_dir else None
        self._plans: dict[str, Plan] = {}
        self._load_plans()

    def _load_plans(self) -> None:
        if self.plans_file and self.plans_file.exists():
            try:
                data = json.loads(self.plans_file.read_text())
                for plan_data in data.get("plans", []):
                    plan = Plan(
                        id=plan_data["id"],
                        title=plan_data["title"],
                        description=plan_data["description"],
                        steps=plan_data.get("steps", []),
                        files_to_modify=plan_data.get("files_to_modify", []),
                        dependencies=plan_data.get("dependencies", []),
                        risks=plan_data.get("risks", []),
                        approved=plan_data.get("approved", False),
                    )
                    self._plans[plan.id] = plan
            except (json.JSONDecodeError, KeyError):
                self._plans = {}

    def _save_plans(self) -> None:
        if self.plans_file:
            data = {
                "plans": [
                    {
                        "id": p.id,
                        "title": p.title,
                        "description": p.description,
                        "steps": p.steps,
                        "files_to_modify": p.files_to_modify,
                        "dependencies": p.dependencies,
                        "risks": p.risks,
                        "approved": p.approved,
                    }
                    for p in self._plans.values()
                ]
            }
            self.plans_file.write_text(json.dumps(data, indent=2))

    def create_plan(
        self,
        title: str,
        description: str,
        steps: list[dict],
        files_to_modify: list[str] | None = None,
        risks: list[str] | None = None,
    ) -> Plan:
        import uuid
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        plan = Plan(
            id=plan_id,
            title=title,
            description=description,
            steps=steps,
            files_to_modify=files_to_modify or [],
            dependencies=[],
            risks=risks or [],
        )
        self._plans[plan_id] = plan
        self._save_plans()
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        return self._plans.get(plan_id)

    def approve_plan(self, plan_id: str) -> Plan | None:
        plan = self._plans.get(plan_id)
        if plan:
            plan.approved = True
            plan.approved_at = datetime.now()
            self._save_plans()
        return plan


def get_plan_tools() -> list[Tool]:
    """Get all plan mode tools."""
    return [
        EnterPlanModeTool(),
        ExitPlanModeTool(),
    ]


__all__ = [
    "PlanModeState",
    "Plan",
    "EnterPlanModeTool",
    "ExitPlanModeTool",
    "PlanStorage",
    "get_plan_tools",
]