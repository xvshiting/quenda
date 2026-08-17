"""Agent package validation through one public Host interface."""

from __future__ import annotations

import json
from pathlib import Path

from quenda.cli import main
from quenda.host.validation import validate_agent_package
from quenda.tools.agent_validation import ValidateAgentPackageTool


def _write_agent(path: Path, *, config: str = "") -> Path:
    path.mkdir(parents=True)
    (path / "AGENT.md").write_text(
        "---\nname: validator-fixture\n---\nValidate this package.\n",
        encoding="utf-8",
    )
    if config:
        (path / "config.yaml").write_text(config, encoding="utf-8")
    return path


def test_validates_declarative_provider_models_and_nested_skills(tmp_path: Path) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="""
providers:
  local:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    models:
      - id: local-model
        name: Local Model
models:
  default:
    provider: local
    model: local-model
skills:
  activate:
    - review-local
""",
    )
    skill = agent / "skills" / "review" / "local" / "review-local"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: review-local\ndescription: Review local code.\n---\nReview it.\n",
        encoding="utf-8",
    )

    report = validate_agent_package(agent, workspace_path=tmp_path)

    assert report.valid
    assert report.agent_name == "validator-fixture"
    assert report.error_count == 0
    assert report.to_dict()["schema_version"] == "quenda.agent-validation/v1"


def test_reports_all_static_reference_errors_without_exposing_secrets(tmp_path: Path) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="""
providers:
  hosted:
    type: custom
    url: https://example.invalid/v1
    api_key: super-secret-value
    api: missing-protocol
    models:
      - id: remote-model
        name: Remote Model
models:
  default:
    provider: hosted
    model: missing-model
  vision:
    provider: hosted
    model: remote-model
instructions:
  include:
    - instructions/missing.md
skills:
  activate:
    - missing-skill
tools:
  bundles:
    - missing-bundle
  include:
    - missing-tool
""",
    )
    extension = agent / "extensions" / "tools"
    extension.mkdir(parents=True)
    (extension / "broken.py").write_text("def invalid(:\n", encoding="utf-8")

    report = validate_agent_package(agent, workspace_path=tmp_path)
    serialized = json.dumps(report.to_dict())
    codes = {diagnostic.code for diagnostic in report.diagnostics}

    assert not report.valid
    assert {
        "extension.syntax",
        "instruction.missing",
        "model.not_found",
        "provider_api.unknown",
        "skill.not_found",
        "tool_bundle.unknown",
        "tool.deferred_extension",
        "vision.unsupported",
    } <= codes
    assert "super-secret-value" not in serialized


def test_rejects_false_local_isolation_claim(tmp_path: Path) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="""
execution:
  backend: local-trusted
  requires_isolation: true
""",
    )

    report = validate_agent_package(agent)

    assert report.valid is False
    assert {item.code for item in report.diagnostics} >= {
        "execution.isolation_unavailable"
    }


def test_rejects_invalid_evolution_policy_values(tmp_path: Path) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="""
evolution:
  enabled: true
  write_mode: unsafe
  every_n_user_turns: 0
  min_confidence: 1.5
  max_proposals: 0
""",
    )

    report = validate_agent_package(agent)
    codes = {item.code for item in report.diagnostics}

    assert {
        "evolution.write_mode_invalid",
        "evolution.every_n_user_turns_invalid",
        "evolution.min_confidence_invalid",
        "evolution.max_proposals_invalid",
    } <= codes


def test_cli_outputs_json_and_nonzero_for_invalid_package(
    tmp_path: Path, capsys
) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="models:\n  default:\n    provider: absent\n    model: absent\n",
    )

    assert main(["agent", "validate", str(agent), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["valid"] is False
    assert payload["counts"]["errors"] >= 1


def test_malformed_yaml_does_not_echo_source_line_secrets(tmp_path: Path) -> None:
    agent = _write_agent(
        tmp_path / "agent",
        config="providers:\n  hosted:\n    api_key: secret-on-bad-line\n   invalid: value\n",
    )

    serialized = json.dumps(validate_agent_package(agent).to_dict())

    assert "secret-on-bad-line" not in serialized
    assert "config.yaml is invalid" in serialized


def test_validation_tool_defaults_to_current_agent_package(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = _write_agent(tmp_path / "agent")
    tool = ValidateAgentPackageTool(
        workspace=workspace,
        agent_package_path=agent,
    )

    result = tool.execute()
    payload = json.loads(result.content)

    assert not result.is_error
    assert payload["valid"] is True
    assert payload["agent"]["path"] == str(agent.resolve())


def test_validation_tool_rejects_arbitrary_outside_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = _write_agent(tmp_path / "agent")
    outside = _write_agent(tmp_path / "outside")
    tool = ValidateAgentPackageTool(
        workspace=workspace,
        agent_package_path=agent,
    )

    result = tool.execute(path=str(outside))

    assert result.is_error
    assert "current workspace or Agent package" in result.content
