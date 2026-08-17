"""
Host layer for Quenda.

The host layer manages persistence, file system access, identity, and resources.
"""

from quenda.host.agent_home import AgentHome, AgentHomeManager
from quenda.host.commands import (
    VALID_MODES,
    ClearCommand,
    CommandCandidate,
    CommandContext,
    CommandRegistry,
    CommandResolution,
    CommandResult,
    ContextCommand,
    ExitCommand,
    HelpCommand,
    ModeCommand,
    ModelCommand,
    ReplAction,
    ResetCommand,
    SessionCommand,
    create_default_registry,
)
from quenda.host.config_inspection import (
    CONFIG_INSPECTION_SCHEMA_VERSION,
    AgentConfigInspector,
)
from quenda.host.config_mutation import (
    AgentConfigEditor,
    AgentConfigMutationResult,
)
from quenda.host.context import (
    ContextRebuilder,
)
from quenda.host.extensions import (
    AgentExtensionContext,
    AgentInitializer,
    AgentInitializerRegistry,
    ContextProvider,
    ContextProviderRegistry,
    ContextProviderRequest,
)
from quenda.host.identity import (
    DefaultUserResolver,
    EnvIdentityResolver,
    IdentityResolver,
    StaticIdentityResolver,
    User,
)
from quenda.host.instructions import (
    InstructionComposer,
    InstructionScope,
    InstructionSource,
    TemplateContext,
    resolve_instruction_sources,
)
from quenda.host.interactions import (
    ChoiceInteraction,
    ConfirmInteraction,
    InputInteraction,
    Interaction,
    InteractionContext,
    InteractionKind,
    InteractionOption,
    InteractionRegistry,
    InteractionRequest,
    InteractionResponse,
    MenuInteraction,
)
from quenda.host.interactions import (
    create_default_registry as create_default_interaction_registry,
)
from quenda.host.loader import (
    AgentConfigYaml,
    AgentPackage,
    ThemeConfig,
    find_builtin_agent,
    load_agent_commands,
    load_agent_context_providers,
    load_agent_from_markdown,
    load_agent_initializers,
    load_agent_interactions,
    load_agent_package,
)
from quenda.host.permission import (
    CompositePolicy,
    HostPermissionPolicy,
    Permission,
    PermissionDeniedError,
    PermissionPolicy,
    PermissivePolicy,
    create_default_policy,
)
from quenda.host.phases import (
    FollowupPhaseDecision,
    FollowupPhaseResult,
    run_followup_phases,
)
from quenda.host.policy_registry import (
    LoadedPolicyCatalog,
    NamedPolicySpec,
    PolicyRegistryBuilder,
)
from quenda.host.prompt import (
    PromptAssembler,
    PromptAssembly,
    PromptCacheObservation,
    PromptChangeReason,
    PromptInvalidation,
    PromptResidency,
    PromptSegment,
    PromptTrust,
    build_prompt_cache_event,
)
from quenda.host.repl import (
    ReplRuntime,
    ReplState,
)
from quenda.host.runner import (
    # Legacy API
    AgentSetup,
    RunContextSnapshot,
    # Two-path model (ADR-026)
    StableHostBinding,
    advance_skill_activation_epoch,
    connect_mcp_servers,
    create_skill_activation_handler,
    refresh_run_context,
    run_agent_once,
    setup_agent,
    setup_host_binding,
)
from quenda.host.service import (
    ActiveRun,
    HostService,
)
from quenda.host.service_types import (
    ContextInfo,
    ContextSource,
    CreateSessionRequest,
    EventEnvelope,
    InteractionResponseRequest,
    InterruptRequest,
    MemoryFile,
    MemorySearchRequest,
    MemorySearchResult,
    PermissionDecisionRequest,
    RequestContext,
    RunHandle,
    RunStatus,
    SessionInfo,
    SessionList,
    StartRunRequest,
)
from quenda.host.skill import (
    SkillActivationResolution,
    build_skill_activation_followup,
    extract_skill_activation_requests,
    resolve_skill_activation_requests,
)
from quenda.host.skill_evolution import SkillEvolutionManager
from quenda.host.storage import (
    FileStorage,
    FileStorageConfig,
    RunState,
    Storage,
)
from quenda.host.validation import (
    VALIDATION_SCHEMA_VERSION,
    ValidationDiagnostic,
    ValidationReport,
    validate_agent_configuration,
    validate_agent_package,
)
from quenda.host.workspace import (
    WorkspaceBinding,
    WorkspaceResolver,
)

