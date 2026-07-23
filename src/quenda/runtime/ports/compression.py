"""
Compression policy protocol for Runtime layer.

Runtime needs to decide when to compress context. This module defines
the policy interface (port) that Runtime uses, while Host provides
implementation with specific compression strategies.

Architecture:
    Runtime (needs compression decisions)
        ↓ uses CompressionPolicy protocol
    Host (provides DefaultCompressionPolicy implementation)

Key principle: Host decides, Runtime executes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from quenda.runtime.compression import CompressionStats

from quenda.runtime.compression import CompressionDecision


class CompressionPolicy(Protocol):
    """
    Compression policy that Runtime needs.

    Runtime calls this with structured stats, and the policy
    returns a structured decision. This keeps the dependency
    direction clean: Runtime computes facts, Host evaluates.

    This is a policy (decision) protocol, not a capability protocol:
    - Policy: Decides "should we compress?" and "how?"
    - Capability: Would provide the actual compression mechanism

    Implementations:
    - Host layer: DefaultCompressionPolicy
    - User code: Custom policies based on token budget, cost, etc.
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


__all__ = ["CompressionPolicy"]