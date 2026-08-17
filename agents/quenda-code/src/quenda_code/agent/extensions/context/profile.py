"""Quenda Code's profile and always-on memory context adapter."""

from __future__ import annotations

from pathlib import Path

from quenda.host.extensions import ContextProviderRequest
from quenda.host.instructions import (
    InstructionScope,
    InstructionSource,
    resolve_identity_files,
)


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
        identity_files = resolve_identity_files(context.agent_package_path)
        candidates = [
            *[
                _optional_source(
                    path,
                    scope=InstructionScope.AGENT_INSTRUCTIONS,
                    prefix=(
                        "<agent_identity>\n"
                        if path.name == "IDENTITY.md"
                        else "<agent_soul>\n"
                    ),
                    suffix=(
                        "\n</agent_identity>"
                        if path.name == "IDENTITY.md"
                        else "\n</agent_soul>"
                    ),
                )
                for path in identity_files
            ],
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
