"""
Tests for agent capability declaration in config.yaml.

Tests the MVP for agents requesting tools and execution capabilities.
"""

import pytest
from pathlib import Path

from quenda.host.loader import (
    AgentConfigYaml,
    PoliciesConfig,
    PolicySpecConfig,
    ToolsConfig,
    ExecutionConfig,
    PythonExecutionConfig,
    load_agent_policies,
    load_agent_package,
)
from quenda.host.policy_registry import PolicyRegistryBuilder
from quenda.host.runner import (
    _resolve_policy_bindings,
    _resolve_tools,
    _resolve_sandbox_config,
)


class TestToolsConfig:
    """Tests for ToolsConfig parsing."""

    def test_empty_tools_config(self) -> None:
        """Test empty tools config."""
        config = ToolsConfig.from_dict({})
        assert config.bundles == []
        assert config.include == []

    def test_bundles_parsing(self) -> None:
        """Test parsing bundles list."""
        config = ToolsConfig.from_dict({
            "bundles": ["core", "network"],
        })
        assert config.bundles == ["core", "network"]
        assert config.include == []

    def test_include_parsing(self) -> None:
        """Test parsing include list."""
        config = ToolsConfig.from_dict({
            "include": ["http_request", "web_fetch"],
        })
        assert config.bundles == []
        assert config.include == ["http_request", "web_fetch"]

class TestExecutionConfig:
    """Tests for ExecutionConfig parsing."""

    def test_empty_execution_config(self) -> None:
        """Test empty execution config."""
        config = ExecutionConfig.from_dict({})
        assert config.python.allowed_modules == []

    def test_python_allowed_modules(self) -> None:
        """Test parsing allowed modules."""
        config = ExecutionConfig.from_dict({
            "python": {
                "allowed_modules": ["requests", "httpx"],
            },
        })
        assert config.python.allowed_modules == ["requests", "httpx"]


class TestPoliciesConfig:
    """Tests for policy config parsing and resolution."""

    def test_empty_policies_config(self) -> None:
        config = PoliciesConfig.from_dict({})
        assert config.termination is None
        assert config.tool_selection is None
        assert config.tool_result_processing is None

    def test_policy_config_parsing(self) -> None:
        config = PoliciesConfig.from_dict({
            "termination": {
                "type": "max_steps",
                "max_steps": "12",
            },
            "tool_selection": {
                "type": "allowlist",
                "allowed": ["read_file", "search_text"],
            },
            "tool_result_processing": {
                "type": "truncate",
                "max_chars": "500",
            },
        })

        assert config.termination is not None
        assert config.termination.type == "max_steps"
        assert config.termination.config["max_steps"] == "12"
        assert config.tool_selection is not None
        assert config.tool_selection.config["allowed"] == ["read_file", "search_text"]
        assert config.tool_result_processing is not None
        assert config.tool_result_processing.config["max_chars"] == "500"

    def test_builtin_policy_resolution(self) -> None:
        agent_config = AgentConfigYaml(
            policies=PoliciesConfig(
                termination=PolicySpecConfig(
                    type="max_steps",
                    config={"max_steps": "12"},
                ),
                tool_selection=PolicySpecConfig(
                    type="denylist",
                    config={"denied": ["run_shell"]},
                ),
                tool_result_processing=PolicySpecConfig(
                    type="truncate",
                    config={"max_chars": "500"},
                ),
            )
        )

        selection_policy, result_policy, termination_policy = _resolve_policy_bindings(agent_config)

        assert selection_policy is not None
        assert selection_policy.denied == {"run_shell"}
        assert result_policy is not None
        assert result_policy.max_chars == 500
        assert termination_policy is not None
        assert termination_policy.max_steps == 12

    def test_local_policy_resolution(self) -> None:
        class LocalPolicy:
            pass

        builder = PolicyRegistryBuilder()
        builder.register_factory("custom_policy", lambda config: LocalPolicy())

        agent_config = AgentConfigYaml(
            policies=PoliciesConfig(
                termination=PolicySpecConfig(
                    type="local",
                    name="custom_policy",
                ),
            )
        )

        _, _, termination_policy = _resolve_policy_bindings(agent_config, builder.build())
        assert isinstance(termination_policy, LocalPolicy)


