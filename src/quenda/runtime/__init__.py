"""
Quenda Runtime Layer.

The runtime manages Agent, Workspace, Session, Prompt, and Run semantics.
It coordinates Kernel execution but does not handle persistence.

This layer is async - it wraps the sync Kernel with real-time event streaming.
"""

from quenda.runtime.agent import Agent, AgentConfig, AgentDefinition
from quenda.runtime.events import (
    AnyEvent,
    ErrorOccurred,
    Event,
    ModelCalled,
    ModelResponded,
    RunCompleted,
    RunStarted,
    RunTerminated,
    ToolExecuted,
)
from quenda.runtime.run import Run, RunStatus, SkillActivationHandler
from quenda.runtime.session import Session, SessionState
from quenda.runtime.termination import (
    CompositeTerminationPolicy,
    ConsecutiveErrorPolicy,
    MaxStepsPolicy,
    NeverTerminatePolicy,
    TerminationDecision,
    TerminationPolicy,
    TerminationState,
    TimeBudgetPolicy,
    TokenBudgetPolicy,
)
from quenda.runtime.tool_policy import (
    AllowAllToolSelectionPolicy,
    AllowlistToolSelectionPolicy,
    DenylistToolSelectionPolicy,
    LineLimitedToolResultProcessingPolicy,
    PassthroughToolResultProcessingPolicy,
    ProcessedToolResult,
    RejectedToolCall,
    ToolResultEnvelope,
    ToolResultProcessingPolicy,
    ToolSelectionDecision,
    ToolSelectionPolicy,
    ToolSelectionRequest,
    TruncatingToolResultProcessingPolicy,
)
from quenda.runtime.trace import JsonlTraceSink, NullTraceSink, TraceSink

__all__ = [
    # Agent
    "Agent",
    "AgentConfig",
    "AgentDefinition",
    # Session
    "Session",
    "SessionState",
    # Run
    "Run",
    "RunStatus",
    "SkillActivationHandler",
    # Events
    "AnyEvent",
    "ErrorOccurred",
    "Event",
    "ModelCalled",
    "ModelResponded",
    "RunCompleted",
    "RunStarted",
    "RunTerminated",
    "ToolExecuted",
    # Trace
    "TraceSink",
    "NullTraceSink",
    "JsonlTraceSink",
    # Termination
    "TerminationState",
    "TerminationDecision",
    "TerminationPolicy",
    "NeverTerminatePolicy",
    "MaxStepsPolicy",
    "TimeBudgetPolicy",
    "TokenBudgetPolicy",
    "ConsecutiveErrorPolicy",
    "CompositeTerminationPolicy",
    # Tool Policy (target contracts)
    "ToolSelectionRequest",
    "RejectedToolCall",
    "ToolSelectionDecision",
    "ToolSelectionPolicy",
    "AllowAllToolSelectionPolicy",
    "DenylistToolSelectionPolicy",
    "AllowlistToolSelectionPolicy",
    "ToolResultEnvelope",
    "ProcessedToolResult",
    "ToolResultProcessingPolicy",
    "PassthroughToolResultProcessingPolicy",
    "TruncatingToolResultProcessingPolicy",
    "LineLimitedToolResultProcessingPolicy",
]
