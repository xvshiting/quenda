"""Initialize Quenda Code's private user profile and memory files."""

from __future__ import annotations

from pathlib import Path

from quenda.host.extensions import AgentExtensionContext


USER_TEMPLATE = """# User Profile

This file contains preferences you explicitly want Quenda Code to follow.
Edit it at any time; changes are loaded on the next Run.

## Communication

- Preferred language:
- Preferred response style:

## Engineering Preferences

- Languages and frameworks:
- Code style:
- Testing preferences:

## Workflow Preferences

- Git and publishing preferences:
- Actions that require confirmation:
"""


MEMORY_TEMPLATE = """# Core Memory

This file contains concise, stable, cross-project context curated for your
private conversations with Quenda Code.

Keep this file short. Detailed notes and dated logs belong in `memory/` and are
loaded only through `memory_search` and `memory_get`.
"""


def _create_once(path: Path, content: str) -> None:
    """Create a UTF-8 text file atomically without replacing existing content."""
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        pass


class QuendaCodeProfileInitializer:
    """Create optional profile and memory scaffolding on first setup."""

    def initialize(self, context: AgentExtensionContext) -> None:
        root = context.user_agent_path
        root.mkdir(parents=True, exist_ok=True)
        (root / "memory").mkdir(exist_ok=True)
        _create_once(root / "USER.md", USER_TEMPLATE)
        _create_once(root / "MEMORY.md", MEMORY_TEMPLATE)


initializers = [QuendaCodeProfileInitializer()]

