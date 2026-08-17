"""Machine-readable description of Quenda's public capability seams.

The manifest is intentionally safe to print, cache, and pass to an Agent.  It
describes supported contracts and registered public identifiers, never runtime
credentials, request headers, or environment values.
"""

from __future__ import annotations

from typing import Any

from quenda import __version__
from quenda.host.skill.package import EXECUTABLE_DIRECTORIES, RESOURCE_DIRECTORIES
from quenda.providers.api import build_default_api_registry
from quenda.providers.registry import build_default_provider_registry
from quenda.runtime.lifecycle import (
    LIFECYCLE_SCHEMA_VERSION,
    LifecycleStage,
    build_default_lifecycle_registry,
)

SCHEMA_VERSION = "quenda.capabilities/v1"


def build_framework_capability_manifest() -> dict[str, Any]:
    """Return Quenda's deterministic, credential-free capability manifest."""
    api_registry = build_default_api_registry()
    provider_registry = build_default_provider_registry(api_registry=api_registry)
    lifecycle_registry = build_default_lifecycle_registry()
    lifecycle_extensions = lifecycle_registry.to_manifest()

    providers: list[dict[str, Any]] = []
    for provider_id in sorted(provider_registry.list_providers()):
        spec = provider_registry.get_spec(provider_id)
        if spec is None:  # Defensive: registry IDs and specs should be atomic.
            continue
        providers.append(
            {
                "id": spec.id,
                "name": spec.name,
                "api": spec.api,
                "models": [
                    {
                        "id": model.id,
                        "name": model.name,
                        "reasoning": model.reasoning,
                        "tool_calling": model.tool_calling,
                        "streaming": model.streaming,
                        "vision": model.vision,
                        "context_window": model.context_window,
                        "max_output_tokens": model.max_output_tokens,
                    }
                    for model in sorted(spec.models, key=lambda item: item.id)
                ],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "framework": {
            "name": "quenda",
            "version": __version__,
        },
        "interfaces": {
            "cli": {
                "capabilities": "quenda capabilities --json",
                "agent_validate": "quenda agent validate <target> --json",
                "run": "quenda run",
                "named_agent": "quenda <agent-name>",
            },
            "web": {
                "capabilities": "/api/system/capabilities",
            },
        },
        "configuration": {
            "agent_file": "config.yaml",
            "model_roles": ["default", "vision"],
            "model_reference_forms": [
                "provider/model",
                {"provider": "provider-id", "model": "model-id"},
            ],
            "providers": {
                "container": "providers",
                "types": ["builtin", "custom", "llama-server"],
                "credential_sources": ["environment", "config"],
                "custom_required_fields": ["url-or-base_url", "models"],
            },
            "skills": {
                "entrypoint": "SKILL.md",
                "recursive_discovery": True,
                "package_boundary": "directory-containing-SKILL.md",
                "resource_directories": sorted(RESOURCE_DIRECTORIES),
                "executable_directories": sorted(EXECUTABLE_DIRECTORIES),
                "roots_in_priority_order": [
                    "user-workspace",
                    "workspace/.quenda/skills",
                    "workspace/.agents/skills",
                    "agent-package/skills",
                    "user/.agents/skills",
                    "${QUENDA_HOME:-~/.quenda}/skills",
                ],
            },
            "agent_extensions": [
                "extensions/commands/*.py",
                "extensions/interactions/*.py",
                "extensions/tools/*.py",
                "extensions/context/*.py",
                "extensions/setup/*.py",
                "extensions/policies/*.py",
                "extensions/providers/*.py",
            ],
            "validation": {
                "schema_version": "quenda.agent-validation/v1",
                "executes_extensions": False,
                "resolves_credentials": False,
                "contacts_providers": False,
            },
            "execution": {
                "default_backend": "local-trusted",
                "requirement_field": "execution.requires_isolation",
                "backends": [
                    {
                        "id": "local-trusted",
                        "available": True,
                        "isolated": False,
                        "trusted_only": True,
                    }
                ],
            },
            "memory_evolution": {
                "journal_schema": "quenda.memory-journal/v1",
                "targets": ["core_memory", "user_profile", "identity", "soul"],
                "write_modes": ["automatic", "review", "disabled"],
                "default_write_mode": "automatic",
                "trigger": {
                    "stage": "after_run",
                    "default_every_n_user_turns": 5,
                    "explicit_signal_shortcut": True,
                    "isolated_model_call": True,
                },
                "optimistic_concurrency": True,
                "revision_storage": "content-addressed",
                "identity_documents": ["IDENTITY.md", "SOUL.md"],
            },
            "skill_evolution": {
                "journal_schema": "quenda.skill-journal/v1",
                "workflow": ["stage", "validate", "commit", "rollback"],
                "validation": "quarantined-static",
                "executes_candidate_code": False,
                "approval": "skill_evolution.write",
                "optimistic_concurrency": True,
                "revision_storage": "content-addressed",
                "activation": "explicit-epoch",
            },
        },
        "registries": {
            "provider_apis": sorted(api_registry.list()),
            "providers": providers,
            "framework_tools": [
                {
                    "id": "apply_agent_config_patch",
                    "availability": "agent-setup",
                    "mutates": True,
                    "approval": "agent_config.write",
                    "patch_format": "rfc7396",
                    "optimistic_concurrency": True,
                },
                {
                    "id": "explain_agent_config",
                    "availability": "agent-setup",
                    "mutates": False,
                    "schema_version": "quenda.agent-config-inspection/v1",
                    "credential_free": True,
                },
                {
                    "id": "validate_agent_package",
                    "availability": "agent-setup",
                    "mutates": False,
                },
                {
                    "id": "inspect_skill_evolution",
                    "availability": "agent-setup",
                    "mutates": False,
                    "candidate_content": "omitted",
                },
                {
                    "id": "apply_skill_evolution",
                    "availability": "agent-setup",
                    "mutates": True,
                    "approval": "skill_evolution.write",
                    "optimistic_concurrency": True,
                    "activation": "explicit-epoch",
                },
            ],
        },
        "lifecycle": {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "stages": [stage.value for stage in LifecycleStage],
            "extension_points": lifecycle_extensions,
        },
        "extension_points": [
            {
                "id": "provider-api",
                "contract": "quenda.providers.Api",
                "registration": "ApiRegistry.register",
            },
            {
                "id": "provider-catalog",
                "contract": "quenda.providers.ProviderSpec",
                "registration": "ProviderRegistry.register",
            },
            {
                "id": "tool",
                "contract": "quenda.kernel.Tool",
                "registration": "ToolRegistryBuilder.register",
            },
            *lifecycle_extensions,
        ],
    }


__all__ = ["SCHEMA_VERSION", "build_framework_capability_manifest"]
