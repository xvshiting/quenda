"""
Tool policies for Quenda Runtime.

This module defines policy interfaces for tool execution control.

Runtime owns the tool phase and calls these policies at concrete handoff
points:
- Tool-call approval before execution (ToolSelectionPolicy)
- Tool-result processing before messages are updated (ToolResultProcessingPolicy)

Usage (future):
    from quenda.runtime.tool_policy import (
        ToolSelectionPolicy,
        DenylistToolSelectionPolicy,
        ToolResultProcessingPolicy,
        TruncatingToolResultProcessingPolicy,
    )

    # Configure tool selection policy
    run.tool_selection_policy = DenylistToolSelectionPolicy(
        denied={"run_shell", "python_execution"},
    )

    # Configure result processing policy
    run.tool_result_processing_policy = TruncatingToolResultProcessingPolicy(
        max_chars=4000,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quenda.kernel.tool import Tool
from quenda.kernel.types import ToolCall

# ============================================================================
# ToolSelectionPolicy - Execution Approval
# ============================================================================


@dataclass(frozen=True)
class ToolSelectionRequest:
    """
    Runtime-owned input to ToolSelectionPolicy.

    Runtime produces this when the model returns tool calls,
    before any execution begins.
    """

    # The tool calls requested by the model
    tool_calls: list[ToolCall]

    # All tools available (for reference, not modification)
    available_tools: list[Tool]

    # Context
    run_id: str
    session_id: str
    agent_name: str

    # Current step info
    step_count: int
    tool_round_count: int


@dataclass(frozen=True)
class RejectedToolCall:
    """
    A rejected tool call with explanation.
    """

    call: ToolCall
    reason: str


@dataclass(frozen=True)
class ToolSelectionDecision:
    """
    Partition of approved and rejected calls.

    ToolSelectionPolicy returns this to indicate which tool calls
    should be allowed to execute.
    """

    approved: list[ToolCall]
    rejected: list[RejectedToolCall]


class ToolSelectionPolicy(Protocol):
    """
    Policy for tool execution approval/filtering.

    Runtime calls select_tools() after model returns tool calls,
    but before any tools are executed.

    This is an execution-time filter, not a model-facing routing layer.
    The model sees all available tools; this policy controls which
    calls are actually allowed to run.

    Runtime owns this handoff and applies the returned decision before
    executing any approved tool calls.
    """

    def select_tools(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        """
        Evaluate which tool calls should be allowed to execute.

        Args:
            request: The tool calls requested and context.

        Returns:
            ToolSelectionDecision with approved and rejected lists.
        """
        ...


class AllowAllToolSelectionPolicy:
    """
    Default: approve every requested tool call.

    This preserves current behavior when no policy is configured.
    """

    def select_tools(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        """Approve all tool calls."""
        return ToolSelectionDecision(
            approved=list(request.tool_calls),
            rejected=[],
        )


class DenylistToolSelectionPolicy:
    """
    Block specific tools from execution.

    Useful for security-sensitive environments where certain
    tools should never be executed.
    """

    def __init__(self, denied: set[str]) -> None:
        """
        Initialize DenylistToolSelectionPolicy.

        Args:
            denied: Set of tool names to block.
        """
        self.denied = denied

    def select_tools(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        """Block denied tools, approve others."""
        approved = []
        rejected = []
        for call in request.tool_calls:
            if call.name in self.denied:
                rejected.append(RejectedToolCall(
                    call=call,
                    reason=f"Tool '{call.name}' is in denylist",
                ))
            else:
                approved.append(call)
        return ToolSelectionDecision(approved=approved, rejected=rejected)


class AllowlistToolSelectionPolicy:
    """
    Only allow specific tools to execute.

    More restrictive than denylist - only explicitly allowed
    tools can run.
    """

    def __init__(self, allowed: set[str]) -> None:
        """
        Initialize AllowlistToolSelectionPolicy.

        Args:
            allowed: Set of tool names to allow.
        """
        self.allowed = allowed

    def select_tools(self, request: ToolSelectionRequest) -> ToolSelectionDecision:
        """Only allow listed tools."""
        approved = []
        rejected = []
        for call in request.tool_calls:
            if call.name not in self.allowed:
                rejected.append(RejectedToolCall(
                    call=call,
                    reason=f"Tool '{call.name}' is not in allowlist",
                ))
            else:
                approved.append(call)
        return ToolSelectionDecision(approved=approved, rejected=rejected)


# ============================================================================
# ToolResultProcessingPolicy - Result Shaping
# ============================================================================


@dataclass(frozen=True)
class ToolResultEnvelope:
    """
    Runtime-owned raw tool result container.

    Contains raw tool execution result that can be processed
    before feeding back to the agent loop.
    """

    # Tool identification
    call_id: str
    tool_name: str

    # Raw result (never modified by processing)
    raw_content: str

    # Metadata
    is_error: bool
    duration_ms: int
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


@dataclass(frozen=True)
class ProcessedToolResult:
    """
    Processed result to feed back into the loop.

    ToolResultProcessingPolicy transforms ToolResultEnvelope into
    this form for the agent loop.
    """

    # Processed content (may be truncated, summarized, etc.)
    content: str

    # Metadata
    is_error: bool
    display_hint: str = ""
    change_preview: str = ""
    result_summary: str = ""


class ToolResultProcessingPolicy(Protocol):
    """
    Policy for shaping tool output before it returns to the agent loop.

    Runtime calls process_result() after tool execution completes,
    but before the result is added to messages.

    The policy can modify content while raw_content is preserved
    for trace/debug purposes.

    Runtime owns this handoff and writes the processed result back to
    the model loop while preserving raw result content for trace/debug.
    """

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """
        Process a tool result.

        Args:
            result: The raw result envelope.

        Returns:
            ProcessedToolResult with potentially modified content.
        """
        ...


class PassthroughToolResultProcessingPolicy:
    """
    Default: return tool output unchanged.

    This preserves current behavior when no policy is configured.
    """

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """Return result unchanged."""
        return ProcessedToolResult(
            content=result.raw_content,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=result.result_summary,
        )


class TruncatingToolResultProcessingPolicy:
    """
    Truncate long results to a maximum character count.

    Useful for preventing context explosion from verbose tools.
    """

    def __init__(self, max_chars: int = 4000, suffix: str = "\n... [truncated]") -> None:
        """
        Initialize TruncatingToolResultProcessingPolicy.

        Args:
            max_chars: Maximum characters to keep.
            suffix: Suffix to append when truncating.
        """
        self.max_chars = max_chars
        self.suffix = suffix

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """Truncate if necessary."""
        if len(result.raw_content) <= self.max_chars:
            return ProcessedToolResult(
                content=result.raw_content,
                is_error=result.is_error,
                display_hint=result.display_hint,
                change_preview=result.change_preview,
                result_summary=result.result_summary,
            )

        truncated = result.raw_content[:self.max_chars] + self.suffix
        return ProcessedToolResult(
            content=truncated,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=f"truncated from {len(result.raw_content)} chars",
        )


class ContextSafeToolResultProcessingPolicy:
    """
    Bound verbose tool output while preserving diagnostically useful regions.

    Keeps the beginning, matching error/warning lines, and the end instead of
    blindly dropping everything after the first N characters. The untouched
    raw output remains available to tracing and persistence layers.
    """

    ERROR_MARKERS = (
        "error",
        "exception",
        "failed",
        "failure",
        "fatal",
        "traceback",
        "warning",
        "assert",
    )

    def __init__(self, max_chars: int = 16_000) -> None:
        if max_chars < 1_000:
            raise ValueError("max_chars must be at least 1000")
        self.max_chars = max_chars

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """Create a bounded model-facing view of a verbose result."""
        content = result.raw_content
        if len(content) <= self.max_chars:
            return ProcessedToolResult(
                content=content,
                is_error=result.is_error,
                display_hint=result.display_hint,
                change_preview=result.change_preview,
                result_summary=result.result_summary,
            )

        notice = (
            f"\n\n[Context view shortened from {len(content)} to "
            f"~{self.max_chars} characters; raw output is preserved in the run trace.]"
        )
        diagnostic_header = "\n\n[Relevant diagnostic lines]\n"
        tail_header = "\n\n[End of tool output]\n"
        available = max(
            1,
            self.max_chars - len(notice) - len(diagnostic_header) - len(tail_header),
        )
        head_size = int(available * 0.35)
        error_size = int(available * 0.20)
        tail_size = available - head_size - error_size

        diagnostic_lines = [
            line
            for line in content.splitlines()
            if any(marker in line.lower() for marker in self.ERROR_MARKERS)
        ]
        diagnostics = "\n".join(diagnostic_lines)
        if len(diagnostics) > error_size:
            suffix = "\n... [diagnostics shortened]"
            diagnostics = diagnostics[:max(0, error_size - len(suffix))] + suffix
        diagnostics = (diagnostics or "(none detected)")[:error_size]

        sections = [
            content[:head_size],
            diagnostic_header + diagnostics,
            tail_header + content[-tail_size:],
            notice,
        ]
        return ProcessedToolResult(
            content="".join(sections),
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=f"context view shortened from {len(content)} chars",
        )


class LineLimitedToolResultProcessingPolicy:
    """
    Limit number of lines in result.

    Alternative to character-based truncation, useful for
    structured output like logs or file listings.
    """

    def __init__(self, max_lines: int = 100, suffix: str = "\n... [more lines truncated]") -> None:
        """
        Initialize LineLimitedToolResultProcessingPolicy.

        Args:
            max_lines: Maximum lines to keep.
            suffix: Suffix to append when truncating.
        """
        self.max_lines = max_lines
        self.suffix = suffix

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """Limit lines if necessary."""
        lines = result.raw_content.split("\n")
        if len(lines) <= self.max_lines:
            return ProcessedToolResult(
                content=result.raw_content,
                is_error=result.is_error,
                display_hint=result.display_hint,
                change_preview=result.change_preview,
                result_summary=result.result_summary,
            )

        truncated = "\n".join(lines[:self.max_lines]) + self.suffix
        return ProcessedToolResult(
            content=truncated,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=f"limited from {len(lines)} lines",
        )


class CompositeToolResultProcessingPolicy:
    """
    Chain multiple processing policies.

    Policies are applied in order, allowing composition of
    different processing strategies.
    """

    def __init__(self, policies: list[ToolResultProcessingPolicy]) -> None:
        """
        Initialize CompositeToolResultProcessingPolicy.

        Args:
            policies: Policies to chain in order.
        """
        self.policies = policies

    def process_result(self, result: ToolResultEnvelope) -> ProcessedToolResult:
        """Apply all policies in sequence."""
        # Start with raw result
        current = ProcessedToolResult(
            content=result.raw_content,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=result.result_summary,
        )

        # Apply each policy
        for policy in self.policies:
            # Create envelope from current processed result
            envelope = ToolResultEnvelope(
                call_id=result.call_id,
                tool_name=result.tool_name,
                raw_content=current.content,  # Use processed content
                is_error=current.is_error,
                duration_ms=result.duration_ms,
                display_hint=current.display_hint,
                change_preview=current.change_preview,
                result_summary=current.result_summary,
            )
            current = policy.process_result(envelope)

        return current


__all__ = [
    # ToolSelectionPolicy
    "ToolSelectionRequest",
    "RejectedToolCall",
    "ToolSelectionDecision",
    "ToolSelectionPolicy",
    "AllowAllToolSelectionPolicy",
    "DenylistToolSelectionPolicy",
    "AllowlistToolSelectionPolicy",
    # ToolResultProcessingPolicy
    "ToolResultEnvelope",
    "ProcessedToolResult",
    "ToolResultProcessingPolicy",
    "PassthroughToolResultProcessingPolicy",
    "TruncatingToolResultProcessingPolicy",
    "ContextSafeToolResultProcessingPolicy",
    "LineLimitedToolResultProcessingPolicy",
    "CompositeToolResultProcessingPolicy",
]
