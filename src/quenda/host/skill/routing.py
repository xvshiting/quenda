"""
Host-side routing helpers for model-requested skill activation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from quenda.runtime.events import ModelResponded

if TYPE_CHECKING:
    from collections.abc import Callable
    from quenda.runtime.events import AnyEvent


@dataclass(frozen=True)
class SkillActivationResolution:
    """Resolved host decision for one batch of skill activation requests."""

    requested: list[str]
    activated: list[str]
    unavailable: list[str]
    already_active: list[str]
    followup_message: str | None


def extract_skill_activation_requests(events: list[AnyEvent]) -> list[dict]:
    """Extract request_skill_activation tool payloads from runtime events."""
    requests: list[dict] = []
    for event in events:
        if isinstance(event, ModelResponded):
            for detail in event.tool_call_details:
                if detail.get("name") == "request_skill_activation":
                    requests.append(detail.get("arguments", {}))
    return requests


def build_skill_activation_followup(
    requested: list[str],
    activated: list[str],
    unavailable: list[str],
    already_active: list[str],
    original_user_message: str,
) -> str:
    """Build the synthetic continuation message after skill activation."""
    lines = [
        "[Host continuation: do not acknowledge this note. "
        "Resume the task directly and provide the user-facing answer only.]",
    ]

    if activated:
        lines.append(f"Activated skills: {', '.join(activated)}.")
    if already_active:
        lines.append(f"Already active: {', '.join(already_active)}.")
    if unavailable:
        lines.append(f"Unavailable skills: {', '.join(unavailable)}.")

    requested_text = ", ".join(requested) if requested else "the requested skills"
    lines.append(f"Use {requested_text} where relevant.")
    lines.append(
        "Do not call `request_skill_activation` again for the same skill unless you need a different one."
    )
    lines.append(f"Original user request: {original_user_message}")
    return " ".join(lines)


def resolve_skill_activation_requests(
    requests: list[dict],
    *,
    available_skill_names: set[str],
    active_skill_names: set[str],
    activate: Callable[[list[str]], list[str]],
    original_user_message: str,
) -> SkillActivationResolution:
    """
    Resolve model-requested skill activations through Host state.

    Returns a structured resolution including a follow-up message when the
    request produced an actionable continuation.
    """
    requested: list[str] = []
    already_active: list[str] = []
    unavailable: list[str] = []
    to_activate: list[str] = []

    for payload in requests:
        skill_name = str(payload.get("skill_name", "")).strip()
        if not skill_name or skill_name in requested:
            continue
        requested.append(skill_name)

        if skill_name in active_skill_names:
            already_active.append(skill_name)
        elif skill_name in available_skill_names:
            to_activate.append(skill_name)
        else:
            unavailable.append(skill_name)

    activated = activate(to_activate) if to_activate else []
    followup_message = None
    if requested:
        followup_message = build_skill_activation_followup(
            requested=requested,
            activated=activated,
            unavailable=unavailable,
            already_active=already_active,
            original_user_message=original_user_message,
        )

    return SkillActivationResolution(
        requested=requested,
        activated=activated,
        unavailable=unavailable,
        already_active=already_active,
        followup_message=followup_message,
    )


__all__ = [
    "SkillActivationResolution",
    "extract_skill_activation_requests",
    "build_skill_activation_followup",
    "resolve_skill_activation_requests",
]
