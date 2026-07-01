"""
Events for Kora Runtime observability.

Events are emitted during Run execution to allow observation
of the agent's behavior in real-time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    """
    Base class for all events.

    All events have:
    - A unique ID
    - A timestamp
    - A run_id linking to the execution context
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    run_id: str = ""


@dataclass(frozen=True)
class RunStarted(Event):
    """Emitted when a Run starts."""

    type: Literal["run_started"] = "run_started"
    agent_name: str = ""
    session_id: str = ""
    user_message: str = ""


@dataclass(frozen=True)
class RunCompleted(Event):
    """Emitted when a Run completes."""

    type: Literal["run_completed"] = "run_completed"
    agent_name: str = ""
    session_id: str = ""
    total_steps: int = 0
    final_content: str | None = None
    duration_ms: int = 0  # Total run duration in milliseconds


@dataclass(frozen=True)
class ModelCalled(Event):
    """Emitted when the model is called."""

    type: Literal["model_called"] = "model_called"
    message_count: int = 0


@dataclass(frozen=True)
class ModelResponded(Event):
    """
    Emitted when the model responds.

    Attributes:
        content: The text content of the response (if any).
        tool_calls: List of tool call IDs requested by the model.
        tool_call_details: Detailed info for each tool call (id, name, arguments).
        stop_reason: Why the model stopped generating.

    Deprecated (use tool_call_details instead):
        tool_arguments: List of argument dicts (kept for backward compatibility).
    """

    type: Literal["model_responded"] = "model_responded"
    content: str | None = None
    tool_calls: list[str] = field(default_factory=list)  # Call IDs
    tool_call_details: list[dict[str, Any]] = field(default_factory=list)  # [{id, name, arguments}]
    # Backward compatible field (deprecated, use tool_call_details)
    tool_arguments: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""


@dataclass(frozen=True)
class ToolPhaseStarted(Event):
    """
    Emitted when tool phase begins (ADR-023).

    This event captures the tool selection decision, showing:
    - What tools the model requested
    - Which were approved for execution
    - Which were rejected and why

    This enables trace to explain what the model asked for vs what
    actually happened.

    Attributes:
        requested_calls: All tool calls the model requested.
        approved_calls: Tool calls approved for execution.
        rejected_calls: Tool calls rejected with reasons.
        policy_name: Name of the ToolSelectionPolicy (if any).
    """

    type: Literal["tool_phase_started"] = "tool_phase_started"
    requested_calls: list[dict[str, Any]] = field(default_factory=list)  # [{id, name, arguments}]
    approved_calls: list[str] = field(default_factory=list)  # Call IDs
    rejected_calls: list[dict[str, Any]] = field(default_factory=list)  # [{id, name, reason}]
    policy_name: str = ""  # Policy class name


@dataclass(frozen=True)
class ToolExecuted(Event):
    """
    Emitted when a tool is executed.

    Attributes:
        tool_name: Name of the tool that was executed.
        arguments: Key parameters for the tool call.
        result: The output content (processed by ToolResultProcessingPolicy if configured).
        raw_result: The original result before processing (for trace/debug).
        is_error: Whether the execution resulted in an error.
        is_denied: Whether the tool call was denied by ToolSelectionPolicy.
        denial_reason: Reason for denial (if is_denied is True).
        duration_ms: Execution time in milliseconds (0 for denied calls).
        call_id: ID of the tool call.
        result_lines: Number of lines in the result.
        result_truncated: Whether the result was truncated by ToolResultProcessingPolicy.
        display_hint: Human-readable hint for display (e.g., "pyproject.toml").
        change_preview: Diff preview for file modification tools.
        result_summary: Summary of the result (e.g., "47 lines", "23 matches").
    """

    type: Literal["tool_executed"] = "tool_executed"
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    raw_result: str = ""  # Original result before processing
    is_error: bool = False
    is_denied: bool = False  # True if denied by ToolSelectionPolicy
    denial_reason: str = ""  # Reason for denial
    duration_ms: int = 0
    call_id: str = ""
    result_lines: int = 0
    result_truncated: bool = False
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


@dataclass(frozen=True)
class ErrorOccurred(Event):
    """Emitted when an error occurs."""

    type: Literal["error_occurred"] = "error_occurred"
    error_message: str = ""
    error_type: str = ""


@dataclass(frozen=True)
class RunInterrupted(Event):
    """Emitted when a run is interrupted by user."""

    type: Literal["run_interrupted"] = "run_interrupted"
    reason: str = "user_cancel"
    steps_completed: int = 0


@dataclass(frozen=True)
class RunTerminated(Event):
    """
    Emitted when a run is terminated by policy.

    This is distinct from RunCompleted (natural completion) and
    RunInterrupted (external stop signal). RunTerminated means
    a TerminationPolicy decided the run should stop.
    """

    type: Literal["run_terminated"] = "run_terminated"
    reason: str = ""  # Policy reason: "max_steps", "time_budget", etc.
    steps_completed: int = 0
    final_content: str | None = None
    duration_ms: int = 0


@dataclass(frozen=True)
class CompressionStarted(Event):
    """Emitted when context compression starts (ADR-015)."""

    type: Literal["compression_started"] = "compression_started"
    session_id: str = ""
    decision: Any = None  # CompressionDecision


@dataclass(frozen=True)
class CompressionCompleted(Event):
    """Emitted when context compression completes (ADR-015)."""

    type: Literal["compression_completed"] = "compression_completed"
    session_id: str = ""
    result: Any = None  # CompressionResult


# Union type for all events
AnyEvent = (
    RunStarted | RunCompleted | ModelCalled | ModelResponded |
    ToolPhaseStarted | ToolExecuted | ErrorOccurred | RunInterrupted |
    RunTerminated | CompressionStarted | CompressionCompleted
)
