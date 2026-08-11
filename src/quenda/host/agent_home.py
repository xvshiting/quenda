"""Local Agent Home creation and discovery.

An Agent Home is the user-facing unit of a locally managed agent.  Its
definition, private instructions, memory, sessions, and default workspace all
live below ``~/.quenda/agent-<name>/`` (or an injected root in tests/server
adapters).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from quenda.host.loader import find_builtin_agent

_AGENT_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
_SCAFFOLD_DIRS = (
    "instructions",
    "skills",
    "memory",
    "sessions",
    "artifacts",
    "workspace",
)
_RUNTIME_STATE_NAMES = frozenset({"agent.yaml", "artifacts", "memory", "sessions", "workspace"})
_CopyIgnore = Callable[[str, list[str]], set[str]]


@dataclass(frozen=True)
class AgentHome:
    """A discovered local Agent Home."""

    name: str
    path: Path
    created_from: str | None = None

    @property
    def workspace(self) -> Path:
        """Return this agent's default workspace."""
        return self.path / "workspace"


class AgentHomeManager:
    """Create, discover, and resolve local Agent Homes."""

    def __init__(self, root: Path | None = None) -> None:
        configured_root = Path(os.environ["QUENDA_HOME"]) if "QUENDA_HOME" in os.environ else None
        self.root = (root or configured_root or Path.home() / ".quenda").expanduser()

    def home_path(self, name: str) -> Path:
        """Return the conventional home path for a validated agent name."""
        self._validate_name(name)
        return self.root / f"agent-{name}"

    def create(self, name: str, *, source: str | Path | None = None) -> AgentHome:
        """Create an independent Agent Home, optionally seeded from a source."""
        target = self.home_path(name)
        if target.exists():
            raise FileExistsError(f'Agent "{name}" already exists at {target}')

        resolved_source = self._resolve_source(source) if source is not None else None
        self.root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".agent-{name}-", dir=self.root))
        try:
            if resolved_source is not None:
                shutil.copytree(
                    resolved_source,
                    staging,
                    dirs_exist_ok=True,
                    ignore=self._source_ignore(resolved_source),
                )

            self._ensure_scaffold(staging, name)
            source_label = str(source) if source is not None else None
            self._write_metadata(staging, name, source_label)
            staging.replace(target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return AgentHome(name=name, path=target, created_from=source_label)

    def get(self, name: str) -> AgentHome | None:
        """Return one valid Agent Home by name."""
        path = self.home_path(name)
        if not (path.is_dir() and (path / "AGENT.md").is_file()):
            return None
        metadata = self._read_metadata(path)
        return AgentHome(
            name=name,
            path=path,
            created_from=metadata.get("created_from"),
        )

    def list(self) -> list[AgentHome]:
        """Discover valid Agent Homes from the filesystem."""
        if not self.root.is_dir():
            return []
        homes: list[AgentHome] = []
        for path in sorted(self.root.glob("agent-*")):
            if not path.is_dir() or not (path / "AGENT.md").is_file():
                continue
            name = path.name.removeprefix("agent-")
            if not _AGENT_NAME.fullmatch(name):
                continue
            metadata = self._read_metadata(path)
            homes.append(AgentHome(name, path, metadata.get("created_from")))
        return homes

    def _resolve_source(self, source: str | Path) -> Path:
        raw = str(source)
        candidate = Path(raw).expanduser()
        if candidate.exists():
            resolved = candidate.resolve()
            if resolved.is_file() and resolved.name == "AGENT.md":
                resolved = resolved.parent
            if not resolved.is_dir() or not (resolved / "AGENT.md").is_file():
                raise ValueError(f"Agent source must contain AGENT.md: {source}")
            return resolved

        builtin = find_builtin_agent(raw)
        if builtin is not None:
            return builtin.resolve()
        raise FileNotFoundError(f"Agent source not found: {source}")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not _AGENT_NAME.fullmatch(name):
            raise ValueError(
                "Agent name must contain only letters, numbers, '-' or '_', "
                "and must start with a letter or number"
            )

    @staticmethod
    def _source_ignore(source_root: Path) -> _CopyIgnore:
        """Return a copy filter that excludes Agent Home runtime state."""

        def ignore(directory: str, names: list[str]) -> set[str]:
            ignored = {name for name in names if name in {".DS_Store", "__pycache__"}}
            if Path(directory).resolve() == source_root:
                ignored.update(name for name in names if name in _RUNTIME_STATE_NAMES)
            return ignored

        return ignore

    @staticmethod
    def _ensure_scaffold(path: Path, name: str) -> None:
        for relative in _SCAFFOLD_DIRS:
            (path / relative).mkdir(parents=True, exist_ok=True)

        agent_md = path / "AGENT.md"
        if agent_md.exists():
            content = agent_md.read_text(encoding="utf-8")
            content = AgentHomeManager._with_agent_name(content, name)
            agent_md.write_text(content, encoding="utf-8")
        else:
            agent_md.write_text(
                f"""---
name: {name}
version: 0.1.0
description: Personal Quenda agent
---

You are {name}, my personal AI agent.

Learn how to help through our conversations and the instructions, skills, and
memory stored in your Agent Home.
""",
                encoding="utf-8",
            )

        defaults = {
            "SOUL.md": "# Soul\n\nDescribe this agent's personality and values here.\n",
            "USER.md": "# User\n\nRecord stable user preferences here.\n",
            "MEMORY.md": "# Memory\n\nStore concise, durable memories here.\n",
            "config.yaml": "tools:\n  bundles:\n    - core\n\nskills:\n  include_catalog: true\n",
        }
        for filename, content in defaults.items():
            destination = path / filename
            if not destination.exists():
                destination.write_text(content, encoding="utf-8")

    @staticmethod
    def _with_agent_name(content: str, name: str) -> str:
        """Return AGENT.md content with a canonical frontmatter name."""
        if not content.startswith("---"):
            return f"---\nname: {name}\n---\n\n{content}"

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Source AGENT.md has unclosed frontmatter")
        frontmatter = parts[1].strip()
        if re.search(r"(?m)^name:\s*.*$", frontmatter):
            frontmatter = re.sub(
                r"(?m)^name:\s*.*$",
                f"name: {name}",
                frontmatter,
                count=1,
            )
        else:
            frontmatter = f"name: {name}\n{frontmatter}" if frontmatter else f"name: {name}"
        body = parts[2].lstrip("\n")
        return f"---\n{frontmatter}\n---\n\n{body}"

    @staticmethod
    def _write_metadata(path: Path, name: str, source: str | None) -> None:
        data: dict[str, object] = {
            "schema_version": 1,
            "name": name,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if source is not None:
            data["created_from"] = source
        (path / "agent.yaml").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_metadata(path: Path) -> dict[str, str]:
        metadata_path = path / "agent.yaml"
        if not metadata_path.is_file():
            return {}
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items() if value is not None}


__all__ = ["AgentHome", "AgentHomeManager"]
