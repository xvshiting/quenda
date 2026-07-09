"""
Scheduled task (Cron) tools for Quenda.

Provides scheduling capabilities for:
- One-shot reminders
- Recurring tasks
- Background execution

Inspired by Claude Code's ScheduleWakeup and CronCreate/CronDelete/CronList tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import override

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class TaskType(str, Enum):
    """Type of scheduled task."""
    ONE_SHOT = "one_shot"
    RECURRING = "recurring"


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str
    cron: str  # cron expression or "one_shot:<timestamp>"
    prompt: str
    task_type: TaskType
    recurring: bool
    durable: bool  # persist to disk
    created_at: datetime = field(default_factory=datetime.now)
    last_run: datetime | None = None
    next_run: datetime | None = None
    active: bool = True


class ScheduleWakeupTool(Tool):
    """
    Tool for scheduling a wake-up in dynamic loop mode.

    Use this when the user has invoked /loop without an interval,
    asking the agent to self-pace iterations.
    """

    @property
    @override
    def name(self) -> str:
        return "schedule_wakeup"

    @property
    @override
    def description(self) -> str:
        return """Schedule when to resume work in /loop dynamic mode.

Use when:
- User invoked /loop without an interval
- You need to self-pace iterations of a specific task

**Important Guidelines for delaySeconds:**

The Anthropic prompt cache has a 5-minute TTL. Choose wisely:

- **Under 5 minutes (60s–270s)**: Cache stays warm. Right for active work.
- **5 minutes to 1 hour (300s–3600s)**: Pay the cache miss. Use when there's no point checking sooner.
- **Avoid 300s**: It's the worst case - cache miss without amortizing it.

For idle ticks with no specific signal, default to **1200s–1800s** (20–30 min).

**Never pick 300s.** If you're tempted to "wait 5 minutes", either drop to 270s (stay in cache) or commit to 1200s+.

Think about what you're actually waiting for, not just "how long should I sleep."

Parameters:
- delaySeconds: Seconds until next wake-up (clamped to [60, 3600])
- prompt: The /loop input to fire on wake-up (pass same input to repeat the loop)
- reason: One short sentence explaining the chosen delay"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "delaySeconds": {
                    "type": "integer",
                    "description": "Seconds from now to wake up (clamped to [60, 3600]).",
                    "minimum": 60,
                    "maximum": 3600,
                },
                "prompt": {
                    "type": "string",
                    "description": "The /loop input to fire on wake-up.",
                },
                "reason": {
                    "type": "string",
                    "description": "One short sentence explaining the chosen delay.",
                },
            },
            "required": ["delaySeconds", "prompt", "reason"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        delay_seconds = int(kwargs.get("delaySeconds", 60))
        prompt = str(kwargs.get("prompt", ""))
        reason = str(kwargs.get("reason", ""))

        # Clamp to valid range
        delay_seconds = max(60, min(3600, delay_seconds))

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"[Wake-up scheduled: {delay_seconds}s later. Reason: {reason}]",
            result_summary=f"wakeup:{delay_seconds}:{reason}",
        )


class CronCreateTool(Tool):
    """
    Tool for creating scheduled tasks.

    Supports:
    - One-shot reminders (fire once, then delete)
    - Recurring tasks (cron schedule)
    """

    @property
    @override
    def name(self) -> str:
        return "cron_create"

    @property
    @override
    def description(self) -> str:
        return """Schedule a prompt to run at a future time.

Uses standard 5-field cron in your local timezone:
`minute hour day-of-month month day-of-week`

Examples:
- `0 9 * * *` — 9am local
- `*/5 * * * *` — every 5 minutes
- `0 * * * *` — hourly
- `0 9 * * 1-5` — weekdays at 9am local

## One-shot tasks (recurring: false)

For "remind me at X" requests — fire once then auto-delete:
- "remind me at 2:30pm today" → cron: "30 14 <today_dom> <today_month> *", recurring: false
- "tomorrow morning, run the smoke test" → cron: "57 8 <tomorrow_dom> <tomorrow_month> *", recurring: false

## Recurring tasks (recurring: true, default)

For "every N minutes" / "every hour" requests:
- "*/5 * * * *" (every 5 min)
- "0 * * * *" (hourly)
- "0 9 * * 1-5" (weekdays at 9am local)

## Avoid :00 and :30 when possible

Every user who asks for "9am" gets `0 9`, landing on the API at the same instant.
When the request is approximate, pick an off-minute:
- "every morning around 9" → "57 8 * * *" or "3 9 * * *" (not "0 9")
- "hourly" → "7 * * * *" (not "0 *")

Only use minute 0 or 30 when user explicitly names that exact time.

## Durability

- durable: false (default) — lives only in this session, gone when process exits
- durable: true — persists to ~/.quenda/scheduled_tasks.json, survives restarts

Use durable only when user explicitly asks ("keep doing this every day", "set this up permanently").

Recurring tasks auto-expire after 7 days."""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "cron": {
                    "type": "string",
                    "description": "Cron expression (5 fields, local timezone).",
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt to execute at the scheduled time.",
                },
                "recurring": {
                    "type": "boolean",
                    "description": "true = recurring task; false = one-shot (default).",
                    "default": True,
                },
                "durable": {
                    "type": "boolean",
                    "description": "Persist to disk and survive restarts (default false).",
                    "default": False,
                },
            },
            "required": ["cron", "prompt"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        import uuid
        from datetime import datetime

        cron_expr = str(kwargs.get("cron", ""))
        prompt = str(kwargs.get("prompt", ""))
        recurring = bool(kwargs.get("recurring", True))
        durable = bool(kwargs.get("durable", False))

        task_id = f"cron_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now().isoformat()

        task_info = {
            "id": task_id,
            "cron": cron_expr,
            "prompt": prompt,
            "recurring": recurring,
            "durable": durable,
            "created_at": created_at,
            "active": True,
        }

        if durable:
            # Signal to Host layer to persist
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"[Durable cron task created: {task_id}]\nSchedule: {cron_expr}\nRecurring: {recurring}\nSaved to ~/.quenda/scheduled_tasks.json",
                result_summary=f"cron_create:durable:{task_id}:{cron_expr}",
            )
        else:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"[Session cron task created: {task_id}]\nSchedule: {cron_expr}\nRecurring: {recurring}\nNote: Task will be lost when this session ends",
                result_summary=f"cron_create:session:{task_id}:{cron_expr}",
            )


