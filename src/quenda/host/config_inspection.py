"""Credential-free explanation of effective Agent configuration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

from quenda.host.loader import AgentConfigYaml, ModelRoleConfig, load_agent_package
from quenda.host.validation import validate_agent_package

CONFIG_INSPECTION_SCHEMA_VERSION = "quenda.agent-config-inspection/v1"
InspectionSection = Literal[
    "summary",
    "models",
    "providers",
    "tools",
    "skills",
    "execution",
    "evolution",
    "all",
]
INSPECTION_SECTIONS = frozenset(
    {
        "summary",
        "models",
        "providers",
        "tools",
        "skills",
        "execution",
        "evolution",
        "all",
    }
)


class AgentConfigInspector:
    """Describe one Agent config through normalized, secret-free data."""

    def __init__(
        self,
        agent_path: Path | str,
        *,
        workspace_path: Path | str | None = None,
    ) -> None:
        path = Path(agent_path).expanduser().resolve()
        self.agent_path = path.parent if path.is_file() else path
        self.workspace_path = (
            Path(workspace_path).expanduser().resolve()
            if workspace_path is not None
            else self.agent_path
        )

    def inspect(self, section: InspectionSection = "summary") -> dict[str, Any]:
        """Return one normalized explanation section or the complete view."""
        if section not in INSPECTION_SECTIONS:
            raise ValueError(
                f"Unknown section {section!r}; expected one of {sorted(INSPECTION_SECTIONS)}"
            )

        config_path = self.agent_path / "config.yaml"
        raw = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
        report = validate_agent_package(
            self.agent_path,
            workspace_path=self.workspace_path,
        )
        result: dict[str, Any] = {
            "schema_version": CONFIG_INSPECTION_SCHEMA_VERSION,
            "agent": {
                "name": report.agent_name,
                "path": str(self.agent_path),
                "config_path": str(config_path),
            },
            "revision": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
            "valid": report.valid,
            "validation": report.to_dict(),
        }
        if not report.valid:
            return result

        package = load_agent_package(self.agent_path)
        config = package.config or AgentConfigYaml()
        sections = self._sections(config)
        if section == "all":
            result.update(sections)
        elif section == "summary":
            result["summary"] = self._summary(config)
        else:
            result[section] = sections[section]
        result["supported"] = self._supported(section)
        return result

    def _sections(self, config: AgentConfigYaml) -> dict[str, Any]:
        return {
            "models": {
                "default": _model_role(config.models.default),
                "vision": _model_role(config.models.vision),
                "routing": {
                    "capability_routing": config.models.capability_routing,
                    "missing_capability": config.models.missing_capability,
                },
            },
            "providers": [
                {
                    "id": provider.id,
                    "type": provider.kind,
                    "name": provider.name,
                    "endpoint": _safe_endpoint(provider.base_url),
                    "api": provider.api,
                    "credential_configured": provider.api_key is not None,
                    "header_names": sorted(provider.headers),
                    "models": [
                        {
                            "id": model.id,
                            "name": model.name,
                            "context_window": model.context_window,
                            "max_output_tokens": model.max_output_tokens,
                            "reasoning": model.reasoning,
                            "tool_calling": model.tool_calling,
                            "streaming": model.streaming,
                            "vision": model.vision,
                        }
                        for model in provider.models
                    ],
                }
                for provider in config.providers
            ],
            "tools": {
                "bundles": list(config.tools.bundles),
                "include": list(config.tools.include),
                "mcp_servers": [
                    {
                        "id": server_id,
                        "transport": server.transport,
                    }
                    for server_id, server in sorted(
                        config.mcp.servers.items() if config.mcp else ()
                    )
                ],
            },
            "skills": {
                "activate": list(config.skills),
                "include_catalog": config.include_skill_catalog,
            },
            "execution": {
                "backend": config.execution.backend,
                "requires_isolation": config.execution.requires_isolation,
            },
            "evolution": {
                "enabled": config.evolution.enabled,
                "write_mode": config.evolution.write_mode,
                "every_n_user_turns": config.evolution.every_n_user_turns,
                "on_explicit_signal": config.evolution.on_explicit_signal,
                "min_confidence": config.evolution.min_confidence,
                "max_proposals": config.evolution.max_proposals,
            },
        }

    @staticmethod
    def _summary(config: AgentConfigYaml) -> dict[str, Any]:
        return {
            "default_model": _model_role(config.models.default),
            "vision_model": _model_role(config.models.vision),
            "declared_provider_ids": [provider.id for provider in config.providers],
            "tool_bundles": list(config.tools.bundles),
            "active_skills": list(config.skills),
            "execution_backend": config.execution.backend,
            "memory_evolution_enabled": config.evolution.enabled,
        }

    @staticmethod
    def _supported(section: InspectionSection) -> dict[str, Any]:
        # Lazy import avoids making Host package initialization depend on the
        # capability manifest's provider and lifecycle registries.
        from quenda.capabilities import build_framework_capability_manifest

        configuration = cast(
            dict[str, Any],
            build_framework_capability_manifest()["configuration"],
        )
        if section == "models":
            return {
                "model_roles": configuration["model_roles"],
                "model_reference_forms": configuration["model_reference_forms"],
            }
        if section == "providers":
            return {"providers": configuration["providers"]}
        if section == "skills":
            return {"skills": configuration["skills"]}
        if section == "execution":
            return {"execution": configuration["execution"]}
        if section == "evolution":
            return {"memory_evolution": configuration["memory_evolution"]}
        if section == "tools":
            return {
                "framework_tools": build_framework_capability_manifest()["registries"]
                ["framework_tools"]
            }
        return configuration


def _model_role(role: ModelRoleConfig | None) -> dict[str, str] | None:
    if role is None:
        return None
    return {"provider": role.provider, "model": role.model}


def _safe_endpoint(value: str | None) -> str | None:
    """Keep endpoint routing information while removing credentials and query data."""
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return None
        hostname = parsed.hostname
        if ":" in hostname:
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except ValueError:
        return None


__all__ = [
    "CONFIG_INSPECTION_SCHEMA_VERSION",
    "INSPECTION_SECTIONS",
    "AgentConfigInspector",
    "InspectionSection",
]