class TestResolveSandboxConfig:
    """Tests for sandbox config resolution.

    ADR-029: Module whitelists are no longer enforced.
    Python execution runs in real subprocess with full capabilities.
    """

    def test_default_sandbox_config(self) -> None:
        """Test default sandbox config without agent request."""
        config = _resolve_sandbox_config(None)
        # ADR-029: Module whitelists are no longer enforced
        # Default config has empty lists (backward compatible, but ignored)
        assert config.default_timeout == 30
        assert config.max_timeout == 60

    def test_merge_requested_modules_ignored(self) -> None:
        """Test that agent-requested modules are accepted but ignored.

        ADR-029: allowed_modules configuration is accepted for backward
        compatibility but has no effect on execution.
        """
        agent_config = AgentConfigYaml(
            execution=ExecutionConfig(
                python=PythonExecutionConfig(
                    allowed_modules=["requests", "httpx"],
                ),
            ),
        )
        config = _resolve_sandbox_config(agent_config)
        # Configuration is accepted (no error)
        # But modules are not actually enforced
        assert config.default_timeout == 30

    def test_no_enforcement_of_blocked_modules(self) -> None:
        """Test that blocked modules are no longer enforced.

        ADR-029: Python can import any module (sys, os, subprocess, etc.)
        """
        config = _resolve_sandbox_config(None)
        # ADR-029: blocked_modules is empty (no restrictions)
        assert config.blocked_modules == []


