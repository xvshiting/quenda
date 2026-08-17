"""
Permission manager for handling runtime permission requests.

This module bridges the semantic PermissionRequest model with the
InteractionRequest UI layer, allowing agents to request permissions
through a consistent user experience.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from quenda.runtime.permission import (
    DenyPermissionPolicy,
    PermissionCache,
    PermissionDecision,
    PermissionKind,
    PermissionLifetime,
    PermissionPolicy,
    PermissionRequest,
    PermissionScope,
    PermissionSource,
)


@dataclass
class HostManagedPermissionPolicy:
    """Allow Host-declared resources, then defer every other decision."""

    delegate: PermissionPolicy = field(default_factory=DenyPermissionPolicy)
    grants: PermissionManager = field(default_factory=lambda: PermissionManager())

    def grant_host_managed_resource(
        self,
        resource: str,
        *,
        kind: PermissionKind = PermissionKind.FILESYSTEM_READ,
        scope: PermissionScope = PermissionScope.DIRECTORY,
        lifetime: PermissionLifetime = PermissionLifetime.SESSION,
        tool_name: str = "",
        reason: str = "Host-managed trusted resource",
    ) -> PermissionDecision:
        """Register one non-interactive Host trust root."""
        return self.grants.grant_host_managed_resource(
            resource,
            kind=kind,
            scope=scope,
            lifetime=lifetime,
            tool_name=tool_name,
            reason=reason,
        )

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        """Resolve Host grants before consulting the caller's policy."""
        cached = self.grants.check_cached(
            request.kind,
            request.resource,
            request.scope,
        )
        if cached is not None:
            return cached
        return self.delegate.decide(request)


def with_host_managed_permissions(
    policy: PermissionPolicy | None,
) -> PermissionPolicy:
    """Return a policy capable of carrying non-interactive Host grants."""
    if isinstance(policy, (PermissionManager, HostManagedPermissionPolicy)):
        return policy
    return HostManagedPermissionPolicy(delegate=policy or DenyPermissionPolicy())


