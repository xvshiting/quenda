"""
Agent loader for Quenda.

Provides functions to load agents from files.
Implements ADR-007: Agent package loading with AGENT.md + config.yaml.
Implements ADR-010: Agent command extensions.
Implements ADR-012: Interaction requests and choice controls.
Implements ADR-014: Interface layer extensibility (theme config).
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quenda.host.instructions import InstructionScope, InstructionSource
from quenda.host.mcp.config import MCPConfig
from quenda.runtime.agent import AgentConfig

if TYPE_CHECKING:
    from quenda.host.commands import CommandRegistry
    from quenda.host.interactions import InteractionRegistry
    from quenda.host.registry import ToolRegistryBuilder
    from quenda.interface.theme import InterfaceTheme


def _coerce_bool(value: object, default: bool = False) -> bool:
    """Coerce common YAML-like boolean values into a Python bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "on", "1"}:
            return True
        if normalized in {"false", "no", "n", "off", "0"}:
            return False
    return default


def _parse_scalar_value(value: str) -> object:
    """Parse a scalar YAML-like value from text."""
    raw = value.strip()
    if not raw:
        return ""

    lower = raw.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none", "~"}:
        return None

    # Integer
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        try:
            return int(raw)
        except ValueError:
            pass

    # Float
    try:
        if any(ch in raw for ch in (".", "e", "E")):
            return float(raw)
    except ValueError:
        pass

    return raw.strip("\"'")


@dataclass
class ThemeConfig:
    """
    Theme configuration from config.yaml.

    Supports:
    - preset: "default", "minimal", "ascii", "silent"
    - Or individual overrides for any InterfaceTheme field

    Example config.yaml:
        theme:
          preset: minimal
          # Or override specific fields:
          agent_icon: "🔮"
          show_duration: false
    """

    preset: str | None = None
    overrides: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThemeConfig:
        """Create from parsed YAML dictionary."""
        if isinstance(data, str):
            # Simple form: theme: minimal
            return cls(preset=data)

        if isinstance(data, dict):
            preset = data.get("preset")
            overrides = {k: v for k, v in data.items() if k != "preset"}
            return cls(preset=preset, overrides=overrides)

        return cls()

    def create_theme(self) -> InterfaceTheme:
        """
        Create an InterfaceTheme from this configuration.

        Returns:
            Configured InterfaceTheme instance.
        """
        from quenda.interface.theme import InterfaceTheme

        # Start with preset or default
        if self.preset == "minimal":
            theme = InterfaceTheme.minimal()
        elif self.preset == "ascii":
            theme = InterfaceTheme.ascii()
        elif self.preset == "silent":
            theme = InterfaceTheme.silent()
        else:
            theme = InterfaceTheme()

        # Apply overrides
        for key, value in self.overrides.items():
            if hasattr(theme, key):
                setattr(theme, key, value)

        return theme


@dataclass
class ModelRoleConfig:
    """
    Configuration for a single model role.

    Attributes:
        provider: Provider ID (e.g., "openai", "deepseek").
        model: Model ID (e.g., "gpt-4o", "deepseek-v4-flash").
    """

    provider: str
    model: str

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "ModelRoleConfig | None":
        """Create from parsed YAML dictionary or string."""
        if isinstance(data, str):
            # Simple form: "provider/model"
            parts = data.split("/", 1)
            if len(parts) == 2:
                return cls(provider=parts[0], model=parts[1])
            return None

        if isinstance(data, dict):
            return cls(
                provider=data.get("provider", ""),
                model=data.get("model", ""),
            )

        return None


