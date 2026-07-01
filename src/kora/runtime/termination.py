"""
TerminationPolicy for Kora Runtime.

This module defines the termination policy interface for Runtime-level
execution control. TerminationPolicy decides whether a run should stop
based on runtime state.

Key principle: Kernel retains hard safety guards (max_iterations).
TerminationPolicy enables user-controlled stopping rules at Runtime level.

Usage:
    from kora.runtime.termination import (
        TerminationPolicy,
        MaxStepsPolicy,
        CompositeTerminationPolicy,
    )

    # Create a policy
    policy = MaxStepsPolicy(max_steps=20)

    # Or combine multiple policies
    policy = CompositeTerminationPolicy([
        MaxStepsPolicy(max_steps=20),
        TokenBudgetPolicy(max_total_tokens=100000),
    ])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TerminationState:
    """
    Runtime-owned snapshot passed into TerminationPolicy.

    Runtime produces this after each step completes, representing
    current execution state for policy evaluation.
    """

    # Execution progress
    step_count: int
    tool_round_count: int  # Number of model->tool->model cycles
    elapsed_time_ms: int

    # Token usage (cumulative for this session)
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int

    # Error tracking
    error_count: int
    consecutive_error_count: int

    # Context for policy decisions
    run_id: str
    session_id: str
    agent_name: str

    # Last step info (optional)
    last_step_type: str | None = None  # "model" or "tool"
    last_stop_reason: str | None = None  # Model stop reason


@dataclass(frozen=True)
class TerminationDecision:
    """
    Output from TerminationPolicy.

    Policy returns this to indicate whether execution should continue.
    """

    should_stop: bool
    reason: str = ""  # "max_steps", "time_budget", "token_budget", etc.


class TerminationPolicy(Protocol):
    """
    Runtime stopping policy.

    Runtime calls should_terminate() after each completed step to decide
    whether execution should continue.

    This is a Runtime strategy seam, not a Kernel execution guard.
    Kernel retains hard safety guards (max_iterations) that prevent
    runaway execution even when no policy is configured.

    The policy decides the transition: LoopDecision -> Terminated
    """

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """
        Evaluate whether execution should stop.

        Args:
            state: Current execution state from Runtime.

        Returns:
            TerminationDecision with should_stop flag and reason.
        """
        ...


class NeverTerminatePolicy:
    """
    Default: never stop early.

    This policy lets the agent run to natural completion.
    It preserves the current behavior when no termination policy is configured.
    """

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Never terminate early."""
        return TerminationDecision(should_stop=False)


class MaxStepsPolicy:
    """
    Stop after a maximum number of steps.

    A step is one observable unit (model step or tool step).
    This is a user-controlled limit, distinct from Kernel's max_iterations
    which is a hard safety guard.
    """

    def __init__(self, max_steps: int) -> None:
        """
        Initialize MaxStepsPolicy.

        Args:
            max_steps: Maximum number of steps allowed.
        """
        self.max_steps = max_steps

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Check if step limit reached."""
        if state.step_count >= self.max_steps:
            return TerminationDecision(
                should_stop=True,
                reason=f"max_steps ({self.max_steps})",
            )
        return TerminationDecision(should_stop=False)


class TimeBudgetPolicy:
    """
    Stop after a time budget is exceeded.

    Time budget is measured in milliseconds from run start.
    """

    def __init__(self, max_time_ms: int) -> None:
        """
        Initialize TimeBudgetPolicy.

        Args:
            max_time_ms: Maximum execution time in milliseconds.
        """
        self.max_time_ms = max_time_ms

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Check if time budget exceeded."""
        if state.elapsed_time_ms >= self.max_time_ms:
            return TerminationDecision(
                should_stop=True,
                reason=f"time_budget ({self.max_time_ms}ms)",
            )
        return TerminationDecision(should_stop=False)


class TokenBudgetPolicy:
    """
    Stop after a token budget is exceeded.

    Token budget is the sum of input and output tokens.
    """

    def __init__(self, max_total_tokens: int) -> None:
        """
        Initialize TokenBudgetPolicy.

        Args:
            max_total_tokens: Maximum total tokens (input + output).
        """
        self.max_total_tokens = max_total_tokens

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Check if token budget exceeded."""
        if state.total_tokens >= self.max_total_tokens:
            return TerminationDecision(
                should_stop=True,
                reason=f"token_budget ({self.max_total_tokens})",
            )
        return TerminationDecision(should_stop=False)


class ConsecutiveErrorPolicy:
    """
    Stop after consecutive errors.

    This policy is useful for detecting stuck or failing agents.
    """

    def __init__(self, max_consecutive_errors: int = 3) -> None:
        """
        Initialize ConsecutiveErrorPolicy.

        Args:
            max_consecutive_errors: Maximum number of consecutive errors allowed.
        """
        self.max_consecutive_errors = max_consecutive_errors

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Check if too many consecutive errors."""
        if state.consecutive_error_count >= self.max_consecutive_errors:
            return TerminationDecision(
                should_stop=True,
                reason=f"consecutive_errors ({self.max_consecutive_errors})",
            )
        return TerminationDecision(should_stop=False)


class CompositeTerminationPolicy:
    """
    Combine multiple policies with OR semantics.

    The first policy that returns should_stop=True wins.
    This allows combining different stopping conditions.
    """

    def __init__(self, policies: list[TerminationPolicy]) -> None:
        """
        Initialize CompositeTerminationPolicy.

        Args:
            policies: List of policies to evaluate in order.
        """
        self.policies = policies

    def should_terminate(self, state: TerminationState) -> TerminationDecision:
        """Evaluate all policies, stop if any returns True."""
        for policy in self.policies:
            decision = policy.should_terminate(state)
            if decision.should_stop:
                return decision
        return TerminationDecision(should_stop=False)


__all__ = [
    "TerminationState",
    "TerminationDecision",
    "TerminationPolicy",
    "NeverTerminatePolicy",
    "MaxStepsPolicy",
    "TimeBudgetPolicy",
    "TokenBudgetPolicy",
    "ConsecutiveErrorPolicy",
    "CompositeTerminationPolicy",
]
