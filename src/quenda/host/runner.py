"""
Agent runner for Quenda Host layer.

Provides high-level API to setup and run agents, encapsulating
the orchestration of all Host layer components.

This is the "main entry point" for programmatic agent usage,
allowing CLI and other interfaces to be thin wrappers.

Implements:
- ADR-026: Textual Context Reload and Capability Rebind
- ADR-025: Skill Lifetime and Prompt Residency
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quenda.host.context import ContextRebuilder
from quenda.host.identity import DefaultUserResolver, User
from quenda.host.instructions import (
    InstructionComposer,
    InstructionSource,
    TemplateContext,
    resolve_instruction_sources,
)
from quenda.host.loader import (
    AgentConfigYaml,
    AgentPackage,
    ExecutionConfig,
    load_agent_package,
    load_agent_tools,
    load_agent_providers,
)
from quenda.host.registry import LoadedToolCatalog, NamedToolSpec, ToolRegistryBuilder
from quenda.host.skill import SkillDiscovery, SkillActivator, ResourceResolver
from quenda.host.storage import FileStorage, FileStorageConfig
from quenda.host.workspace import WorkspaceResolver

if TYPE_CHECKING:
    from quenda.host.commands import CommandRegistry
    from quenda.host.compression_policy import CompressionPolicy
    from quenda.host.interactions import InteractionRegistry
    from quenda.host.skill import SkillPackage
    from quenda.kernel.model import Model
    from quenda.runtime.agent import Agent
    from quenda.runtime.compressor import Compressor
    from quenda.runtime.permission import PermissionPolicy
    from quenda.tools import Tool
    from quenda.tools.execution import SandboxConfig


# =============================================================================
# Data Structures for Two-Path Model (ADR-026)
# =============================================================================


@dataclass
class StableHostBinding:
    """
    Capability-level bindings that persist across runs.

    These are resolved once at setup or explicit rebind time.
    They should NOT be silently re-read at each turn.

    Attributes:
        agent_package_path: Path to the agent package.
        workspace_path: Path to the workspace.
        workspace_id: Unique workspace identifier.
        user: Current user identity.
        provider_name: Model provider name.
        model_name: Model name.
        model_instance: Resolved Model instance.
        vision_model_instance: Optional vision model for capability routing (ADR-028).
        capability_routing: Whether capability-based routing is enabled.
        tools: Granted tool set.
        sandbox_config: Python sandbox configuration.
        compression_policy: Compression policy if enabled.
        compressor: Compressor instance if enabled.
        storage: File storage for session persistence.
        active_skill_names: Durable persistent skill activation state.
        transient_skill_names: Transient model-selected skills for current task.
        loaded_tool_catalog: Catalog of custom tools.
        agent_package: Loaded agent package (for config access).
        skill_activator: Skill activation manager.
    """

    agent_package_path: Path
    workspace_path: Path
    workspace_id: str
    user: User
    provider_name: str
    model_name: str
    model_instance: Model
    tools: list[Tool]
    sandbox_config: SandboxConfig
    vision_model_instance: Model | None = None
    capability_routing: bool = True
    compression_policy: CompressionPolicy | None = None
    compressor: Compressor | None = None
    storage: FileStorage | None = None
    active_skill_names: list[str] = field(default_factory=list)
    transient_skill_names: list[str] = field(default_factory=list)
    loaded_tool_catalog: LoadedToolCatalog | None = None
    agent_package: AgentPackage | None = None
    skill_activator: SkillActivator | None = None


@dataclass
class RunContextSnapshot:
    """
    Text-level context rebuilt before each run.

    These are re-read at each turn boundary. Editing AGENT.md,
    instructions, or skill files should affect the next run.

    Attributes:
        agent_md_content: Re-read AGENT.md content.
        instruction_sources: Resolved instruction sources.
        composed_prompt: Final composed system prompt.
        discovered_skills: Freshly discovered skill catalog.
        resolved_active_skills: SkillPackage objects for active skills.
        template_context: Template variables for prompt composition.
    """

    agent_md_content: str
    instruction_sources: list[InstructionSource]
    composed_prompt: str
    discovered_skills: list[SkillPackage] = field(default_factory=list)
    resolved_active_skills: list[SkillPackage] = field(default_factory=list)
    template_context: TemplateContext | None = None


def _resolve_tools(
    workspace: Path,
    config: AgentConfigYaml | None,
    loaded_tool_catalog: LoadedToolCatalog | None = None,
    skill_resource_resolver: ResourceResolver | None = None,
    permission_policy: "PermissionPolicy" | None = None,
) -> list[Tool]:
    """
    Resolve tools based on agent capability declaration.

    Implements ADR-014 and ADR-024 capability declaration:
    - tools.bundles: ["core", "network"]
    - tools.include: ["my_custom_tool"]
    - execution.python.allowed_modules: extend sandbox allowlist

    All bundles and include entries are requests. The Host resolves
    the final tool set.

    **Compatibility default**: If tools.bundles is missing or empty,
    Host defaults to ["core"]. This is a compatibility measure, not
    a "core is free" policy. Future versions may require explicit
    declaration for all capabilities.

    Args:
        workspace: Workspace path for file operations.
        config: Agent configuration from config.yaml.
        loaded_tool_catalog: Catalog of agent-local custom tools.
        skill_resource_resolver: Optional resolver for skill resource tools.

    Returns:
        List of resolved Tool instances.

    Raises:
        ValueError: If a requested tool in tools.include is not found.
    """
    from quenda.tools import (
        ApplyPatchTool,
        ListFilesTool,
        PythonExecutionTool,
        ReadFileTool,
        RequestInteractionTool,
        RequestSkillActivationTool,
        RunShellTool,
        SearchTextTool,
        WriteFileTool,
    )
    from quenda.tools.execution import SandboxConfig

    # Determine requested bundles
    # Compatibility default: missing/empty bundles → ["core"]
    requested_bundles: list[str]
    if config and config.tools and config.tools.bundles:
        requested_bundles = config.tools.bundles
    else:
        requested_bundles = ["core"]  # Compatibility default

    # Determine requested individual tools
    requested_include: list[str]
    if config and config.tools and config.tools.include:
        requested_include = config.tools.include
    else:
        requested_include = []

    # Build a unified catalog with built-in tools
    builder = ToolRegistryBuilder()

    # Register built-in bundle tools (for reference and deduplication)
    # Core bundle tools
    if "core" in requested_bundles:
        sandbox_config = _resolve_sandbox_config(config)
        builder.register(ListFilesTool(workspace), source="builtin")
        builder.register(SearchTextTool(workspace), source="builtin")
        builder.register(ReadFileTool(workspace, permission_policy=permission_policy), source="builtin")
        builder.register(WriteFileTool(workspace), source="builtin")
        builder.register(ApplyPatchTool(workspace), source="builtin")
        builder.register(RunShellTool(workspace), source="builtin")
        builder.register(RequestInteractionTool(), source="builtin")
        builder.register(RequestSkillActivationTool(), source="builtin")
        builder.register(PythonExecutionTool(workspace, sandbox_config), source="builtin")

    # Network bundle tools
    if "network" in requested_bundles:
        from quenda.tools.network import HTTPRequestTool, WebFetchTool
        builder.register(HTTPRequestTool(), source="builtin")
        builder.register(WebFetchTool(), source="builtin")

    # Register agent-local custom tools from loaded catalog
    if loaded_tool_catalog:
        for spec in loaded_tool_catalog.all_specs():
            # Check for duplicate names (built-in vs custom)
            if builder._catalog.has(spec.name):
                existing = builder._catalog.get(spec.name)
                if existing.source == "builtin":
                    raise ValueError(
                        f"Agent-local tool '{spec.name}' conflicts with built-in tool. "
                        f"Custom tools cannot override built-in tool names."
                    )
            builder._catalog.add(spec)

    # Register skill resource tools if resolver is provided
    if skill_resource_resolver is not None:
        builder.register_skill_resource_tools(skill_resource_resolver)

    # Resolve requested include names
    resolved_tools: list[Tool] = []
    seen_names: set[str] = set()

    # Add all registered tools (builtin + skill_resource + agent_local)
    # Note: skill_resource tools are always available when skills are configured
    for name, spec in builder._catalog.tools.items():
        if spec.source in ("builtin", "skill_resource"):
            tool = _instantiate_tool(spec, workspace)
            _apply_permission_policy(tool, permission_policy)
            if tool.name not in seen_names:
                resolved_tools.append(tool)
                seen_names.add(tool.name)

    # Then, resolve tools.include names
    for name in requested_include:
        if name in seen_names:
            continue  # Already included via bundle

        spec = builder._catalog.get(name)
        if spec is None:
            raise ValueError(
                f"Tool '{name}' requested in tools.include not found. "
                f"Available tools: {builder._catalog.all_names()}"
            )

        tool = _instantiate_tool(spec, workspace)
        _apply_permission_policy(tool, permission_policy)
        if tool.name not in seen_names:
            resolved_tools.append(tool)
            seen_names.add(tool.name)

    return resolved_tools


def _instantiate_tool(spec: NamedToolSpec, workspace: Path) -> Tool:
    """
    Instantiate a tool from a spec.

    Args:
        spec: The tool spec to instantiate.
        workspace: Workspace path for context-aware tools.

    Returns:
        The instantiated Tool.
    """
    if spec.tool is not None:
        return spec.tool

    if spec.factory is not None:
        # Try calling with workspace first, then without
        try:
            return spec.factory(workspace)
        except TypeError:
            return spec.factory()

    raise ValueError(f"Tool spec '{spec.name}' has neither tool nor factory")


def _apply_permission_policy(tool: Tool, permission_policy: "PermissionPolicy" | None) -> None:
    """Attach the active permission policy to tools that support it."""
    if permission_policy is None:
        return

    try:
        current_policy = getattr(tool, "permission_policy", None)
        if current_policy is None:
            setattr(tool, "permission_policy", permission_policy)
    except Exception:
        pass


def _resolve_sandbox_config(config: AgentConfigYaml | None) -> SandboxConfig:
    """
    Resolve sandbox configuration based on agent capability request.

    Agent can request additional allowed modules via:
    ```yaml
    execution:
      python:
        allowed_modules:
          - requests
          - httpx
    ```

    Host merges requested modules with the default allowlist.
    Blocked modules are always enforced for security.

    Args:
        config: Agent configuration from config.yaml.

    Returns:
        SandboxConfig with resolved allowed modules.
    """
    from quenda.tools.execution import SandboxConfig
    from quenda.tools.security.patterns import SANDBOX_ALLOWED_MODULES

    # Start with default allowed modules
    allowed = list(SANDBOX_ALLOWED_MODULES)

    # Merge agent-requested modules
    if config and config.execution and config.execution.python:
        requested = config.execution.python.allowed_modules
        if requested:
            # Add requested modules that aren't already in the list
            for module in requested:
                if module not in allowed:
                    allowed.append(module)

    return SandboxConfig(allowed_modules=allowed)


# =============================================================================
# Path A: Capability Binding (runs once at setup or explicit rebind)
# =============================================================================


def setup_host_binding(
    agent_path: Path,
    workspace: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    tools: list[Tool] | None = None,
    permission_policy: "PermissionPolicy" | None = None,
) -> StableHostBinding | None:
    """
    Capability binding path - runs once at setup or explicit rebind.

    This resolves capability-affecting configuration:
    - Model/provider binding
    - Tool grants
    - Sandbox configuration
    - Policy wiring
    - Initial skill activation (names only)

    These bindings remain stable across runs until explicitly rebound.

    Args:
        agent_path: Path to AGENT.md file or agent directory.
        workspace: Workspace directory for file operations.
        provider: Model provider override.
        model: Model name override.
        tools: Optional custom tools (overrides config-based resolution).

    Returns:
        StableHostBinding with capability-level bindings, or None on error.
    """
    try:
        # 1. Validate paths
        if not agent_path.exists():
            return None

        if not workspace.exists():
            return None

        # 2. Determine if path is AGENT.md or directory
        if agent_path.is_file() and agent_path.name == "AGENT.md":
            agent_dir = agent_path.parent
        else:
            agent_dir = agent_path

        # 3. Load agent package
        agent_package = load_agent_package(agent_dir)

        # 4. Resolve workspace binding
        resolver = WorkspaceResolver()
        binding = resolver.resolve(workspace)
        workspace_id = binding.id

        # 5. Resolve user
        user = DefaultUserResolver().resolve()

        # 6. Load agent-local custom providers (before resolving provider/model)
        load_agent_providers(agent_dir)

        # 7. Resolve provider/model (with ADR-028 model roles support)
        models_config = (
            agent_package.config.models
            if agent_package.config and agent_package.config.models
            else None
        )

        # Determine default model
        if models_config and models_config.default:
            provider_name = models_config.default.provider
            model_name = models_config.default.model
        else:
            # Legacy or override
            provider_name = provider or (
                agent_package.config.model_provider if agent_package.config else None
            ) or "deepseek"
            model_name = model or (
                agent_package.config.model_name if agent_package.config else None
            ) or "deepseek-v4-flash"

        # 8. Get model instances
        from quenda.providers import get_provider_registry
        registry = get_provider_registry()
        try:
            model_instance = registry.get_model(provider_name, model_name)
        except KeyError:
            return None

        # Resolve vision model if configured
        vision_model_instance = None
        capability_routing = models_config.capability_routing if models_config else True

        if models_config and models_config.vision:
            try:
                vision_model_instance = registry.get_model(
                    models_config.vision.provider,
                    models_config.vision.model,
                )
            except KeyError:
                # Vision model configured but not found - will warn but not fail
                pass

        # 9. Setup skill discovery and activator
        user_workspace_skills_path = resolver.get_user_workspace_skills_path(
            user, binding
        )
        skill_discovery = SkillDiscovery(
            user_workspace_skills_path=user_workspace_skills_path,
            agent_package_path=agent_dir,
        )
        skill_activator = SkillActivator(discovery=skill_discovery)

        # 10. Activate initial skills from config
        if agent_package.config and agent_package.config.skills:
            for skill_name in agent_package.config.skills:
                skill_activator.activate_skill(skill_name, transient=False)

        # 11. Create resource resolver for skill resource tools
        skill_resource_resolver = ResourceResolver.from_activator(skill_activator)

        # 12. Load agent-local custom tools
        tool_builder = ToolRegistryBuilder()
        load_agent_tools(agent_dir, tool_builder)
        loaded_tool_catalog = tool_builder.build()

        # 13. Resolve tools (capability grant)
        if tools is None:
            tools = _resolve_tools(
                workspace,
                agent_package.config,
                loaded_tool_catalog,
                skill_resource_resolver,
                permission_policy,
            )
        else:
            for tool in tools:
                _apply_permission_policy(tool, permission_policy)

        # 14. Resolve sandbox config
        sandbox_config = _resolve_sandbox_config(agent_package.config)

        # 15. Setup storage
        storage_path = resolver.get_user_workspace_path(user, agent_package.name, binding)
        storage = FileStorage(config=FileStorageConfig(base_dir=storage_path))

        # 16. Setup compression (if configured)
        compression_policy = None
        compressor = None

        compression_config = (
            agent_package.config.compression
            if agent_package.config and agent_package.config.compression
            else None
        )

        if compression_config and compression_config.enabled:
            from quenda.host.compression_policy import DefaultCompressionPolicy
            from quenda.runtime.compressor import SummarizerCompressor

            compression_policy = DefaultCompressionPolicy(
                threshold_ratio=compression_config.threshold_ratio,
                keep_last_n_messages=compression_config.keep_last_n_messages,
                archive_raw_messages=compression_config.archive_raw_messages,
            )

            if compression_config.compression_model:
                try:
                    summary_model = registry.get_model(provider_name, compression_config.compression_model)
                except KeyError:
                    summary_model = model_instance
            else:
                summary_model = model_instance

            compressor = SummarizerCompressor(model=summary_model, storage=storage)

        return StableHostBinding(
            agent_package_path=agent_dir,
            workspace_path=workspace,
            workspace_id=workspace_id,
            user=user,
            provider_name=provider_name,
            model_name=model_name,
            model_instance=model_instance,
            vision_model_instance=vision_model_instance,
            capability_routing=capability_routing,
            tools=tools,
            sandbox_config=sandbox_config,
            compression_policy=compression_policy,
            compressor=compressor,
            storage=storage,
            active_skill_names=skill_activator.list_persistent(),
            transient_skill_names=skill_activator.list_transient(),
            loaded_tool_catalog=loaded_tool_catalog,
            agent_package=agent_package,
            skill_activator=skill_activator,
        )

    except Exception:
        return None


# =============================================================================
# Path B: Text Refresh (runs before each new run)
# =============================================================================


def refresh_run_context(
    binding: StableHostBinding,
    session_id: str = "",
) -> RunContextSnapshot:
    """
    Text refresh path - runs before each new run.

    This re-reads textual context sources:
    - AGENT.md content
    - Instruction files
    - Skill catalog
    - Active skill instructions

    Called at each turn boundary to pick up edits to text files.

    Args:
        binding: Stable capability bindings.
        session_id: Current session ID for template context.

    Returns:
        RunContextSnapshot with fresh text context.
    """
    # 1. Re-read agent package (fresh AGENT.md and instructions)
    agent_package = load_agent_package(binding.agent_package_path)

    # 2. Re-discover skills
    resolver = WorkspaceResolver()
    user_workspace_skills_path = resolver.get_user_workspace_skills_path(
        binding.user,
        WorkspaceResolver().resolve(binding.workspace_path),
    )

    skill_discovery = SkillDiscovery(
        user_workspace_skills_path=user_workspace_skills_path,
        agent_package_path=binding.agent_package_path,
    )
    discovered_skills = skill_discovery.discover_skills()

    # 3. Re-resolve active skills by name
    resolved_active_skills: list[SkillPackage] = []
    for skill_name in binding.active_skill_names + binding.transient_skill_names:
        skill = skill_discovery.get_skill(skill_name)
        if skill:
            resolved_active_skills.append(skill)

    # 4. Build template context
    template_context = TemplateContext(
        agent_name=agent_package.name,
        agent_version=agent_package.version,
        workspace_id=binding.workspace_id,
        workspace_path=str(binding.workspace_path),
        user_id=binding.user.id,
        model_provider=binding.provider_name,
        model_name=binding.model_name,
        date=datetime.now().strftime("%Y-%m-%d"),
        session_id=session_id,
    )

    # 5. Resolve instruction sources (includes discovered + active skills)
    instruction_sources = resolve_instruction_sources(
        agent_package_path=binding.agent_package_path,
        agent_name=agent_package.name,
        agent_md_content=agent_package.agent_md,
        agent_instructions=agent_package.instructions,
        workspace_path=binding.workspace_path,
        user=binding.user,
        discovered_skills=discovered_skills,
        active_skills=resolved_active_skills,
        include_skill_catalog=bool(
            agent_package.config and agent_package.config.include_skill_catalog
        ),
    )

    # 6. Compose prompt
    composer = InstructionComposer(template_context)
    composed_prompt = composer.compose(instruction_sources)

    return RunContextSnapshot(
        agent_md_content=agent_package.agent_md,
        instruction_sources=instruction_sources,
        composed_prompt=composed_prompt,
        discovered_skills=discovered_skills,
        resolved_active_skills=resolved_active_skills,
        template_context=template_context,
    )


# =============================================================================
# Legacy AgentSetup (maintained for backward compatibility)
# =============================================================================


@dataclass
class AgentSetup:
    """
    All resolved pieces for an agent setup.

    This is the result of setup_agent(), carrying everything
    needed to create the Agent and ContextRebuilder.

    **ADR-026 Migration**:
    This class now wraps StableHostBinding and RunContextSnapshot.
    Legacy fields are populated from these new structures for compatibility.
    """

    # New two-path model (ADR-026)
    binding: StableHostBinding
    context_snapshot: RunContextSnapshot

    # Legacy fields (populated from binding/snapshot for compatibility)
    agent: Agent
    agent_package: AgentPackage
    context_builder: ContextRebuilder
    provider_name: str
    model_name: str
    workspace_id: str
    instruction_sources: list[InstructionSource]
    user: User

    # ADR-015: Compression support
    compression_policy: CompressionPolicy | None = None
    compressor: Compressor | None = None

    # Skills support
    skill_discovery: SkillDiscovery | None = None
    skill_activator: SkillActivator | None = None

    # Workspace
    workspace_path: Path | None = None


def setup_agent(
    agent_path: Path,
    workspace: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    tools: list[Tool] | None = None,
    permission_policy: "PermissionPolicy" | None = None,
) -> AgentSetup | None:
    """
    Setup an agent from AGENT.md path.

    Implements ADR-026 Two-Path Reload Model:
    - Path A: Capability binding (setup_host_binding) - runs once
    - Path B: Text refresh (refresh_run_context) - runs before each run

    Legacy fields are populated for backward compatibility.

    This implements the Host resolution model (ADR-004):
    1. Resolve workspace binding (.quenda/workspace.yaml)
    2. Get user-agent-workspace storage path
    3. Setup storage with correct path hierarchy

    And ADR-007's instruction layer:
    1. Load agent package (AGENT.md + config.yaml + instructions/)
    2. Resolve workspace overlays
    3. Compose instructions

    Args:
        agent_path: Path to AGENT.md file or agent directory.
        workspace: Workspace directory for file operations.
        provider: Model provider override.
        model: Model name override.
        tools: Optional custom tools (default: core tools).

    Returns:
        AgentSetup with all resolved pieces, or None on error.
    """
    try:
        # =====================================================================
        # Path A: Capability Binding (runs once at setup)
        # =====================================================================
        binding = setup_host_binding(
            agent_path=agent_path,
            workspace=workspace,
            provider=provider,
            model=model,
            tools=tools,
            permission_policy=permission_policy,
        )
        if binding is None:
            return None

        # =====================================================================
        # Path B: Text Refresh (runs before each run)
        # =====================================================================
        context_snapshot = refresh_run_context(binding)

        # =====================================================================
        # Create Runtime Components
        # =====================================================================

        # Create Agent (public API)
        from quenda.runtime import Agent
        agent = Agent(
            name=binding.agent_package.name if binding.agent_package else "agent",
            system_prompt=context_snapshot.composed_prompt,
            tools=binding.tools,
            model=binding.model_instance,
            storage=binding.storage,
            compression_policy=binding.compression_policy,
            compressor=binding.compressor,
            vision_model=binding.vision_model_instance,
            capability_routing=binding.capability_routing,
        )

        # Create ContextRebuilder for runtime context rebuilding
        context_builder = ContextRebuilder(
            agent_name=binding.agent_package.name if binding.agent_package else "agent",
            agent_version=binding.agent_package.version if binding.agent_package else "0.1.0",
            agent_md_content=context_snapshot.agent_md_content,
            agent_instructions=binding.agent_package.instructions if binding.agent_package else {},
            agent_package_path=binding.agent_package_path,
            workspace_path=binding.workspace_path,
            workspace_id=binding.workspace_id,
            user=binding.user,
        )

        # Use skill components from binding (already initialized)
        skill_discovery = binding.skill_activator.discovery if binding.skill_activator else None
        skill_activator = binding.skill_activator

        # =====================================================================
        # Return AgentSetup (with both new and legacy fields)
        # =====================================================================
        return AgentSetup(
            # New two-path model
            binding=binding,
            context_snapshot=context_snapshot,
            # Legacy fields (for backward compatibility)
            agent=agent,
            agent_package=binding.agent_package,
            context_builder=context_builder,
            provider_name=binding.provider_name,
            model_name=binding.model_name,
            workspace_id=binding.workspace_id,
            instruction_sources=context_snapshot.instruction_sources,
            user=binding.user,
            compression_policy=binding.compression_policy,
            compressor=binding.compressor,
            skill_discovery=skill_discovery,
            skill_activator=skill_activator,
            workspace_path=binding.workspace_path,
        )

    except Exception:
        return None


__all__ = [
    # Two-path model (ADR-026)
    "StableHostBinding",
    "RunContextSnapshot",
    "setup_host_binding",
    "refresh_run_context",
    # Legacy API
    "AgentSetup",
    "setup_agent",
]
