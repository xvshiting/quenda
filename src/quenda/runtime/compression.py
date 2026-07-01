"""
Compression protocol interfaces for Quenda.

This module defines the data structures for communication between
Runtime and Host layers during context compression, as defined in ADR-015.

Key principle: Host decides, Runtime executes, Kernel is unaware.

Flow:
1. Runtime computes CompressionStats from current state
2. Runtime calls CompressionPolicy.should_compress(stats)
3. Host policy returns CompressionDecision
4. Runtime invokes Compressor.compress() if needed
5. Runtime applies CompressionResult to SessionState
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.kernel.types import Message
    from quenda.runtime.session import SessionState, SessionUsage


@dataclass
class CompressionStats:
    """
    Per-turn compression policy input.

    Runtime produces this after assembling the effective message list
    for the upcoming model call. Host policy evaluates these stats
    to decide whether compression is needed.
    """

    estimated_input_tokens: int
    message_count: int
    context_window: int | None
    reserved_output_tokens: int | None
    summary_token_count: int
    hot_message_count: int
    session_id: str
    agent_name: str
    mode: str
    cumulative_usage: SessionUsage


@dataclass
class CompressionDecision:
    """
    Host policy output.

    The compression policy returns this structured decision,
    which Runtime then executes via Compressor.
    """

    compress: bool
    keep_last_n_messages: int
    target_budget_tokens: int | None
    archive_raw_messages: bool
    summarizer_id: str | None
    reason: str


@dataclass
class CompressionResult:
    """
    Result of a compression operation.

    Compressor.compress() returns this, and Runtime applies it
    to the in-memory SessionState.
    """

    summary_messages: list[Message]
    archived_message_count: int
    archive_refs: list[str]
    summary_token_count: int


__all__ = [
    "CompressionStats",
    "CompressionDecision",
    "CompressionResult",
]
