"""Agent Home backed business logic for the Web UI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from quenda.host import AgentHome, AgentHomeManager
from quenda.host.loader import ModelsConfig
from quenda.web.models.agent import AgentConfig, AgentSummary, AgentTemplate


class AgentService:
    """Expose the same named Agent Homes used by the CLI."""

    def __init__(
        self,
        agents_dir: Path | None = None,
        *,
        manager: AgentHomeManager | None = None,
    ) -> None:
        # ``agents_dir`` remains as a compatibility injection point for callers
        # of the prototype service; it now means the Quenda Home root.
        self.manager = manager or AgentHomeManager(agents_dir)

    async def list_agents(self) -> list[AgentSummary]:
        return [self._summary(home) for home in self.manager.list()]

    async def get_agent(self, agent_id: str) -> AgentConfig | None:
        try:
            home = self.manager.get(agent_id)
        except ValueError:
            return None
        return self._load_package(agent_id, home.path) if home else None

    async def create_agent(self, request: Any) -> AgentConfig:
        source = getattr(request, "source", None)
        home = self.manager.create(request.name, source=source)
        if request.description or request.system_prompt:
            self._update_agent_md(
                home.path / "AGENT.md",
                description=request.description,
                body=request.system_prompt,
            )
        if request.config_yaml is not None:
            self._validate_config(request.config_yaml)
            (home.path / "config.yaml").write_text(request.config_yaml, encoding="utf-8")
        loaded = self._load_package(home.name, home.path)
        assert loaded is not None
        return loaded

    async def update_agent(self, agent_id: str, request: Any) -> AgentConfig | None:
        try:
            home = self.manager.get(agent_id)
        except ValueError:
            return None
        if home is None:
            return None
        if request.name is not None and request.name != agent_id:
            raise ValueError("Renaming an Agent Home is not supported; create a new named agent")
        if request.description is not None or request.system_prompt is not None:
            self._update_agent_md(
                home.path / "AGENT.md",
                description=request.description,
                body=request.system_prompt,
            )
        if request.config_yaml is not None:
            self._validate_config(request.config_yaml)
            (home.path / "config.yaml").write_text(request.config_yaml, encoding="utf-8")
        return self._load_package(agent_id, home.path)

    async def delete_agent(self, agent_id: str) -> bool:
        try:
            home = self.manager.get(agent_id)
        except ValueError:
            return False
        if home is None:
            return False
        # The validated manager lookup guarantees an exact agent-<name> child.
        import shutil

        shutil.rmtree(home.path)
        return True

    async def get_templates(self) -> list[AgentTemplate]:
        return [
            AgentTemplate(
                id="blank",
                name="Blank personal agent",
                description="An editable Agent Home with identity, memory, skills, and workspace",
                category="general",
                config={},
            ),
            AgentTemplate(
                id="quenda-code",
                name="Quenda Code",
                description="Seed a personal coding agent from the installed Quenda Code package",
                category="coding",
                config={"source": "quenda-code"},
            ),
        ]

    def _summary(self, home: AgentHome) -> AgentSummary:
        config = self._load_package(home.name, home.path)
        assert config is not None
        return AgentSummary(
            id=config.id,
            name=config.name,
            description=config.description,
            created_at=config.created_at,
            updated_at=config.updated_at,
            model=config.model,
            provider=config.provider,
            tool_count=len(config.tools),
            home_path=config.home_path,
            workspace_path=config.workspace_path,
            created_from=config.created_from,
        )

    @staticmethod
    def _load_package(agent_id: str, path: Path) -> AgentConfig | None:
        agent_md = path / "AGENT.md"
        if not agent_md.is_file():
            return None
        content = agent_md.read_text(encoding="utf-8")
        metadata: dict[str, Any] = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) == 3:
                parsed_metadata = yaml.safe_load(parts[1]) or {}
                metadata = parsed_metadata if isinstance(parsed_metadata, dict) else {}
                body = parts[2].strip()
        config_file = path / "config.yaml"
        config_yaml = config_file.read_text(encoding="utf-8") if config_file.is_file() else None
        parsed_config = yaml.safe_load(config_yaml) if config_yaml else {}
        config_data = parsed_config if isinstance(parsed_config, dict) else {}
        default_model = ModelsConfig.from_dict(config_data.get("models") or {}).default
        tool_config = config_data.get("tools") or {}
        tools = list(tool_config.get("include") or [])
        stat = agent_md.stat()
        return AgentConfig(
            id=agent_id,
            name=str(metadata.get("name", agent_id)),
            description=metadata.get("description"),
            system_prompt=body,
            tools=tools,
            model=(default_model.model if default_model else None)
            or metadata.get("model"),
            provider=(default_model.provider if default_model else None)
            or metadata.get("provider"),
            home_path=str(path),
            workspace_path=str(path / "workspace") if (path / "agent.yaml").is_file() else None,
            created_from=AgentService._load_created_from(path / "agent.yaml"),
            config_yaml=config_yaml,
            created_at=datetime.fromtimestamp(stat.st_ctime, UTC),
            updated_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            metadata=metadata,
        )

    @staticmethod
    def _update_agent_md(path: Path, *, description: str | None, body: str | None) -> None:
        content = path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) != 3:
            raise ValueError("AGENT.md must contain valid YAML frontmatter")
        metadata = yaml.safe_load(parts[1]) or {}
        if description is not None:
            metadata["description"] = description
        next_body = body if body is not None else parts[2].strip()
        rendered = yaml.safe_dump(metadata, sort_keys=False).strip()
        path.write_text(f"---\n{rendered}\n---\n\n{next_body}\n", encoding="utf-8")

    @staticmethod
    def _validate_config(content: str) -> None:
        parsed = yaml.safe_load(content)
        if parsed is not None and not isinstance(parsed, dict):
            raise ValueError("config_yaml must contain a YAML mapping")

    @staticmethod
    def _load_created_from(path: Path) -> str | None:
        """Read optional provenance without making the whole Agent list fragile."""
        if not path.is_file():
            return None
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(metadata, dict):
            return None
        created_from = metadata.get("created_from")
        return str(created_from) if created_from is not None else None
