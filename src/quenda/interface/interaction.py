"""
Interaction rendering helpers for Quenda Interface.

These helpers turn structured interaction requests into readable
terminal output. They stay intentionally thin so different interfaces
can reuse the same Host-side interaction protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quenda.host.interactions import InteractionContext, InteractionOption, InteractionRegistry, InteractionRequest

if TYPE_CHECKING:
    from quenda.host.interactions import Interaction


def render_interaction_request(
    request: InteractionRequest,
    registry: InteractionRegistry | None = None,
    context: InteractionContext | None = None,
) -> str:
    """
    Render an interaction request as terminal-friendly text.

    If a registry is provided, the registered interaction kind can
    normalize or validate the options before rendering.
    """
    options = list(request.options)
    errors: list[str] = []

    if registry is not None and context is not None:
        errors = registry.validate(request, context)
        options = registry.get_suggestions(request, context)

    lines: list[str] = []
    lines.append(f"\n{request.title}")

    if request.message:
        lines.append(request.message)

    if request.kind:
        lines.append(f"Type: {request.kind}")

    if errors:
        lines.append("")
        for error in errors:
            lines.append(f"⚠ {error}")

    if options:
        lines.append("")
        for index, option in enumerate(options, 1):
            default_marker = " (default)" if _is_default_option(request, option) else ""
            description = f" - {option.description}" if option.description else ""
            lines.append(f"  {index}. {option.label}{default_marker}{description}")
    else:
        lines.append("")
        lines.append("  (no options)")

    return "\n".join(lines)


def _is_default_option(request: InteractionRequest, option: InteractionOption) -> bool:
    if request.default_option_id is not None:
        return option.id == request.default_option_id
    return option.is_default


__all__ = [
    "render_interaction_request",
]