class TestResolveTools:
    """Tests for tool resolution based on capability declaration."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create a workspace directory."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        return ws

    def test_core_tools_by_default(self, workspace: Path) -> None:
        """Test that core tools are provided by compatibility default when no config."""
        # No config → compatibility default: ["core"]
        tools = _resolve_tools(workspace, None)
        tool_names = {t.name for t in tools}

        # Core tools from compatibility default
        assert "list_files" in tool_names
        assert "search_text" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "apply_patch" in tool_names
        assert "execute_python" in tool_names
        assert "run_shell" in tool_names
        assert "request_interaction" in tool_names
        assert "request_skill_activation" in tool_names

        # Network tools NOT included (not requested)
        assert "http_request" not in tool_names
        assert "web_fetch" not in tool_names

    def test_explicit_core_bundle(self, workspace: Path) -> None:
        """Test that explicitly requesting 'core' gives core tools."""
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # Core tools present
        assert "list_files" in tool_names
        assert "execute_python" in tool_names
        assert "request_skill_activation" in tool_names

        # No network tools
        assert "http_request" not in tool_names

    def test_network_tools_when_requested(self, workspace: Path) -> None:
        """Test that network tools are added when requested (core must be explicit)."""
        # Request both core and network
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core", "network"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # Core tools present
        assert "list_files" in tool_names
        assert "execute_python" in tool_names

        # Network tools now included
        assert "http_request" in tool_names
        assert "web_fetch" in tool_names
        assert "web_search" not in tool_names

    def test_network_only_no_core(self, workspace: Path) -> None:
        """Test that requesting only 'network' gives only network tools."""
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["network"]),
        )
        tools = _resolve_tools(workspace, agent_config)
        tool_names = {t.name for t in tools}

        # No core tools
        assert "list_files" not in tool_names
        assert "execute_python" not in tool_names

        # Only network tools
        assert "http_request" in tool_names
        assert "web_fetch" in tool_names
        assert "web_search" not in tool_names

    def test_custom_sandbox_ignored(self, workspace: Path) -> None:
        """Test that custom sandbox config is accepted but ignored.

        ADR-029: allowed_modules configuration is accepted for backward
        compatibility but has no effect on execution. Python can import
        any module regardless of this configuration.
        """
        agent_config = AgentConfigYaml(
            tools=ToolsConfig(bundles=["core"]),  # Need core for Python execution
            execution=ExecutionConfig(
                python=PythonExecutionConfig(
                    allowed_modules=["requests"],
                ),
            ),
        )
        tools = _resolve_tools(workspace, agent_config)

        # Find Python execution tool
        python_tool = next(t for t in tools if t.name == "execute_python")
        assert python_tool is not None

        # ADR-029: allowed_modules is no longer enforced
        # The tool config may be empty (module whitelist removed)
        # But the tool still works and can import any module


class TestAgentConfigYamlIntegration:
    """Tests for full config.yaml parsing with capability declaration."""

    def test_full_config_parsing(self) -> None:
        """Test parsing a complete config with tools and execution."""
        config_data = {
            "model": {"provider": "deepseek", "name": "deepseek-v4-flash"},
            "skills": ["code-review"],
            "tools": {
                "bundles": ["network"],
            },
            "execution": {
                "python": {
                    "allowed_modules": ["requests", "httpx"],
                },
            },
        }
        config = AgentConfigYaml.from_dict(config_data)

        assert config.model_provider == "deepseek"
        assert config.model_name == "deepseek-v4-flash"
        assert config.skills == ["code-review"]
        assert config.include_skill_catalog is False
        assert config.tools.bundles == ["network"]
        assert config.execution.python.allowed_modules == ["requests", "httpx"]

    def test_load_agent_package_yaml_booleans(self, tmp_path: Path) -> None:
        """Test config.yaml boolean values are parsed correctly from disk."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: sample\n---\nSample agent\n",
            encoding="utf-8",
        )
        (agent_dir / "config.yaml").write_text(
            "tools:\n"
            "  bundles:\n"
            "    - network\n"
            "compression:\n"
            "  enabled: false\n",
            encoding="utf-8",
        )

        package = load_agent_package(agent_dir)
        assert package.config is not None
        assert package.config.compression.enabled is False

    def test_load_agent_package_policies(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: sample\n---\nSample agent\n",
            encoding="utf-8",
        )
        (agent_dir / "config.yaml").write_text(
            "policies:\n"
            "  termination:\n"
            "    type: max_steps\n"
            "    max_steps: 7\n"
            "  tool_selection:\n"
            "    type: allowlist\n"
            "    allowed:\n"
            "      - read_file\n"
            "      - search_text\n"
            "  tool_result_processing:\n"
            "    type: truncate\n"
            "    max_chars: 300\n",
            encoding="utf-8",
        )

        package = load_agent_package(agent_dir)

        assert package.config is not None
        assert package.config.policies.termination is not None
        assert package.config.policies.termination.type == "max_steps"
        assert package.config.policies.termination.config["max_steps"] == "7"
        assert package.config.policies.tool_selection is not None
        assert package.config.policies.tool_selection.config["allowed"] == ["read_file", "search_text"]

    def test_loaded_config_resolves_builtin_policies(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            "---\nname: sample\n---\nSample agent\n",
            encoding="utf-8",
        )
        (agent_dir / "config.yaml").write_text(
            "policies:\n"
            "  termination:\n"
            "    type: max_steps\n"
            "    max_steps: 9\n"
            "  tool_result_processing:\n"
            "    type: truncate\n"
            "    max_chars: 123\n",
            encoding="utf-8",
        )

        package = load_agent_package(agent_dir)
        assert package.config is not None

        _, result_policy, termination_policy = _resolve_policy_bindings(package.config)

        assert termination_policy is not None
        assert termination_policy.max_steps == 9
        assert result_policy is not None
        assert result_policy.max_chars == 123

    def test_load_agent_policies_resolves_local_policy_extension(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "agent"
        policies_dir = agent_dir / "extensions" / "policies"
        policies_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text(
            "---\nname: sample\n---\nSample agent\n",
            encoding="utf-8",
        )
        (agent_dir / "config.yaml").write_text(
            "policies:\n"
            "  tool_selection:\n"
            "    type: local\n"
            "    name: no_shell\n",
            encoding="utf-8",
        )
        (policies_dir / "no_shell.py").write_text(
            "from quenda.runtime.tool_policy import ToolSelectionDecision, RejectedToolCall\n\n"
            "class NoShellPolicy:\n"
            "    def select_tools(self, request):\n"
            "        approved = []\n"
            "        rejected = []\n"
            "        for call in request.tool_calls:\n"
            "            if call.name == 'run_shell':\n"
            "                rejected.append(RejectedToolCall(call, 'shell disabled'))\n"
            "            else:\n"
            "                approved.append(call)\n"
            "        return ToolSelectionDecision(approved, rejected)\n\n"
            "policies = {'no_shell': NoShellPolicy()}\n",
            encoding="utf-8",
        )

        builder = PolicyRegistryBuilder()
        loaded = load_agent_policies(agent_dir, builder)
        package = load_agent_package(agent_dir)

        assert loaded == 1
        assert package.config is not None
        selection_policy, _, _ = _resolve_policy_bindings(package.config, builder.build())
        assert selection_policy is not None
        assert type(selection_policy).__name__ == "NoShellPolicy"