@dataclass
class ModelsConfig:
    """
    Model roles configuration (ADR-028: Capability-Based Model Routing).

    Supports:
    - default: Default model for text-based tasks
    - vision: Model for image input (routed automatically)
    - routing: Routing behavior configuration

    Example config.yaml:
        models:
          default:
            provider: deepseek
            model: deepseek-v4-flash
          vision:
            provider: dashscope
            model: qwen3-vl-plus
          routing:
            capability_routing: true
            missing_capability: error
    """

    default: ModelRoleConfig | None = None
    vision: ModelRoleConfig | None = None
    capability_routing: bool = True
    missing_capability: str = "error"  # error | warn | ignore

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelsConfig":
        """Create from parsed YAML dictionary."""
        if not data:
            return cls()

        # Handle simple form: models: "provider/model"
        if isinstance(data, str):
            default = ModelRoleConfig.from_dict(data)
            return cls(default=default)

        default_data = data.get("default")
        vision_data = data.get("vision")
        routing_data = data.get("routing", {})

        return cls(
            default=ModelRoleConfig.from_dict(default_data) if default_data else None,
            vision=ModelRoleConfig.from_dict(vision_data) if vision_data else None,
            capability_routing=_coerce_bool(
                routing_data.get("capability_routing", True), True
            ),
            missing_capability=routing_data.get("missing_capability", "error"),
        )


@dataclass
class CompressionConfig:
    """
    Compression configuration from config.yaml (ADR-015).

    Example config.yaml:
        compression:
          enabled: true
          threshold_ratio: 0.8
          keep_last_n_messages: 10
          archive_raw_messages: true
          compression_model: "deepseek-v4-flash"  # Optional, use cheaper model
    """

    enabled: bool = True
    threshold_ratio: float = 0.8
    keep_last_n_messages: int = 10
    archive_raw_messages: bool = True
    compression_model: str | None = None  # Use different model for summarization

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompressionConfig:
        """Create from parsed YAML dictionary."""
        if not data:
            return cls()

        return cls(
            enabled=_coerce_bool(data.get("enabled", True), True),
            threshold_ratio=data.get("threshold_ratio", 0.8),
            keep_last_n_messages=data.get("keep_last_n_messages", 10),
            archive_raw_messages=_coerce_bool(data.get("archive_raw_messages", True), True),
            compression_model=data.get("compression_model"),
        )


@dataclass
class ToolsConfig:
    """
    Tool capability request from agent package.

    Agent can declare which tool bundles and individual tools it needs.
    Host resolves the final tool set based on these requests.

    Example config.yaml:
        tools:
          bundles:
            - core       # Default: filesystem + execution + interaction
            - network    # HTTP, web fetch, web search
          include:
            - http_request
            - web_fetch
    """

    bundles: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolsConfig:
        """Create from parsed YAML dictionary."""
        if not data:
            return cls()

        return cls(
            bundles=data.get("bundles", []),
            include=data.get("include", []),
        )


@dataclass
class PythonExecutionConfig:
    """
    Python sandbox capability request from agent package.

    Agent can request additional modules to be allowed in Python sandbox.
    Host decides final allowed modules based on security policy.

    Example config.yaml:
        execution:
          python:
            allowed_modules:
              - requests
              - httpx
    """

    allowed_modules: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PythonExecutionConfig:
        """Create from parsed YAML dictionary."""
        if not data:
            return cls()

        return cls(
            allowed_modules=data.get("allowed_modules", []),
        )


