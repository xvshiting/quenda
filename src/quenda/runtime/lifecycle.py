"""Code-owned catalog of Quenda lifecycle extension seams.

The registry describes contracts and ordering; it does not dispatch hooks.
Keeping discovery separate from execution lets tooling, documentation, and
Agents inspect the same lifecycle without granting or invoking extensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

LIFECYCLE_SCHEMA_VERSION = "quenda.lifecycle/v1"


class LifecycleStage(StrEnum):
    """Stable order of extension stages owned by Core and Host."""

    SETUP_REBIND = "setup_rebind"
    BEFORE_RUN = "before_run"
    COMPRESSION_CHECK = "compression_check"
    MEMORY_RETRIEVE = "memory_retrieve"
    CONTEXT_ASSEMBLY = "context_assembly"
    BEFORE_MODEL = "before_model"
    AFTER_MODEL = "after_model"
    BEFORE_TOOL_BATCH = "before_tool_batch"
    AROUND_TOOL_CALL = "around_tool_call"
    AFTER_TOOL_RESULT = "after_tool_result"
    LOOP_DECISION = "loop_decision"
    AFTER_RUN = "after_run"
    SESSION_IDLE_CLOSE = "session_idle_close"


class LifecycleStatus(StrEnum):
    """Whether a descriptor is executable today or reserves a future seam."""

    ACTIVE = "active"
    RESERVED = "reserved"


class FailureMode(StrEnum):
    """Failure semantics an implementation at the seam must preserve."""

    FAIL_CLOSED = "fail_closed"
    FAIL_RUN = "fail_run"
    ISOLATED = "isolated"


class CacheImpact(StrEnum):
    """Largest prompt-cache region an extension may invalidate."""

    NONE = "none"
    BINDING = "binding"
    SESSION = "session"
    ACTIVATION = "activation"
    DYNAMIC_TAIL = "dynamic_tail"


@dataclass(frozen=True)
class LifecycleDescriptor:
    """Public description of one lifecycle extension interface."""

    id: str
    stage: LifecycleStage
    kind: str
    contract: str
    registration: str
    owner: str
    order: int
    failure_mode: FailureMode
    mutation: str = "none"
    chooses_transition: bool = False
    cache_impact: CacheImpact = CacheImpact.NONE
    status: LifecycleStatus = LifecycleStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "stage": self.stage.value,
            "kind": self.kind,
            "contract": self.contract,
            "registration": self.registration,
            "owner": self.owner,
            "order": self.order,
            "failure_mode": self.failure_mode.value,
            "mutation": self.mutation,
            "chooses_transition": self.chooses_transition,
            "cache_impact": self.cache_impact.value,
            "status": self.status.value,
        }


_STAGE_ORDER = {stage: index for index, stage in enumerate(LifecycleStage)}


class LifecycleRegistry:
    """Deterministic registry used by runtime tooling and generated manifests."""

    def __init__(self) -> None:
        self._descriptors: dict[str, LifecycleDescriptor] = {}

    def register(self, descriptor: LifecycleDescriptor) -> None:
        if descriptor.id in self._descriptors:
            raise ValueError(f"Lifecycle extension {descriptor.id!r} already registered")
        self._descriptors[descriptor.id] = descriptor

    def get(self, extension_id: str) -> LifecycleDescriptor | None:
        return self._descriptors.get(extension_id)

    def list(self) -> tuple[LifecycleDescriptor, ...]:
        return tuple(sorted(
            self._descriptors.values(),
            key=lambda item: (_STAGE_ORDER[item.stage], item.order, item.id),
        ))

    def to_manifest(self) -> list[dict[str, object]]:
        return [descriptor.to_dict() for descriptor in self.list()]


def build_default_lifecycle_registry() -> LifecycleRegistry:
    """Build the canonical lifecycle catalog without importing extensions."""
    registry = LifecycleRegistry()
    descriptors = (
        LifecycleDescriptor(
            id="initializer",
            stage=LifecycleStage.SETUP_REBIND,
            kind="initializer",
            contract="quenda.host.extensions.AgentInitializer",
            registration="extensions/setup/*.py",
            owner="host",
            order=30,
            failure_mode=FailureMode.FAIL_CLOSED,
            mutation="binding",
            cache_impact=CacheImpact.BINDING,
        ),
        LifecycleDescriptor(
            id="before-run-context-refresh",
            stage=LifecycleStage.BEFORE_RUN,
            kind="resolver",
            contract="quenda.host.refresh_run_context",
            registration="host-default",
            owner="host",
            order=10,
            failure_mode=FailureMode.FAIL_RUN,
            mutation="prompt_snapshot",
            cache_impact=CacheImpact.SESSION,
        ),
        LifecycleDescriptor(
            id="compression-policy",
            stage=LifecycleStage.COMPRESSION_CHECK,
            kind="policy",
            contract="quenda.runtime.ports.CompressionPolicy",
            registration="Agent.compression_policy",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.FAIL_RUN,
            chooses_transition=True,
            cache_impact=CacheImpact.DYNAMIC_TAIL,
        ),
        LifecycleDescriptor(
            id="memory-retriever",
            stage=LifecycleStage.MEMORY_RETRIEVE,
            kind="provider",
            contract="quenda.runtime.Retriever",
            registration="future registry",
            owner="host",
            order=30,
            failure_mode=FailureMode.ISOLATED,
            mutation="prompt_overlay",
            cache_impact=CacheImpact.DYNAMIC_TAIL,
            status=LifecycleStatus.RESERVED,
        ),
        LifecycleDescriptor(
            id="context-provider",
            stage=LifecycleStage.CONTEXT_ASSEMBLY,
            kind="provider",
            contract="quenda.host.extensions.ContextProvider",
            registration="extensions/context/*.py",
            owner="host",
            order=40,
            failure_mode=FailureMode.FAIL_RUN,
            mutation="prompt_sources",
            cache_impact=CacheImpact.SESSION,
        ),
        LifecycleDescriptor(
            id="prompt-assembler",
            stage=LifecycleStage.CONTEXT_ASSEMBLY,
            kind="core-default",
            contract="quenda.host.PromptAssembler",
            registration="host-default",
            owner="host",
            order=90,
            failure_mode=FailureMode.FAIL_RUN,
            mutation="prompt_snapshot",
            cache_impact=CacheImpact.SESSION,
        ),
        LifecycleDescriptor(
            id="model-router",
            stage=LifecycleStage.BEFORE_MODEL,
            kind="router",
            contract="quenda.runtime.ModelRouter",
            registration="Agent capability routing",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.FAIL_CLOSED,
            chooses_transition=True,
        ),
        LifecycleDescriptor(
            id="verification-policy",
            stage=LifecycleStage.AFTER_MODEL,
            kind="policy",
            contract="quenda.runtime.VerificationPolicy",
            registration="future registry",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.FAIL_CLOSED,
            chooses_transition=True,
            cache_impact=CacheImpact.DYNAMIC_TAIL,
            status=LifecycleStatus.RESERVED,
        ),
        LifecycleDescriptor(
            id="tool-selection-policy",
            stage=LifecycleStage.BEFORE_TOOL_BATCH,
            kind="policy",
            contract="quenda.runtime.ToolSelectionPolicy",
            registration="extensions/policies/*.py",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.FAIL_CLOSED,
            chooses_transition=True,
        ),
        LifecycleDescriptor(
            id="permission-policy",
            stage=LifecycleStage.AROUND_TOOL_CALL,
            kind="policy",
            contract="quenda.runtime.PermissionPolicy",
            registration="Host setup",
            owner="host",
            order=10,
            failure_mode=FailureMode.FAIL_CLOSED,
            chooses_transition=True,
        ),
        LifecycleDescriptor(
            id="tool-result-processing-policy",
            stage=LifecycleStage.AFTER_TOOL_RESULT,
            kind="policy",
            contract="quenda.runtime.ToolResultProcessingPolicy",
            registration="extensions/policies/*.py",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.ISOLATED,
            mutation="model_result_view",
            cache_impact=CacheImpact.DYNAMIC_TAIL,
        ),
        LifecycleDescriptor(
            id="termination-policy",
            stage=LifecycleStage.LOOP_DECISION,
            kind="policy",
            contract="quenda.runtime.TerminationPolicy",
            registration="extensions/policies/*.py",
            owner="runtime",
            order=30,
            failure_mode=FailureMode.FAIL_RUN,
            chooses_transition=True,
        ),
        LifecycleDescriptor(
            id="trace-sink",
            stage=LifecycleStage.AFTER_RUN,
            kind="observer",
            contract="quenda.runtime.TraceSink",
            registration="Run.trace_sink",
            owner="runtime",
            order=90,
            failure_mode=FailureMode.ISOLATED,
        ),
        LifecycleDescriptor(
            id="evolution-policy",
            stage=LifecycleStage.AFTER_RUN,
            kind="maintenance-policy",
            contract="quenda.runtime.ports.AfterRunHandler",
            registration="Agent.after_run_handler / config.yaml evolution",
            owner="host",
            order=40,
            failure_mode=FailureMode.ISOLATED,
            mutation="staged_writes",
        ),
        LifecycleDescriptor(
            id="session-maintenance-policy",
            stage=LifecycleStage.SESSION_IDLE_CLOSE,
            kind="maintenance-policy",
            contract="quenda.evolution.MaintenancePolicy",
            registration="future registry",
            owner="host",
            order=30,
            failure_mode=FailureMode.ISOLATED,
            mutation="staged_writes",
            status=LifecycleStatus.RESERVED,
        ),
    )
    for descriptor in descriptors:
        registry.register(descriptor)
    return registry


__all__ = [
    "CacheImpact",
    "FailureMode",
    "LIFECYCLE_SCHEMA_VERSION",
    "LifecycleDescriptor",
    "LifecycleRegistry",
    "LifecycleStage",
    "LifecycleStatus",
    "build_default_lifecycle_registry",
]