__all__ = [
    # Agent loading
    "load_agent_from_markdown",
    "load_agent_package",
    "load_agent_commands",
    "load_agent_interactions",
    "load_agent_context_providers",
    "load_agent_initializers",
    "find_builtin_agent",
    "ThemeConfig",
    "AgentConfigYaml",
    "AgentPackage",
    "AgentHome",
    "AgentHomeManager",
    # Storage
    "Storage",
    "FileStorage",
    "FileStorageConfig",
    "RunState",
    # Identity
    "User",
    "IdentityResolver",
    "EnvIdentityResolver",
    "StaticIdentityResolver",
    "DefaultUserResolver",
    # Workspace
    "WorkspaceBinding",
    "WorkspaceResolver",
    # Permission
    "Permission",
    "PermissionDeniedError",
    "PermissionPolicy",
    "HostPermissionPolicy",
    "PermissivePolicy",
    "CompositePolicy",
    "create_default_policy",
    # Policy registry
    "LoadedPolicyCatalog",
    "NamedPolicySpec",
    "PolicyRegistryBuilder",
    # Instructions
    "InstructionScope",
    "InstructionSource",
    "TemplateContext",
    "InstructionComposer",
    "resolve_instruction_sources",
    # Commands
    "CommandCandidate",
    "CommandResolution",
    "CommandResult",
    "CommandContext",
    "CommandRegistry",
    "create_default_registry",
    "HelpCommand",
    "ClearCommand",
    "ExitCommand",
    "SessionCommand",
    "ModelCommand",
    "ModeCommand",
    "ContextCommand",
    "ResetCommand",
    "ReplAction",
    "VALID_MODES",
    # Interactions
    "InteractionKind",
    "InteractionOption",
    "InteractionRequest",
    "InteractionResponse",
    "InteractionContext",
    "Interaction",
    "InteractionRegistry",
    "ChoiceInteraction",
    "ConfirmInteraction",
    "InputInteraction",
    "MenuInteraction",
    "create_default_interaction_registry",
    # Context
    "ContextRebuilder",
    "PromptAssembler",
    "PromptAssembly",
    "PromptCacheObservation",
    "PromptChangeReason",
    "PromptInvalidation",
    "PromptResidency",
    "PromptSegment",
    "PromptTrust",
    "build_prompt_cache_event",
    "AgentExtensionContext",
    "AgentInitializer",
    "AgentInitializerRegistry",
    "ContextProvider",
    "ContextProviderRegistry",
    "ContextProviderRequest",
    # REPL
    "ReplState",
    "ReplRuntime",
    # Follow-up phases
    "FollowupPhaseDecision",
    "FollowupPhaseResult",
    "run_followup_phases",
    # Skill routing
    "SkillActivationResolution",
    "extract_skill_activation_requests",
    "build_skill_activation_followup",
    "resolve_skill_activation_requests",
    # Runner - Two-path model (ADR-026)
    "StableHostBinding",
    "RunContextSnapshot",
    "setup_host_binding",
    "refresh_run_context",
    "connect_mcp_servers",
    "advance_skill_activation_epoch",
    # Runner - Legacy API
    "AgentSetup",
    "create_skill_activation_handler",
    "run_agent_once",
    "setup_agent",
    # HostService (ADR-032)
    "HostService",
    "ActiveRun",
    # Agent package validation
    "VALIDATION_SCHEMA_VERSION",
    "ValidationDiagnostic",
    "ValidationReport",
    "validate_agent_configuration",
    "validate_agent_package",
    "AgentConfigEditor",
    "AgentConfigMutationResult",
    "CONFIG_INSPECTION_SCHEMA_VERSION",
    "AgentConfigInspector",
    "SkillEvolutionManager",
    # Service types (ADR-032)
    "CreateSessionRequest",
    "SessionInfo",
    "SessionList",
    "RunStatus",
    "StartRunRequest",
    "RunHandle",
    "EventEnvelope",
    "InteractionResponseRequest",
    "PermissionDecisionRequest",
    "InterruptRequest",
    "ContextSource",
    "ContextInfo",
    "MemorySearchRequest",
    "MemorySearchResult",
    "MemoryFile",
    "RequestContext",
]
