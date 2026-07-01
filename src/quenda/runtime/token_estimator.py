"""
Token estimation for Kora Runtime.

Provides simple token counting estimation for compression decisions.
Estimated tokens are used before model invocation to decide compression.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.kernel.types import Message


class TokenEstimator:
    """
    Simple token estimation for compression decisions.

    Uses character-based approximation: ~4 characters per token for English.
    This is a rough estimate, not authoritative billing data.

    For more accurate counting, consider integrating tiktoken later.
    """

    # Approximate characters per token ratio
    # English: ~4 chars/token, Chinese: ~2 chars/token
    # Using conservative estimate of 3 chars/token
    CHAR_PER_TOKEN_RATIO = 3.0

    def estimate_text(self, text: str) -> int:
        """
        Estimate token count for a text string.

        Args:
            text: The text to estimate.

        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        # Add overhead for message formatting
        return int(len(text) / self.CHAR_PER_TOKEN_RATIO) + 4

    def estimate_messages(self, messages: list[Message]) -> int:
        """
        Estimate total token count for a message list.

        This includes content plus overhead for role labels and formatting.

        Args:
            messages: The messages to estimate.

        Returns:
            Estimated total token count.
        """
        total = 0

        for msg in messages:
            # Role overhead (e.g., "user: ", "assistant: ", "system: ")
            total += 4

            # Content estimation
            if isinstance(msg.content, str):
                total += self.estimate_text(msg.content)
            else:
                # Tool calls / results - estimate from serialized form
                for item in msg.content:
                    if hasattr(item, "name"):
                        total += self.estimate_text(str(item.name))
                    if hasattr(item, "content"):
                        total += self.estimate_text(str(item.content))
                    if hasattr(item, "arguments"):
                        total += self.estimate_text(str(item.arguments))
                    # Add tool call overhead
                    total += 10

        # Add message list overhead
        total += 3

        return max(total, 0)


__all__ = ["TokenEstimator"]