class CronDeleteTool(Tool):
    """Tool for canceling a scheduled task."""

    @property
    @override
    def name(self) -> str:
        return "cron_delete"

    @property
    @override
    def description(self) -> str:
        return "Cancel a scheduled cron job by its ID."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Job ID returned by cron_create.",
                },
            },
            "required": ["id"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        task_id = str(kwargs.get("id", ""))

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"[Cron task deleted: {task_id}]",
            result_summary=f"cron_delete:{task_id}",
        )


class CronListTool(Tool):
    """Tool for listing all scheduled tasks."""

    @property
    @override
    def name(self) -> str:
        return "cron_list"

    @property
    @override
    def description(self) -> str:
        return """List all cron jobs scheduled via cron_create.

Shows both:
- Durable jobs (persisted to ~/.quenda/scheduled_tasks.json)
- Session-only jobs (in-memory, lost when process exits)"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        return ToolResult(
            call_id="",
            name=self.name,
            content="[Cron list requested - check result for scheduled tasks]",
            result_summary="cron_list",
        )


class ScheduledTaskStorage:
    """Storage for durable scheduled tasks."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path.home() / ".quenda"
        self.tasks_file = self.storage_dir / "scheduled_tasks.json"
        self._tasks: dict[str, ScheduledTask] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        if self.tasks_file.exists():
            try:
                data = json.loads(self.tasks_file.read_text())
                for task_data in data.get("tasks", []):
                    if task_data.get("active", True):
                        task = ScheduledTask(
                            id=task_data["id"],
                            cron=task_data["cron"],
                            prompt=task_data["prompt"],
                            task_type=TaskType.RECURRING if task_data.get("recurring") else TaskType.ONE_SHOT,
                            recurring=task_data.get("recurring", True),
                            durable=True,
                            created_at=datetime.fromisoformat(task_data.get("created_at", datetime.now().isoformat())),
                            active=task_data.get("active", True),
                        )
                        self._tasks[task.id] = task
            except (json.JSONDecodeError, KeyError):
                self._tasks = {}

    def _save_tasks(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "tasks": [
                {
                    "id": t.id,
                    "cron": t.cron,
                    "prompt": t.prompt,
                    "recurring": t.recurring,
                    "durable": True,
                    "created_at": t.created_at.isoformat(),
                    "active": t.active,
                }
                for t in self._tasks.values()
            ],
            "updated_at": datetime.now().isoformat(),
        }
        self.tasks_file.write_text(json.dumps(data, indent=2))

    def add_task(self, task: ScheduledTask) -> None:
        self._tasks[task.id] = task
        if task.durable:
            self._save_tasks()

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].active = False
            self._save_tasks()
            return True
        return False

    def get_active_tasks(self) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if t.active]


def get_cron_tools() -> list[Tool]:
    """Get all scheduling/cron tools."""
    return [
        ScheduleWakeupTool(),
        CronCreateTool(),
        CronDeleteTool(),
        CronListTool(),
    ]


__all__ = [
    "TaskType",
    "ScheduledTask",
    "ScheduleWakeupTool",
    "CronCreateTool",
    "CronDeleteTool",
    "CronListTool",
    "ScheduledTaskStorage",
    "get_cron_tools",
]