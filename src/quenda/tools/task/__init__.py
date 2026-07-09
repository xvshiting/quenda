"""
Task management tools for Quenda.

Tools for creating, updating, and managing a structured task list
during coding sessions. Helps track progress on complex multi-step tasks.

Inspired by Claude Code's TodoWriteTool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import override
import json

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolResult


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELETED = "deleted"


@dataclass
class Task:
    """A single task in the task list."""
    id: str
    subject: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    active_form: str = ""
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "activeForm": self.active_form,
            "owner": self.owner,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            subject=data["subject"],
            description=data["description"],
            status=TaskStatus(data.get("status", "pending")),
            active_form=data.get("activeForm", ""),
            owner=data.get("owner", ""),
            created_at=datetime.fromisoformat(data.get("createdAt", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updatedAt", datetime.now().isoformat())),
        )


class TaskManager:
    """
    Manager for the session's task list.

    Tasks are stored in a JSON file in the session directory.
    """

    def __init__(self, session_dir: Path | None = None) -> None:
        """
        Initialize the task manager.

        Args:
            session_dir: Directory for storing tasks. If None, uses in-memory only.
        """
        self.session_dir = session_dir
        self.tasks_file = session_dir / "tasks.json" if session_dir else None
        self._tasks: dict[str, Task] = {}
        self._next_id = 1
        self._load_tasks()

    def _load_tasks(self) -> None:
        """Load tasks from file if available."""
        if self.tasks_file and self.tasks_file.exists():
            try:
                data = json.loads(self.tasks_file.read_text())
                for task_data in data.get("tasks", []):
                    task = Task.from_dict(task_data)
                    self._tasks[task.id] = task
                self._next_id = data.get("nextId", len(self._tasks) + 1)
            except (json.JSONDecodeError, KeyError):
                self._tasks = {}
                self._next_id = 1

    def _save_tasks(self) -> None:
        """Save tasks to file if available."""
        if self.tasks_file:
            data = {
                "tasks": [t.to_dict() for t in self._tasks.values()],
                "nextId": self._next_id,
                "updatedAt": datetime.now().isoformat(),
            }
            self.tasks_file.write_text(json.dumps(data, indent=2))

    def create_task(
        self,
        subject: str,
        description: str,
        active_form: str = "",
    ) -> Task:
        """
        Create a new task.

        Args:
            subject: Brief title for the task (imperative form).
            description: Detailed description of what needs to be done.
            active_form: Present continuous form for progress display.

        Returns:
            The created Task.
        """
        task_id = str(self._next_id)
        self._next_id += 1

        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            status=TaskStatus.PENDING,
            active_form=active_form or f"Working on: {subject}",
        )
        self._tasks[task_id] = task
        self._save_tasks()
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """
        List all tasks, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of tasks.
        """
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: int(t.id))

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        subject: str | None = None,
        description: str | None = None,
        active_form: str | None = None,
        owner: str | None = None,
    ) -> Task | None:
        """
        Update a task.

        Args:
            task_id: ID of the task to update.
            status: New status.
            subject: New subject.
            description: New description.
            active_form: New active form.
            owner: New owner.

        Returns:
            The updated Task, or None if not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        if status is not None:
            task.status = status
        if subject is not None:
            task.subject = subject
        if description is not None:
            task.description = description
        if active_form is not None:
            task.active_form = active_form
        if owner is not None:
            task.owner = owner

        task.updated_at = datetime.now()
        self._save_tasks()
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_tasks()
            return True
        return False

    def get_active_task(self) -> Task | None:
        """Get the single task that should be in progress."""
        for task in self._tasks.values():
            if task.status == TaskStatus.IN_PROGRESS:
                return task
        return None

    def summary(self) -> str:
        """Get a summary of the task list state."""
        pending = len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING])
        in_progress = len([t for t in self._tasks.values() if t.status == TaskStatus.IN_PROGRESS])
        completed = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED])

        active = self.get_active_task()
        active_str = f"\nActive: [{active.id}] {active.subject}" if active else ""

        return f"Tasks: {pending} pending, {in_progress} in progress, {completed} completed{active_str}"


# Global task manager instance (for session-level tasks)
_task_manager: TaskManager | None = None


def get_task_manager(session_dir: Path | None = None) -> TaskManager:
    """Get or create the global task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(session_dir)
    return _task_manager


def set_task_manager(manager: TaskManager) -> None:
    """Set the global task manager."""
    global _task_manager
    _task_manager = manager


class TaskCreateTool(Tool):
    """Tool for creating a new task."""

    @property
    @override
    def name(self) -> str:
        return "task_create"

    @property
    @override
    def description(self) -> str:
        return """Create a new task in the task list.

Use this tool proactively for complex multi-step tasks (3+ distinct steps).
Always provide both content (imperative) and activeForm (present continuous).