@dataclass
class PermissionManager:
    """
    Manages runtime permission requests and decisions.

    Responsibilities:
    - Maintain session-level permission cache
    - Check cached permissions before prompting
    - Generate user prompts for permission requests
    - Store granted permissions in cache

    Usage:
        manager = PermissionManager(cache)

        # Check cache first
        decision = manager.check_cached(request)
        if decision:
            return decision

        # Prompt user
        decision = await manager.request_permission(request, interaction_registry)
        return decision
    """

    cache: PermissionCache = field(default_factory=PermissionCache)

    # Handler for permission prompts (injected by Host layer)
    # Returns True if allowed, False if denied
    prompt_handler: Callable[[PermissionRequest], bool] | None = None

    def check_cached(
        self,
        kind: PermissionKind,
        resource: str,
        scope: PermissionScope = PermissionScope.PATH,
    ) -> PermissionDecision | None:
        """
        Check if permission has already been granted.

        Args:
            kind: Permission type.
            resource: Resource path.
            scope: Permission scope.

        Returns:
            Cached decision if found, None otherwise.
        """
        # Normalize the resource path
        try:
            normalized = str(Path(resource).resolve())
        except Exception:
            normalized = resource

        return self.cache.check(kind, normalized, scope)

    def request_permission(
        self,
        request: PermissionRequest,
    ) -> PermissionDecision:
        """
        Process a permission request.

        First checks the cache. If not found, prompts the user
        (via prompt_handler) and caches the result.

        Args:
            request: The permission request.

        Returns:
            The permission decision.
        """
        # Check cache first
        if request.cacheable:
            cached = self.cache.check(request.kind, request.resource, request.scope)
            if cached:
                return cached

        # No cached permission, need to prompt
        if self.prompt_handler is None:
            # No handler configured, default deny
            return PermissionDecision(
                request=request,
                allowed=False,
                reason="Access denied - no permission handler configured",
            )

        # Prompt user
        allowed = self.prompt_handler(request)

        decision = PermissionDecision(
            request=request,
            allowed=allowed,
            scope=request.scope,
            lifetime=request.lifetime,
            reason="" if allowed else "Denied by user",
        )

        # Cache if allowed
        if allowed and request.cacheable:
            self.cache.grant(decision)

        return decision

    def grant_user_provided_resource(
        self,
        resource: str,
        *,
        kind: PermissionKind = PermissionKind.FILESYSTEM_READ,
        scope: PermissionScope = PermissionScope.DIRECTORY,
        lifetime: PermissionLifetime = PermissionLifetime.SESSION,
        tool_name: str = "",
    ) -> PermissionDecision:
        """
        Mark a resource as explicitly provided by the user.

        This is an explicit grant, not a prompt-driven approval. It is used
        for paths the user directly supplied in REPL input.
        """
        return self._grant_resource(
            resource,
            kind=kind,
            scope=scope,
            lifetime=lifetime,
            tool_name=tool_name,
            reason="User provided resource",
            source="user_provided",
        )

    def grant_host_managed_resource(
        self,
        resource: str,
        *,
        kind: PermissionKind = PermissionKind.FILESYSTEM_READ,
        scope: PermissionScope = PermissionScope.DIRECTORY,
        lifetime: PermissionLifetime = PermissionLifetime.SESSION,
        tool_name: str = "",
        reason: str = "Host-managed trusted resource",
    ) -> PermissionDecision:
        """Grant narrowly scoped access to a resource trusted by the Host."""
        return self._grant_resource(
            resource,
            kind=kind,
            scope=scope,
            lifetime=lifetime,
            tool_name=tool_name,
            reason=reason,
            source="host_managed",
        )

    def _grant_resource(
        self,
        resource: str,
        *,
        kind: PermissionKind,
        scope: PermissionScope,
        lifetime: PermissionLifetime,
        tool_name: str,
        reason: str,
        source: PermissionSource,
    ) -> PermissionDecision:
        """Create and cache an explicit non-interactive permission grant."""
        normalized_resource = resource
        if scope == PermissionScope.DIRECTORY:
            try:
                path = Path(resource).expanduser()
                if path.exists() and path.is_file():
                    normalized_resource = str(path.parent.resolve())
                elif path.exists() and path.is_dir():
                    normalized_resource = str(path.resolve())
                else:
                    normalized_resource = str((path.parent if path.suffix else path).resolve())
            except Exception:
                normalized_resource = resource

        request = PermissionRequest(
            kind=kind,
            resource=normalized_resource,
            scope=scope,
            reason=reason,
            lifetime=lifetime,
            tool_name=tool_name,
            source=source,
        )
        decision = PermissionDecision(
            request=request,
            allowed=True,
            scope=scope,
            lifetime=lifetime,
            reason=reason,
        )
        self.cache.grant(decision)
        return decision

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        """Alias that lets PermissionManager act like a PermissionPolicy."""
        return self.request_permission(request)

    def clear_cache(self) -> None:
        """Clear all cached permissions."""
        self.cache.clear()

    def to_state(self) -> dict[str, object]:
        """Serialize user decisions, excluding recomputable Host-managed grants."""
        state = self.cache.to_dict()
        decisions = state.get("decisions")
        if isinstance(decisions, dict):
            state["decisions"] = {
                key: value
                for key, value in decisions.items()
                if not (
                    isinstance(value, dict)
                    and isinstance(value.get("request"), dict)
                    and value["request"].get("source") == "host_managed"
                )
            }
        return state

    def load_state(self, state: dict[str, object] | None) -> None:
        """Merge persisted user decisions with current Host-managed grants."""
        if not state:
            return
        restored = PermissionCache.from_dict(state)
        self.cache.decisions.update(restored.decisions)


def format_permission_prompt(request: PermissionRequest) -> str:
    """
    Format a permission request as a user-friendly prompt.

    This can be used by the UI layer to display the request.

    Args:
        request: The permission request.

    Returns:
        Formatted prompt string.
    """
    action_desc = {
        PermissionKind.FILESYSTEM_READ: "read file",
        PermissionKind.FILESYSTEM_WRITE: "write to file",
        PermissionKind.FILESYSTEM_DELETE: "delete file",
        PermissionKind.SHELL_EXECUTE: "execute shell command",
        PermissionKind.NETWORK_ACCESS: "access network",
        PermissionKind.AGENT_CONFIG_WRITE: "change Agent configuration",
        PermissionKind.SKILL_EVOLUTION_WRITE: "activate Skill revision",
    }.get(request.kind, "access")

    lines = [
        f"[Permission Request] {action_desc}",
        f"  Target: {request.resource}",
    ]

    if request.reason:
        lines.append(f"  Reason: {request.reason}")

    if request.tool_name:
        lines.append(f"  Tool: {request.tool_name}")

    lines.extend([
        f"  Scope: {request.scope.value}",
        f"  Valid for: {request.lifetime.value}",
    ])

    return "\n".join(lines)


__all__ = [
    "PermissionManager",
    "format_permission_prompt",
]
