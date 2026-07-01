"""
Compression policy for Kora Host layer.

This module defines the compression policy interface that Host provides
to Runtime for deciding when and how to compress context.

Key principle: Host decides, Runtime executes.
"""

from __future__ import annotations

from typing import Protocol

from quenda.runtime.compression import CompressionDecision, CompressionStats


class CompressionPolicy(Protocol):
    """
    Host-provided compression policy interface.

    Runtime calls this with structured stats, and the policy
    returns a structured decision. This keeps the dependency
    direction clean: Runtime computes facts, Host evaluates.
    """

    def should_compress(self, stats: CompressionStats) -> CompressionDecision:
        """
        Decide whether to compress based on runtime statistics.

        Args:
            stats: Runtime-computed compression statistics.

        Returns:
            A structured decision indicating whether to compress
            and with what parameters.
        """
        ...


class DefaultCompressionPolicy:
    """
    Default compression policy implementation.

    Triggers compression when estimated input tokens exceed
    a threshold ratio of the context window.
    """

    def __init__(
        self,
        threshold_ratio: float = 0.8,
        keep_last_n_messages: int = 10,
        archive_raw_messages: bool = True,
    ) -> None:
        """
        Initialize the default compression policy.

        Args:
            threshold_ratio: Trigger compression when tokens exceed
                this ratio of context_window (default 0.8 = 80%).
            keep_last_n_messages: Number of recent messages to keep
                uncompressed (default 10).
            archive_raw_messages: Whether to archive raw messages
                before compression (default True).
        """
        self.threshold_ratio = threshold_ratio
        self.keep_last_n_messages = keep_last_n_messages
        self.archive_raw_messages = archive_raw_messages

    def should_compress(self, stats: CompressionStats) -> CompressionDecision:
        """
        Evaluate whether compression is needed.

        Args:
            stats: Runtime-computed compression statistics.

        Returns:
            CompressionDecision with compress=True if threshold exceeded.
        """
        # Cannot decide without context window info
        if not stats.context_window:
            return CompressionDecision(
                compress=False,
                keep_last_n_messages=0,
                target_budget_tokens=None,
                archive_raw_messages=False,
                summarizer_id=None,
                reason="context_window unknown",
            )

        # Calculate threshold
        threshold = int(stats.context_window * self.threshold_ratio)
        should_compress = stats.estimated_input_tokens > threshold

        if should_compress:
            return CompressionDecision(
                compress=True,
                keep_last_n_messages=self.keep_last_n_messages,
                target_budget_tokens=threshold,
                archive_raw_messages=self.archive_raw_messages,
                summarizer_id="default",
                reason=f"tokens {stats.estimated_input_tokens} > threshold {threshold}",
            )
        else:
            return CompressionDecision(
                compress=False,
                keep_last_n_messages=self.keep_last_n_messages,
                target_budget_tokens=None,
                archive_raw_messages=False,
                summarizer_id=None,
                reason=f"tokens {stats.estimated_input_tokens} <= threshold {threshold}",
            )


__all__ = [
    "CompressionPolicy",
    "DefaultCompressionPolicy",
]
