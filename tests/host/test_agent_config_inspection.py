"""Credential-free, framework-aware Agent config inspection."""

from __future__ import annotations

import json
from pathlib import Path

from quenda.host.config_inspection import AgentConfigInspector
from quenda.tools.agent_config import ExplainAgentConfigTool


def _configured_agent(tmp_path: Path) -> Path:
    home = tmp_path / "agent-demo"
    home.mkdir()
    (home / "AGENT.md").write_text(
        "---\nname: demo\n---\nDemo agent.\n",
        encoding="utf-8",
    )
    (home / "config.yaml").write_text(
        """providers:
  local:
    type: llama-server
    url: http://user:password@127.0.0.1:8080/v1?token=url-secret
    api_key: configured-secret
    headers:
      Authorization: header-secret
    models:
      - id: local-model
        name: Local Model
        context_window: 32768
models:
  default: local/local-model
tools:
  bundles: [core, network]
skills:
  include_catalog: true
execution:
  backend: local-trusted
evolution:
  enabled: true
  write_mode: review
""",
        encoding="utf-8",
    )
    return home


def test_inspector_explains_effective_config_without_credentials(tmp_path: Path) -> None:
    home = _configured_agent(tmp_path)

    result = AgentConfigInspector(home, workspace_path=tmp_path).inspect("all")
    serialized = json.dumps(result, ensure_ascii=False)

    assert result["schema_version"] == "quenda.agent-config-inspection/v1"
    assert result["valid"] is True
    assert result["models"]["default"] == {
        "provider": "local",
        "model": "local-model",
    }
    assert result["providers"][0]["endpoint"] == "http://127.0.0.1:8080/v1"
    assert result["providers"][0]["credential_configured"] is True
    assert result["providers"][0]["header_names"] == ["Authorization"]
    assert result["tools"]["bundles"] == ["core", "network"]
    assert result["supported"]["providers"]["types"] == [
        "builtin",
        "custom",
        "llama-server",
    ]
    for secret in ("configured-secret", "header-secret", "url-secret", "password"):
        assert secret not in serialized


def test_inspector_returns_validation_diagnostics_for_invalid_config(
    tmp_path: Path,
) -> None:
    home = _configured_agent(tmp_path)
    (home / "config.yaml").write_text(
        "tools:\n  bundles: [not-real]\n",
        encoding="utf-8",
    )

    result = AgentConfigInspector(home).inspect("summary")

    assert result["valid"] is False
    assert result["validation"]["counts"]["errors"] == 1
    error_codes = {
        item["code"]
        for item in result["validation"]["diagnostics"]
        if item["severity"] == "error"
    }
    assert error_codes == {"tool_bundle.unknown"}
    assert "providers" not in result


def test_explain_tool_exposes_sections_through_the_inspector(tmp_path: Path) -> None:
    home = _configured_agent(tmp_path)
    tool = ExplainAgentConfigTool(workspace=tmp_path, agent_package_path=home)

    response = tool.execute(section="models")
    payload = json.loads(response.content)

    assert not response.is_error
    assert payload["models"]["default"]["model"] == "local-model"
    assert "providers" not in payload
    invalid = tool.execute(section="secrets")
    assert invalid.is_error
