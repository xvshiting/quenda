"""
Host layer for Quenda.

The host layer manages persistence, file system access, identity, and resources.
"""

from quenda.host.loader import (
    ThemeConfig,
    AgentConfigYaml,
    AgentPackage,
    load_agent_from_markdown,
    load_agent_package,
    load_agent_commands,
    load_agent_interactions,
    find_builtin_agent,
)
from quenda.host.storage import (
    FileStorage,
    FileStorageConfig,
    RunState,
    Storage,
)
from quenda.host.identity import (
    User,
    IdentityResolver,
    EnvIdentityResolver,
    StaticIdentityResolver,
    DefaultUserResolver,
)
from quenda.host.workspace import (
    WorkspaceBinding,
    WorkspaceResolver,
)
from quenda.host.permission import (
    Permission,
    PermissionDeniedError,
    PermissionPolicy,
    HostPermissionPolicy,
    PermissivePolicy,
    CompositePolicy,
    create_default_policy,
)
from quenda.host.policy_registry import (
    LoadedPolicyCatalog,
    NamedPolicySpec,
    PolicyRegistryBuilder,
)
from quenda.host.instructions import (
    InstructionScope,
    InstructionSource,
    TemplateContext,
    InstructionComposer,
    resolve_instruction_sources,
)
from quenda.host.commands import (
    CommandCandidate,
    CommandResolution,
    CommandResult,
    CommandContext,
    CommandRegistry,
    create_default_registry,
    HelpCommand,
    ClearCommand,
    ExitCommand,
    SessionCommand,
    ModelCommand,
    ModeCommand,
    ContextCommand,
    ResetCommand,
    ReplAction,
    VALID_MODES,
)
from quenda.host.interactions import (
    InteractionKind,
    InteractionOption,
    InteractionRequest,
    InteractionResponse,
    InteractionContext,
    Interaction,
    InteractionRegistry,
    ChoiceInteraction,
    ConfirmInteraction,
    InputInteraction,
    MenuInteraction,
    create_default_registry as create_default_interaction_registry,
)
from quenda.host.context import (
    ContextRebuilder,
)
from quenda.host.repl import (
    ReplState,
    ReplRuntime,
)
from quenda.host.phases import (
    FollowupPhaseDecision,
    FollowupPhaseResult,
    run_followup_phases,
)
from quenda.host.runner import (
    # Two-path model (ADR-026)
    StableHostBinding,
    RunContextSnapshot,
    setup_host_binding,
    refresh_run_context,
    connect_mcp_servers,
    # Legacy API
    AgentSetup,
    create_skill_activation_handler,
    run_agent_once,
    setup_agent,
)
from quenda.host.skill import (
    SkillActivationResolution,
    extract_skill_activation_requests,
    build_skill_activation_followup,
    resolve_skill_activation_requests,
)

__all__ = [
    # Agent loading
    "load_agent_from_markdown",
    "load_agent_package",
    "load_agent_commands",
    "load_agent_interactions",
    "find_builtin_agent",
    "ThemeConfig",
    "AgentConfigYaml",
    "AgentPackage",
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
    # Runner - Legacy API
    "AgentSetup",
    "create_skill_activation_handler",
    "run_agent_once",
    "setup_agent",
]
