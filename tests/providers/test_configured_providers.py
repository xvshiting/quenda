"""Behavior tests for config-driven provider and model catalogs."""

from pathlib import Path

from quenda.host.loader import AgentConfigYaml
from quenda.host.runner import setup_host_binding
from quenda.providers import build_default_provider_registry
from quenda.runtime.permission import DenyPermissionPolicy


def test_agent_config_parses_multiple_custom_providers_and_model_roles() -> None:
    """An Agent can describe several providers and select text/vision roles."""
    config = AgentConfigYaml.from_dict(
        {
            "providers": {
                "local-llama": {
                    "type": "llama-server",
                    "url": "http://127.0.0.1:8080/v1",
                    "models": [
                        {
                            "id": "Qwen3.5-9B-Q4_K_M.gguf",
                            "name": "Local Qwen 3.5 9B",
                            "context_window": 32768,
                        }
                    ],
                },
                "private-cloud": {
                    "type": "custom",
                    "url": "https://models.example.test/v1",
                    "api": "openai",
                    "key": "configured-secret",
                    "models": [
                        {
                            "id": "vision-1",
                            "name": "Private Vision",
                            "vision": True,
                        }
                    ],
                },
            },
            "models": {
                "default": "local-llama/Qwen3.5-9B-Q4_K_M.gguf",
                "vision": "private-cloud/vision-1",
            },
        }
    )

    assert [provider.id for provider in config.providers] == [
        "local-llama",
        "private-cloud",
    ]
    assert config.providers[0].kind == "llama-server"
    assert config.providers[0].base_url == "http://127.0.0.1:8080/v1"
    assert config.providers[0].models[0].id == "Qwen3.5-9B-Q4_K_M.gguf"
    assert config.providers[0].models[0].context_window == 32768
    assert config.providers[1].api == "openai-completions"
    assert config.providers[1].api_key == "configured-secret"
    assert "configured-secret" not in repr(config.providers[1])
    assert config.providers[1].models[0].vision is True
    assert config.models.default is not None
    assert config.models.default.provider == "local-llama"
    assert config.models.default.model == "Qwen3.5-9B-Q4_K_M.gguf"
    assert config.models.vision is not None
    assert config.models.vision.provider == "private-cloud"
    assert config.models.vision.model == "vision-1"


def test_agent_binding_registers_yaml_providers_and_resolves_model_roles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Configured providers participate in normal default and vision binding."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_dir = tmp_path / "agent"
    workspace = tmp_path / "project"
    agent_dir.mkdir()
    workspace.mkdir()
    (agent_dir / "AGENT.md").write_text(
        "---\nname: configured-agent\n---\nConfigured agent.\n",
        encoding="utf-8",
    )
    (agent_dir / "config.yaml").write_text(
        """
providers:
  local-llama:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    models:
      - id: "qwen3.5:9b"
        name: Local Qwen 3.5 9B
        context_window: 32768
  private-cloud:
    type: custom
    url: https://models.example.test/v1
    api: openai
    key: configured-secret
    models:
      - id: vision-1
        name: Private Vision
        vision: true
models:
  default: "local-llama/qwen3.5:9b"
  vision: "private-cloud/vision-1"
""",
        encoding="utf-8",
    )

    registry = build_default_provider_registry()
    binding = setup_host_binding(
        agent_dir,
        workspace,
        provider_registry=registry,
        tools=[],
    )

    assert binding is not None
    assert binding.provider_name == "local-llama"
    assert binding.model_name == "qwen3.5:9b"
    assert binding.model_instance.provider.resolve_base_url(
        binding.model_instance.spec
    ) == "http://127.0.0.1:8080/v1"
    assert binding.model_instance.provider.resolve_api(
        binding.model_instance.spec
    ) == "openai-completions"
    assert binding.model_instance.provider.resolve_api_key() == "no-key"
    assert binding.vision_model_instance is not None
    assert binding.vision_model_instance.provider.id == "private-cloud"
    assert binding.vision_model_instance.provider.resolve_api_key() == "configured-secret"


def test_agent_home_config_is_readable_and_writable_without_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The Host-owned Agent Home remains manageable from an external project."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent_home = tmp_path / "agent-home"
    workspace = tmp_path / "project"
    agent_home.mkdir()
    workspace.mkdir()
    (agent_home / "agent.yaml").write_text("version: 1\n", encoding="utf-8")
    (agent_home / "AGENT.md").write_text(
        "---\nname: configured-agent\n---\nConfigured agent.\n",
        encoding="utf-8",
    )
    config_text = "model:\n  provider: jdcloud\n  name: GLM-5\n"
    config_path = agent_home / "config.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    unrelated_path = tmp_path / "unrelated.txt"
    unrelated_path.write_text("private", encoding="utf-8")
    permissions = DenyPermissionPolicy()

    binding = setup_host_binding(
        agent_home,
        workspace,
        provider_registry=build_default_provider_registry(),
        permission_policy=permissions,
    )

    assert binding is not None
    read_file = next(tool for tool in binding.tools if tool.name == "read_file")
    write_file = next(tool for tool in binding.tools if tool.name == "write_file")
    read_result = read_file.execute(path=str(config_path))
    write_result = write_file.execute(path=str(config_path), content=config_text)
    blocked_result = read_file.execute(path=str(unrelated_path))
    assert not read_result.is_error, read_result.content
    assert not write_result.is_error, write_result.content
    assert blocked_result.is_error
    assert "permission requests are disabled" in blocked_result.content


def test_agent_config_can_supply_or_reference_a_builtin_provider_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A provider override can keep the builtin catalog and replace its credential."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_JDCLOUD_KEY", "environment-secret")
    agent_dir = tmp_path / "agent"
    workspace = tmp_path / "project"
    agent_dir.mkdir()
    workspace.mkdir()
    (agent_dir / "AGENT.md").write_text(
        "---\nname: configured-agent\n---\nConfigured agent.\n",
        encoding="utf-8",
    )
    (agent_dir / "config.yaml").write_text(
        """
providers:
  jdcloud:
    api_key: "${AGENT_JDCLOUD_KEY}"
models:
  default: jdcloud/GLM-5
""",
        encoding="utf-8",
    )

    binding = setup_host_binding(
        agent_dir,
        workspace,
        provider_registry=build_default_provider_registry(),
        tools=[],
    )

    assert binding is not None
    assert binding.model_instance.provider.resolve_api_key() == "environment-secret"
    assert binding.model_instance.provider.spec.metadata["configured_by"] == "agent-config"
