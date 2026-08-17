"""Framework capability manifest contract."""

from __future__ import annotations

import json

from quenda.capabilities import build_framework_capability_manifest
from quenda.cli import main


def test_manifest_is_versioned_deterministic_and_secret_free() -> None:
    first = build_framework_capability_manifest()
    second = build_framework_capability_manifest()

    assert first == second
    assert first["schema_version"] == "quenda.capabilities/v1"
    assert first["framework"]["name"] == "quenda"
    assert first["configuration"]["providers"]["types"] == [
        "builtin",
        "custom",
        "llama-server",
    ]
    assert first["configuration"]["skills"]["recursive_discovery"] is True
    assert first["configuration"]["execution"]["default_backend"] == "local-trusted"
    assert first["configuration"]["execution"]["backends"][0]["isolated"] is False
    assert first["configuration"]["memory_evolution"] == {
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
    }
    assert first["configuration"]["skill_evolution"] == {
        "journal_schema": "quenda.skill-journal/v1",
        "workflow": ["stage", "validate", "commit", "rollback"],
        "validation": "quarantined-static",
        "executes_candidate_code": False,
        "approval": "skill_evolution.write",
        "optimistic_concurrency": True,
        "revision_storage": "content-addressed",
        "activation": "explicit-epoch",
    }
    assert "openai-completions" in first["registries"]["provider_apis"]
    assert first["registries"]["framework_tools"] == [
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
    ]
    assert any(
        point["id"] == "tool-result-processing-policy" for point in first["extension_points"]
    )
    assert first["lifecycle"]["schema_version"] == "quenda.lifecycle/v1"
    lifecycle_ids = {point["id"] for point in first["lifecycle"]["extension_points"]}
    assert {"prompt-assembler", "evolution-policy"} <= lifecycle_ids
    evolution = next(
        point
        for point in first["lifecycle"]["extension_points"]
        if point["id"] == "evolution-policy"
    )
    assert evolution["status"] == "active"

    serialized = json.dumps(first).lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized


def test_capabilities_cli_prints_pipeable_json(capsys) -> None:
    assert main(["capabilities", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "quenda.capabilities/v1"
    assert payload["interfaces"]["cli"]["capabilities"] == "quenda capabilities --json"


def test_capabilities_cli_can_select_one_section(capsys) -> None:
    assert main(["capabilities", "--json", "--section", "configuration"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == ["configuration"]


def test_capabilities_cli_can_select_lifecycle_catalog(capsys) -> None:
    assert main(["capabilities", "--json", "--section", "lifecycle"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["lifecycle"]["schema_version"] == "quenda.lifecycle/v1"