Examples:
- content: "Fix authentication bug"
- activeForm: "Fixing authentication bug"
"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Brief title for the task (imperative form, e.g., 'Run tests').",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what needs to be done.",
                },
                "activeForm": {
                    "type": "string",
                    "description": "Present continuous form for progress display (e.g., 'Running tests').",
                },
            },
            "required": ["subject", "description"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        subject = str(kwargs.get("subject", ""))
        description = str(kwargs.get("description", ""))
        active_form = str(kwargs.get("activeForm", ""))

        manager = get_task_manager()
        task = manager.create_task(subject, description, active_form)

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"Created task [{task.id}]: {task.subject}\n{manager.summary()}",
        )


class TaskGetTool(Tool):
    """Tool for getting a specific task."""

    @property
    @override
    def name(self) -> str:
        return "task_get"

    @property
    @override
    def description(self) -> str:
        return "Get detailed information about a specific task by its ID."

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "taskId": {
                    "type": "string",
                    "description": "The ID of the task to retrieve.",
                },
            },
            "required": ["taskId"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        task_id = str(kwargs.get("taskId", ""))

        manager = get_task_manager()
        task = manager.get_task(task_id)

        if not task:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Task [{task_id}] not found.",
            )

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"Task [{task.id}]: {task.subject}\nStatus: {task.status.value}\nDescription: {task.description}\nActive form: {task.active_form}",
        )


class TaskListTool(Tool):
    """Tool for listing all tasks."""

    @property
    @override
    def name(self) -> str:
        return "task_list"

    @property
    @override
    def description(self) -> str:
        return "List all tasks in the task list with their status."

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
        manager = get_task_manager()
        tasks = manager.list_tasks()

        if not tasks:
            return ToolResult(
                call_id="",
                name=self.name,
                content="No tasks in the list.",
            )

        lines = []
        for task in tasks:
            status_icon = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.DELETED: "❌",
            }.get(task.status, "•")
            owner_str = f" (owner: {task.owner})" if task.owner else ""
            lines.append(f"{status_icon} [{task.id}] {task.subject}{owner_str}")

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"{manager.summary()}\n\n" + "\n".join(lines),
        )


class TaskUpdateTool(Tool):
    """Tool for updating a task."""

    @property
    @override
    def name(self) -> str:
        return "task_update"

    @property
    @override
    def description(self) -> str:
        return """Update a task in the task list.

Mark tasks as in_progress BEFORE starting work, and completed IMMEDIATELY after finishing.
Only ONE task should be in_progress at any time.

Status values: pending, in_progress, completed, deleted"""

    @property
    @override
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "taskId": {
                    "type": "string",
                    "description": "The ID of the task to update.",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "deleted"],
                    "description": "New status for the task.",
                },
                "subject": {
                    "type": "string",
                    "description": "New subject for the task.",
                },
                "description": {
                    "type": "string",
                    "description": "New description for the task.",
                },
                "activeForm": {
                    "type": "string",
                    "description": "New active form for progress display.",
                },
                "owner": {
                    "type": "string",
                    "description": "Assign the task to an agent by name.",
                },
            },
            "required": ["taskId"],
        }

    @override
    def execute(self, **kwargs: object) -> ToolResult:
        task_id = str(kwargs.get("taskId", ""))
        status_str = kwargs.get("status")
        subject = kwargs.get("subject")
        description = kwargs.get("description")
        active_form = kwargs.get("activeForm")
        owner = kwargs.get("owner")

        manager = get_task_manager()

        # Convert status string to enum
        status = None
        if status_str:
            try:
                status = TaskStatus(str(status_str))
            except ValueError:
                return ToolResult(
                    call_id="",
                    name=self.name,
                    content=f"Invalid status: {status_str}. Valid values: pending, in_progress, completed, deleted",
                    is_error=True,
                )

        # Handle status deletion
        if status == TaskStatus.DELETED:
            if manager.delete_task(task_id):
                return ToolResult(
                    call_id="",
                    name=self.name,
                    content=f"Deleted task [{task_id}]\n{manager.summary()}",
                )
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Task [{task_id}] not found.",
                is_error=True,
            )

        task = manager.update_task(
            task_id,
            status=status,
            subject=str(subject) if subject else None,
            description=str(description) if description else None,
            active_form=str(active_form) if active_form else None,
            owner=str(owner) if owner else None,
        )

        if not task:
            return ToolResult(
                call_id="",
                name=self.name,
                content=f"Task [{task_id}] not found.",
                is_error=True,
            )

        status_icon = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
        }.get(task.status, "•")

        return ToolResult(
            call_id="",
            name=self.name,
            content=f"{status_icon} Updated task [{task.id}]: {task.subject}\nStatus: {task.status.value}\n{manager.summary()}",
        )


def get_task_tools() -> list[Tool]:
    """Get all task management tools."""
    return [
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskUpdateTool(),
    ]


__all__ = [
    "Task",
    "TaskStatus",
    "TaskManager",
    "get_task_manager",
    "set_task_manager",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskListTool",
    "TaskUpdateTool",
    "get_task_tools",
]