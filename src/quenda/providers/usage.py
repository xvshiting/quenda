"""Normalize provider token usage into one accounting contract.

``UsageStats.input_tokens`` is total logical input, including cache reads and
cache writes. ``cached_input_tokens`` is the subset served from an existing
cache. Callers therefore never need provider-specific addition rules.
"""

from __future__ import annotations

from typing import Any

from quenda.kernel.types import UsageStats


def normalize_openai_usage(usage: Any) -> UsageStats:
    """Translate OpenAI Chat/compatible usage; cached tokens are a subset."""
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    cached = _first_int(
        getattr(prompt_details, "cached_tokens", None),
        getattr(usage, "cached_input_tokens", None),
        getattr(usage, "prompt_cache_hit_tokens", None),
        getattr(usage, "cache_read_input_tokens", None),
    )
    return UsageStats(
        input_tokens=_nonnegative_int(getattr(usage, "prompt_tokens", 0)),
        output_tokens=_nonnegative_int(getattr(usage, "completion_tokens", 0)),
        cached_input_tokens=cached,
        cache_creation_input_tokens=None,
        reasoning_tokens=_optional_nonnegative_int(
            getattr(completion_details, "reasoning_tokens", None)
        ),
    )


def normalize_anthropic_usage(usage: Any) -> UsageStats:
    """Translate Anthropic usage, whose three input counters are disjoint."""
    uncached = _nonnegative_int(getattr(usage, "input_tokens", 0))
    cache_read = _optional_nonnegative_int(
        getattr(usage, "cache_read_input_tokens", None)
    )
    cache_creation = _optional_nonnegative_int(
        getattr(usage, "cache_creation_input_tokens", None)
    )
    return UsageStats(
        input_tokens=uncached + (cache_read or 0) + (cache_creation or 0),
        output_tokens=_nonnegative_int(getattr(usage, "output_tokens", 0)),
        cached_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
        reasoning_tokens=None,
    )


def _first_int(*values: object) -> int | None:
    for value in values:
        normalized = _optional_nonnegative_int(value)
        if normalized is not None:
            return normalized
    return None


def _optional_nonnegative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _nonnegative_int(value: object) -> int:
    return _optional_nonnegative_int(value) or 0


__all__ = ["normalize_anthropic_usage", "normalize_openai_usage"]