@dataclass
class ExecutionConfig:
    """
    Execution capability request from agent package.

    Controls sandbox and execution environment capabilities.
    """

    python: PythonExecutionConfig = field(default_factory=PythonExecutionConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionConfig:
        """Create from parsed YAML dictionary."""
        if not data:
            return cls()

        python_data = data.get("python", {})
        return cls(
            python=PythonExecutionConfig.from_dict(python_data),
        )


@dataclass
class PolicySpecConfig:
    """
    One configured policy binding.

    The `type` field selects a built-in policy or `local`; all remaining keys
    are passed as policy-specific parameters.
    """

    type: str = ""
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicySpecConfig:
        if not data:
            return cls()

        policy_type = str(data.get("type", data.get("name", "")))
        name = str(data.get("name", ""))
        config = {k: v for k, v in data.items() if k not in {"type", "name"}}
        nested_config = data.get("config")
        if isinstance(nested_config, dict):
            config.update(nested_config)
            config.pop("config", None)

        return cls(type=policy_type, name=name, config=config)


@dataclass
class PoliciesConfig:
    """
    Policy bindings requested by an agent package.

    Example config.yaml:
        policies:
          termination:
            type: max_steps
            max_steps: 30
          tool_selection:
            type: allowlist
            allowed:
              - read_file
              - search_text
          tool_result_processing:
            type: truncate
            max_chars: 6000
    """

    termination: PolicySpecConfig | None = None
    tool_selection: PolicySpecConfig | None = None
    tool_result_processing: PolicySpecConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PoliciesConfig:
        if not data:
            return cls()

        termination = data.get("termination")
        tool_selection = data.get("tool_selection")
        tool_result_processing = data.get("tool_result_processing")

        return cls(
            termination=PolicySpecConfig.from_dict(termination) if isinstance(termination, dict) else None,
            tool_selection=PolicySpecConfig.from_dict(tool_selection) if isinstance(tool_selection, dict) else None,
            tool_result_processing=(
                PolicySpecConfig.from_dict(tool_result_processing)
                if isinstance(tool_result_processing, dict)
                else None
            ),
        )


@dataclass
class AgentConfigYaml:
    """
    Machine-readable agent configuration from config.yaml.

    Attributes:
        model_provider: Default model provider (legacy, prefer models.default).
        model_name: Default model name (legacy, prefer models.default).
        models: Model roles configuration (ADR-028).
        instructions_include: List of instruction files to include.
        skills: List of skills to activate by default.
        mcp: MCP server configuration.
        theme: Theme configuration for interface layer.
        compression: Compression configuration (ADR-015).
        tools: Tool capability request.
        execution: Execution capability request.
        policies: Runtime policy bindings.
    """

    model_provider: str | None = None
    model_name: str | None = None
    models: ModelsConfig = field(default_factory=ModelsConfig)
    instructions_include: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    include_skill_catalog: bool = False
    mcp: MCPConfig | None = None
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    policies: PoliciesConfig = field(default_factory=PoliciesConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfigYaml:
        """Create from parsed YAML dictionary."""
        model = data.get("model", {})
        models_data = data.get("models", {})
        instructions = data.get("instructions", {})
        theme_data = data.get("theme", {})
        compression_data = data.get("compression", {})
        tools_data = data.get("tools", {})
        execution_data = data.get("execution", {})
        policies_data = data.get("policies", {})
        mcp_data = data.get("mcp", {})

        # Skills can be at top level or under skills.activate
        skills_data = data.get("skills", {})
        if isinstance(skills_data, list):
            # Simple form: skills: [skill1, skill2]
            skills_list = skills_data
        elif isinstance(skills_data, dict):
            # Structured form: skills: {activate: [skill1, skill2]}
            skills_list = skills_data.get("activate", [])
            include_skill_catalog = skills_data.get("include_catalog", False)
        else:
            skills_list = []
            include_skill_catalog = False

        # Parse models config
        # Priority: models key > model key with new format (default/vision) > model key with legacy format
        models_config = None

        # 1. Check for "models:" key (ADR-028 new format)
        if models_data:
            models_config = ModelsConfig.from_dict(models_data)

        # 2. Check for "model:" key with new format (default/vision)
        if models_config is None and isinstance(model, dict):
            if "default" in model or "vision" in model:
                # model: default: ... vision: ... format
                models_config = ModelsConfig.from_dict(model)

        # 3. Check for "model:" key with legacy format (provider/name)
        if models_config is None or models_config.default is None:
            if isinstance(model, dict):
                model_provider = model.get("provider")
                model_name = model.get("name")
                if model_provider and model_name:
                    # Legacy format: model: provider: ... name: ...
                    models_config = ModelsConfig(
                        default=ModelRoleConfig(provider=model_provider, model=model_name)
                    )

        # 4. Default: empty config
        if models_config is None:
            models_config = ModelsConfig()

        # Parse MCP config
        mcp_config = None
        if mcp_data:
            mcp_config = MCPConfig.from_dict(mcp_data)

        return cls(
            model_provider=model.get("provider") if isinstance(model, dict) else None,
            model_name=model.get("name") if isinstance(model, dict) else None,
            models=models_config,
            instructions_include=instructions.get("include", []) if isinstance(instructions, dict) else [],
            skills=skills_list,
            include_skill_catalog=_coerce_bool(include_skill_catalog, False)
            if isinstance(skills_data, dict)
            else False,
            mcp=mcp_config,
            theme=ThemeConfig.from_dict(theme_data),
            compression=CompressionConfig.from_dict(compression_data),
            tools=ToolsConfig.from_dict(tools_data),
            execution=ExecutionConfig.from_dict(execution_data),
            policies=PoliciesConfig.from_dict(policies_data),
        )


@dataclass
class AgentPackage:
    """
    A complete agent package loaded from a directory.

    Attributes:
        path: Path to the agent package directory.
        name: Agent name.
        version: Agent version.
        description: Agent description.
        agent_md: Content of AGENT.md (base prompt).
        config: Parsed config.yaml if exists.
        instructions: List of included instruction sources.
    """

    path: Path
    name: str
    version: str
    description: str
    agent_md: str
    config: AgentConfigYaml | None = None
    instructions: list[InstructionSource] = field(default_factory=list)


def load_agent_from_markdown(path: Path | str) -> AgentConfig:
    """
    Load an agent configuration from an AGENT.md file.

    Expected format:
    ```markdown
    ---
    name: my-agent
    tools:
      - echo
      - calculate
    ---

    You are a helpful assistant...
    ```

    Args:
        path: Path to the AGENT.md file.

    Returns:
        An AgentConfig instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file format is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Agent file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Parse frontmatter
    if not content.startswith("---"):
        raise ValueError(f"Agent file must start with '---': {path}")

    # Split frontmatter and content
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid agent file format: {path}")

    frontmatter = parts[1].strip()
    body = parts[2].strip()

    # Parse frontmatter (simple YAML-like parsing)
    config: dict[str, object] = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Handle list values
            if value.startswith("[") and value.endswith("]"):
                # Simple list parsing: [a, b, c]
                items = value[1:-1].split(",")
                config[key] = [_parse_scalar_value(item) for item in items if item.strip()]
            else:
                # Remove quotes
                config[key] = _parse_scalar_value(value)

    name = config.get("name", path.parent.name)
    if not isinstance(name, str):
        raise ValueError(f"Agent name must be a string: {path}")

    return AgentConfig(
        name=name,
        system_prompt=body if body else None,
        tools=[],  # Tools must be added separately
    )


def load_agent_package(path: Path | str) -> AgentPackage:
    """
    Load an agent package from a directory.

    Loads:
    - AGENT.md (required) - base prompt and metadata
    - config.yaml (optional) - machine-readable configuration
    - instructions/*.md (if included in config.yaml)

    Args:
        path: Path to the agent package directory.

    Returns:
        An AgentPackage instance.

    Raises:
        FileNotFoundError: If AGENT.md doesn't exist.
        ValueError: If the file format is invalid.
    """
    path = Path(path)

    # Load AGENT.md (required)
    agent_md_path = path / "AGENT.md"
    if not agent_md_path.exists():
        raise FileNotFoundError(f"AGENT.md not found in {path}")

    agent_md_content = agent_md_path.read_text(encoding="utf-8")

    # Parse AGENT.md frontmatter
    frontmatter = _parse_frontmatter(agent_md_content, agent_md_path)
    name = frontmatter.get("name", path.name)
    version = frontmatter.get("version", "0.1.0")
    description = frontmatter.get("description", "")

    # Extract body (after frontmatter)
    parts = agent_md_content.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
    else:
        body = ""

    # Load config.yaml (optional)
    config_path = path / "config.yaml"
    config: AgentConfigYaml | None = None
    if config_path.exists():
        config_data = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))
        config = AgentConfigYaml.from_dict(config_data)

    # Load included instructions
    instructions: list[InstructionSource] = []
    if config and config.instructions_include:
        for include_path in config.instructions_include:
            # Resolve path relative to agent package
            instruction_path = path / include_path
            if instruction_path.exists():
                content = instruction_path.read_text(encoding="utf-8")
                instructions.append(InstructionSource(
                    scope=InstructionScope.AGENT_INSTRUCTIONS,
                    content=content,
                    path=instruction_path,
                ))

    return AgentPackage(
        path=path,
        name=name if isinstance(name, str) else str(name),
        version=version if isinstance(version, str) else "0.1.0",
        description=description if isinstance(description, str) else "",
        agent_md=body,
        config=config,
        instructions=instructions,
    )


def _parse_frontmatter(content: str, path: Path) -> dict[str, object]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    frontmatter = parts[1].strip()
    config: dict[str, object] = {}

    for line in frontmatter.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Handle list values
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1].split(",")
                config[key] = [_parse_scalar_value(item) for item in items if item.strip()]
            else:
                config[key] = _parse_scalar_value(value)

    return config


def _parse_simple_yaml(content: str) -> dict[str, Any]:
    """
    Parse simple YAML content.

    Supports:
    - key: value (top-level)
    - nested dicts with indentation
    - lists with -
    """
    result: dict[str, Any] = {}

    # Stack of dicts: [result, level1_dict, level2_dict, ...]
    dict_stack: list[dict[str, Any]] = [result]
    # Stack of keys for nested dicts
    key_stack: list[str] = []
    # Current list being built and its parent
    current_list: list[str] | None = None
    current_list_dict: dict[str, Any] | None = None
    current_list_key: str | None = None

    for line in content.split("\n"):
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        indent_level = indent // 2  # 0, 1, 2, ...

        # Handle list items (check lstrip to handle indentation)
        lstripped = stripped.lstrip()
        if lstripped.startswith("- "):
            if current_list is None:
                current_list = []
            current_list.append(lstripped[2:].strip("\"'"))
            continue

        # Handle key: value
        if ":" in stripped:
            # Save any pending list to its parent dict
            if current_list is not None and current_list_dict is not None and current_list_key is not None:
                current_list_dict[current_list_key] = current_list
                current_list = None
                current_list_dict = None
                current_list_key = None

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Adjust stack to current indent level
            while len(key_stack) > indent_level:
                key_stack.pop()
                if len(dict_stack) > 1:
                    dict_stack.pop()

            current_dict = dict_stack[-1]

            if value == "":
                # Start of nested structure (could become dict or list)
                # For now, create empty dict; will be replaced if list follows
                current_dict[key] = {}
                dict_stack.append(current_dict[key])
                key_stack.append(key)
                # Remember this location in case a list follows
                current_list_dict = current_dict
                current_list_key = key
            else:
                # Regular value
                current_dict[key] = value.strip("\"'")
                # Clear list tracking since this is a value, not a list parent
                current_list_dict = None
                current_list_key = None

    # Save any pending list at end
    if current_list is not None and current_list_dict is not None and current_list_key is not None:
        current_list_dict[current_list_key] = current_list

    return result


def load_agent_commands(
    agent_path: Path,
    registry: CommandRegistry,
) -> int:
    """
    Load command extensions from an agent package.

    Implements ADR-010: Agent command extensions.

    Scans `extensions/commands/*.py` in the agent package directory,
    loads each module, and registers commands.

    Loading contract (one of):
    1. `commands` list - list of Command objects
    2. `register(registry)` function - called to register commands

    Args:
        agent_path: Path to the agent package directory.
        registry: CommandRegistry to register commands into.

    Returns:
        Number of command files loaded (not individual commands).
    """
    commands_dir = agent_path / "extensions" / "commands"
    if not commands_dir.exists():
        return 0

    loaded = 0
    for py_file in commands_dir.glob("*.py"):
        # Skip private/internal modules
        if py_file.name.startswith("_"):
            continue

        try:
            module = _load_extension_module(py_file, namespace="commands")
            if module is None:
                continue

            # Priority 1: commands list
            if hasattr(module, "commands"):
                for cmd in module.commands:
                    registry.register(cmd)
                loaded += 1

            # Priority 2: register function
            elif hasattr(module, "register"):
                module.register(registry)
                loaded += 1

        except Exception as e:
            # Log warning but don't fail agent loading
            import warnings
            warnings.warn(
                f"Failed to load command extension {py_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return loaded


def load_agent_interactions(
    agent_path: Path,
    registry: InteractionRegistry,
) -> int:
    """
    Load interaction extensions from an agent package.

    Implements the same agent-local extension pattern as commands.

    Scans `extensions/interactions/*.py` in the agent package directory,
    loads each module, and registers interactions.

    Loading contract (one of):
    1. `interactions` list - list of Interaction objects
    2. `register(registry)` function - called to register interactions

    Args:
        agent_path: Path to the agent package directory.
        registry: InteractionRegistry to register interactions into.

    Returns:
        Number of interaction files loaded (not individual interactions).
    """
    interactions_dir = agent_path / "extensions" / "interactions"
    if not interactions_dir.exists():
        return 0

    loaded = 0
    for py_file in interactions_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            module = _load_extension_module(py_file, namespace="interactions")
            if module is None:
                continue

            if hasattr(module, "interactions"):
                for interaction in module.interactions:
                    registry.register(interaction)
                loaded += 1
            elif hasattr(module, "register"):
                module.register(registry)
                loaded += 1

        except Exception as e:
            import warnings

            warnings.warn(
                f"Failed to load interaction extension {py_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return loaded


def load_agent_tools(
    agent_path: Path,
    builder: ToolRegistryBuilder,
) -> int:
    """
    Load tool extensions from an agent package.

    Implements ADR-024: Agent-local custom tool extensions.

    Scans `extensions/tools/*.py` in the agent package directory,
    loads each module, and registers tools.

    Loading contract (one of):
    1. `tools` list - list of Tool objects
    2. `register(builder)` function - called to register tools

    Args:
        agent_path: Path to the agent package directory.
        builder: ToolRegistryBuilder to register tools into.

    Returns:
        Number of tool files loaded (not individual tools).

    Raises:
        ValueError: If a tool name conflicts with an already registered tool.
    """
    tools_dir = agent_path / "extensions" / "tools"
    if not tools_dir.exists():
        return 0

    loaded = 0
    for py_file in tools_dir.glob("*.py"):
        # Skip private/internal modules
        if py_file.name.startswith("_"):
            continue

        try:
            module = _load_extension_module(py_file, namespace="tools")
            if module is None:
                continue

            # Priority 1: tools list
            if hasattr(module, "tools"):
                for tool in module.tools:
                    builder.register(tool, source="agent_local")
                loaded += 1

            # Priority 2: register function
            elif hasattr(module, "register"):
                module.register(builder)
                loaded += 1

        except ValueError:
            # Re-raise ValueError (duplicate tool name)
            raise
        except Exception as e:
            # Log warning but don't fail agent loading
            import warnings
            warnings.warn(
                f"Failed to load tool extension {py_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return loaded


def load_agent_policies(
    agent_path: Path,
    builder: "PolicyRegistryBuilder",
) -> int:
    """
    Load policy extensions from an agent package.

    Scans `extensions/policies/*.py` in the agent package directory.

    Loading contract (one of):
    1. `policies` dict - mapping policy name to policy instance or factory
    2. `register(builder)` function - called to register policies
    """
    from quenda.host.policy_registry import PolicyRegistryBuilder

    policies_dir = agent_path / "extensions" / "policies"
    if not policies_dir.exists():
        return 0

    loaded = 0
    for py_file in policies_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            module = _load_extension_module(py_file, namespace="policies")
            if module is None:
                continue

            if hasattr(module, "policies"):
                policies = module.policies
                if not isinstance(policies, dict):
                    raise ValueError("policies must be a dict of name -> policy/factory")
                for name, policy in policies.items():
                    if callable(policy):
                        builder.register_factory(str(name), policy, source="agent_local")
                    else:
                        builder.register(str(name), policy, source="agent_local")
                loaded += 1
            elif hasattr(module, "register"):
                module.register(builder)
                loaded += 1

        except ValueError:
            raise
        except Exception as e:
            import warnings

            warnings.warn(
                f"Failed to load policy extension {py_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return loaded


def load_agent_providers(
    agent_path: Path,
) -> int:
    """
    Load provider extensions from an agent package.

    Scans `extensions/providers/*.py` in the agent package directory,
    loads each module, and registers providers to the global registry.

    Loading contract (one of):
    1. `providers` list - list of ProviderSpec objects
    2. `register(registry)` function - called to register providers

    Args:
        agent_path: Path to the agent package directory.

    Returns:
        Number of provider files loaded (not individual providers).

    Raises:
        ValueError: If a provider ID conflicts with an already registered provider.
    """
    from quenda.providers import get_provider_registry

    providers_dir = agent_path / "extensions" / "providers"
    if not providers_dir.exists():
        return 0

    registry = get_provider_registry()
    loaded = 0

    for py_file in providers_dir.glob("*.py"):
        # Skip private/internal modules
        if py_file.name.startswith("_"):
            continue

        try:
            module = _load_extension_module(py_file, namespace="providers")
            if module is None:
                continue

            # Priority 1: providers list
            if hasattr(module, "providers"):
                for spec in module.providers:
                    registry.register(spec)
                loaded += 1

            # Priority 2: register function
            elif hasattr(module, "register"):
                module.register(registry)
                loaded += 1

        except ValueError:
            # Re-raise ValueError (duplicate provider ID)
            raise
        except Exception as e:
            # Log warning but don't fail agent loading
            import warnings
            warnings.warn(
                f"Failed to load provider extension {py_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    return loaded


def _load_extension_module(py_file: Path, *, namespace: str):
    """
    Dynamically load a Python module from a file.

    Args:
        py_file: Path to the Python file.
        namespace: Module namespace prefix to avoid collisions.

    Returns:
        The loaded module, or None on failure.
    """
    module_name = f"kora_ext_{namespace}_{py_file.stem}"

    # Skip if already loaded
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        # Clean up on failure
        del sys.modules[module_name]
        raise


def find_builtin_agent(name: str) -> Path | None:
    """
    Find a built-in agent by name.

    Discovery order:
    1. Entry points (``kora.agents`` group) — for pip-installed packages.
    2. Development fallback — ``agents/<name>/`` relative to project root.

    Args:
        name: Agent name (e.g., ``"quenda-code"``).

    Returns:
        Path to agent directory or ``None`` if not found.
    """
    # Priority 1: Entry point discovery (ADR-013)
    # Installed agent packages register a quenda.agents entry point
    # pointing to a module with an AGENT_DIR attribute.
    try:
        from importlib.metadata import entry_points

        for ep in entry_points(group="quenda.agents"):
            if ep.name == name:
                module = ep.load()
                agent_dir = getattr(module, "AGENT_DIR", None)
                if agent_dir is not None and agent_dir.exists():
                    return Path(agent_dir)
    except Exception:
        pass

    # Priority 2: Development mode — look in agents/ relative to project root.
    # loader.py is at: <project_root>/src/kora/host/loader.py
    package_dir = Path(__file__).parent  # src/kora/host
    quenda_dir = package_dir.parent  # src/kora
    src_dir = quenda_dir.parent  # src
    project_root = src_dir.parent  # project root

    # Try new layout: agents/<name>/src/quenda_code/agent/
    agent_dir = project_root / "agents" / name / "src" / "quenda_code" / "agent"
    if agent_dir.exists() and (agent_dir / "AGENT.md").exists():
        return agent_dir

    # Try old layout: agents/<name>/
    agent_dir = project_root / "agents" / name
    if agent_dir.exists() and (agent_dir / "AGENT.md").exists():
        return agent_dir

    return None


__all__ = [
    "ThemeConfig",
    "CompressionConfig",
    "ToolsConfig",
    "PythonExecutionConfig",
    "ExecutionConfig",
    "PolicySpecConfig",
    "PoliciesConfig",
    "AgentConfigYaml",
    "AgentPackage",
    "load_agent_from_markdown",
    "load_agent_package",
    "load_agent_commands",
    "load_agent_interactions",
    "load_agent_tools",
    "load_agent_policies",
    "load_agent_providers",
    "find_builtin_agent",
]
