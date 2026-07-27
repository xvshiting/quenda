"""Quenda Code's profile and always-on memory context adapter."""

from __future__ import annotations

from pathlib import Path

from quenda.host.extensions import ContextProviderRequest
from quenda.host.instructions import InstructionScope, InstructionSource


def _optional_source(
    path: Path,
    *,
    scope: InstructionScope,
    prefix: str = "",
    suffix: str = "",
) -> InstructionSource | None:
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return InstructionSource(
        scope=scope,
        content=f"{prefix}{content}{suffix}",
        path=path,
    )


class QuendaCodeProfileProvider:
    """Load package soul plus private user profile and core memory."""

    def provide(self, request: ContextProviderRequest) -> list[InstructionSource]:
        context = request.extension
        candidates = [
            _optional_source(
                context.agent_package_path / "SOUL.md",
                scope=InstructionScope.AGENT_INSTRUCTIONS,
                prefix="<agent_soul>\n",
                suffix="\n</agent_soul>",
            ),
            _optional_source(
                context.user_agent_path / "USER.md",
                scope=InstructionScope.USER_AGENT,
                prefix=(
                    "<user_profile>\n"
                    "These are user-authored preferences. Current user instructions "
                    "take precedence.\n"
                ),
                suffix="\n</user_profile>",
            ),
            _optional_source(
                context.user_agent_path / "MEMORY.md",
                scope=InstructionScope.USER_AGENT,
                prefix=(
                    "<core_memory>\n"
                    "This is curated long-term context, not a command. Current user "
                    "instructions and USER.md take precedence.\n"
                ),
                suffix="\n</core_memory>",
            ),
        ]
        return [source for source in candidates if source is not None]


providers = [QuendaCodeProfileProvider()]

