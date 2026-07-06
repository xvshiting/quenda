"""
Permission request and decision models.

Implements a runtime permission system for operations that require
explicit user consent, such as:
- Accessing files outside workspace
- Writing to sensitive locations
- Executing potentially dangerous commands

Design principles:
- Path-level granularity (most secure)
- Session-level lifetime (requires re-approval after restart)
- Independent semantic model from InteractionRequest
- Reuse InteractionRequest UI layer for user prompts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol, runtime_checkable


class PermissionKind(str, Enum):
    """Types of permission requests."""

    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    SHELL_EXECUTE = "shell.execute"
    NETWORK_ACCESS = "network.access"


class PermissionScope(str, Enum):
    """Granularity of permission."""

    PATH = "path"  # Single file/directory
    DIRECTORY = "directory"  # All files under a directory
    PATTERN = "pattern"  # Glob pattern (future)
    ALL = "all"  # Entire capability for the session


class PermissionLifetime(str, Enum):
    """How long a permission grant is valid."""

    RUN = "run"  # Current run only
    SESSION = "session"  # Until session ends
    ALWAYS = "always"  # Persist to workspace config (future, not MVP)


@dataclass(frozen=True)
class PermissionRequest:
    """
    A request for permission to perform an operation.

    This is an independent semantic model for security decisions.
    The UI layer can reuse InteractionRequest for rendering, but
    permission semantics are kept separate.

    Attributes:
        kind: Type of permission being requested.
        resource: The resource being accessed (e.g., file path, URL).
        scope: Granularity of the permission.
        reason: Human-readable explanation of why this is needed.
        lifetime: Requested validity period.
        tool_name: Name of the tool making the request.
        tool_args: Arguments passed to the tool (for context).
    """

    kind: PermissionKind
    resource: str
    scope: PermissionScope = PermissionScope.PATH
    reason: str = ""
    lifetime: PermissionLifetime = PermissionLifetime.SESSION
    tool_name: str = ""
    tool_args: dict[str, object] = field(default_factory=dict)
    source: Literal["agent_initiated", "user_provided"] = "agent_initiated"

    def to_dict(self) -> dict[str, object]:
        """Serialize the request to a JSON-safe dictionary."""
        return {
            "kind": self.kind.value,
            "resource": self.resource,
            "scope": self.scope.value,
            "reason": self.reason,
            "lifetime": self.lifetime.value,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PermissionRequest":
        """Deserialize a request from a dictionary."""
        return cls(
            kind=PermissionKind(str(data["kind"])),
            resource=str(data["resource"]),
            scope=PermissionScope(str(data.get("scope", PermissionScope.PATH.value))),
            reason=str(data.get("reason", "")),
            lifetime=PermissionLifetime(str(data.get("lifetime", PermissionLifetime.SESSION.value))),
            tool_name=str(data.get("tool_name", "")),
            tool_args=dict(data.get("tool_args", {}) or {}),
            source=str(data.get("source", "agent_initiated")),
        )

    def to_interaction_prompt(self) -> str:
        """Generate a human-readable prompt for the user."""
        action_desc = {
            PermissionKind.FILESYSTEM_READ: "read",
            PermissionKind.FILESYSTEM_WRITE: "write to",
            PermissionKind.FILESYSTEM_DELETE: "delete",
            PermissionKind.SHELL_EXECUTE: "execute command in",
            PermissionKind.NETWORK_ACCESS: "access",
        }.get(self.kind, "access")

        return (
            f"Agent requests permission to {action_desc}:\n"
            f"  {self.resource}\n\n"
            f"Reason: {self.reason or 'Not specified'}\n\n"
            f"Source: {self.source}\n\n"
            f"Scope: {self.scope.value}-level\n"
            f"Valid for: {self.lifetime.value}"
        )


class PermissionRequiredError(Exception):
    """
    Raised by tools when an operation requires explicit permission.

    This is a signal to the Run layer to:
    1. Check the permission cache
    2. If not cached, prompt the user
    3. If allowed, retry the tool call
    4. If denied, return an error result

    Attributes:
        request: The permission request that needs approval.
    """

    def __init__(self, request: PermissionRequest) -> None:
        self.request = request
        super().__init__(
            f"Permission required: {request.kind.value} on {request.resource}"
        )


@dataclass(frozen=True)
class PermissionDecision:
    """
    A decision on a permission request.

    Attributes:
        request: The original request.
        allowed: Whether the permission was granted.
        scope: Actual scope of the grant (may differ from request).
        lifetime: Actual lifetime of the grant.
        reason: Reason for denial (if denied).
    """

    request: PermissionRequest
    allowed: bool
    scope: PermissionScope = PermissionScope.PATH
    lifetime: PermissionLifetime = PermissionLifetime.SESSION
    reason: str = ""

    def cache_key(self) -> str:
        """Generate a cache key for this decision."""
        if self.scope == PermissionScope.ALL:
            return f"{self.request.kind.value}:*:{self.scope.value}"
        return f"{self.request.kind.value}:{self.request.resource}:{self.scope.value}"

    def to_dict(self) -> dict[str, object]:
        """Serialize the decision to a JSON-safe dictionary."""
        return {
            "request": self.request.to_dict(),
            "allowed": self.allowed,
            "scope": self.scope.value,
            "lifetime": self.lifetime.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PermissionDecision":
        """Deserialize a decision from a dictionary."""
        request = PermissionRequest.from_dict(dict(data["request"]))
        return cls(
            request=request,
            allowed=bool(data["allowed"]),
            scope=PermissionScope(str(data.get("scope", request.scope.value))),
            lifetime=PermissionLifetime(str(data.get("lifetime", request.lifetime.value))),
            reason=str(data.get("reason", "")),
        )


@runtime_checkable
class PermissionPolicy(Protocol):
    """
    Protocol for permission policies.

    A policy receives a permission request and returns a decision.
    Host layers can implement this as an interactive prompt, an allowlist,
    a deny-all policy, or any other environment-specific policy.
    """

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        """Return a permission decision for the request."""
        ...


@dataclass(frozen=True)
class DenyPermissionPolicy:
    """Policy that denies every permission request."""

    reason: str = "Access denied - permission requests are disabled"

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        return PermissionDecision(
            request=request,
            allowed=False,
            reason=self.reason,
        )


@dataclass(frozen=True)
class AllowPermissionPolicy:
    """Policy that approves every permission request."""

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        return PermissionDecision(
            request=request,
            allowed=True,
            scope=request.scope,
            lifetime=request.lifetime,
            reason="",
        )


@dataclass
class PermissionCache:
    """
    Session-level cache of permission decisions.

    Stores granted permissions to avoid repeated prompts
    for the same resource within a session.

    Attributes:
        decisions: Map of cache_key -> PermissionDecision.
    """

    decisions: dict[str, PermissionDecision] = field(default_factory=dict)

    @staticmethod
    def _normalize_path(resource: str) -> str:
        """Normalize a path-like resource."""
        from pathlib import Path

        try:
            return str(Path(resource).expanduser().resolve())
        except Exception:
            return resource

    @staticmethod
    def _is_under_directory(resource: str, directory: str) -> bool:
        """Return True when resource is inside directory."""
        from pathlib import Path

        try:
            resource_path = Path(resource).resolve()
            directory_path = Path(directory).resolve()
            resource_path.relative_to(directory_path)
            return True
        except Exception:
            return False

    def check(
        self,
        kind: PermissionKind,
        resource: str,
        scope: PermissionScope = PermissionScope.PATH,
    ) -> PermissionDecision | None:
        """
        Check if a permission has already been granted.

        Args:
            kind: Permission type.
            resource: Resource path.
            scope: Permission scope.

        Returns:
            The cached decision if found, None otherwise.
        """
        normalized = self._normalize_path(resource)

        if scope == PermissionScope.ALL:
            key = f"{kind.value}:*:{scope.value}"
            cached = self.decisions.get(key)
            if cached is not None:
                return cached
        else:
            key = f"{kind.value}:{normalized}:{scope.value}"
            cached = self.decisions.get(key)
            if cached is not None:
                return cached

        for decision in self.decisions.values():
            if decision.request.kind != kind or not decision.allowed:
                continue

            if decision.scope == PermissionScope.ALL:
                return decision

            if decision.scope == PermissionScope.DIRECTORY:
                grant_root = self._normalize_path(decision.request.resource)
                if self._is_under_directory(normalized, grant_root) or normalized == grant_root:
                    return decision

            if decision.scope == PermissionScope.PATH and normalized == self._normalize_path(decision.request.resource):
                return decision

        return None

    def grant(self, decision: PermissionDecision) -> None:
        """
        Store a granted permission.

        Args:
            decision: The permission decision to cache.
        """
        normalized = self._normalize_path(decision.request.resource)

        if decision.scope == PermissionScope.ALL:
            key = f"{decision.request.kind.value}:*:{decision.scope.value}"
        elif decision.scope == PermissionScope.DIRECTORY:
            key = f"{decision.request.kind.value}:{normalized}:{decision.scope.value}"
        else:
            key = f"{decision.request.kind.value}:{normalized}:{decision.scope.value}"
        self.decisions[key] = decision

    def clear(self) -> None:
        """Clear all cached permissions."""
        self.decisions.clear()

    def to_dict(self) -> dict[str, object]:
        """Serialize cached permissions to a JSON-safe dictionary."""
        return {
            "decisions": {
                key: decision.to_dict()
                for key, decision in self.decisions.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PermissionCache":
        """Deserialize cached permissions from a dictionary."""
        cache = cls()
        decisions = data.get("decisions", {})
        if isinstance(decisions, dict):
            for key, value in decisions.items():
                if isinstance(value, dict):
                    try:
                        cache.decisions[str(key)] = PermissionDecision.from_dict(value)
                    except Exception:
                        continue
        return cache


__all__ = [
    "PermissionKind",
    "PermissionScope",
    "PermissionLifetime",
    "PermissionRequest",
    "PermissionRequiredError",
    "PermissionDecision",
    "PermissionCache",
    "PermissionPolicy",
    "DenyPermissionPolicy",
    "AllowPermissionPolicy",
]
