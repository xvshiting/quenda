"""
Permission control for Kora Host layer.

Provides permission policies to protect Host-owned metadata and resources.

Core protection:
- Host-owned files (workspace.yaml) cannot be modified by Agents
- Workspace boundaries cannot be crossed
- Future: Skill permissions, tool access control
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kora.host.workspace import WorkspaceResolver


class Permission(Enum):
    """Permission types for operations."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


class PermissionDeniedError(Exception):
    """Raised when an operation is denied by permission policy."""

    def __init__(self, path: Path, permission: Permission, reason: str) -> None:
        self.path = path
        self.permission = permission
        self.reason = reason
        super().__init__(f"Permission denied: {permission.value} on {path}. {reason}")


class PermissionPolicy(Protocol):
    """
    Protocol for permission policies.

    Implementations define what operations are allowed on what resources.
    """

    def check(self, path: Path, permission: Permission) -> bool:
        """
        Check if an operation is allowed on a path.

        Args:
            path: The path to check.
            permission: The permission type.

        Returns:
            True if allowed, False if denied.
        """
        ...

    def require(self, path: Path, permission: Permission) -> None:
        """
        Require an operation to be allowed, raising if not.

        Args:
            path: The path to check.
            permission: The permission type.

        Raises:
            PermissionDeniedError: If the operation is not allowed.
        """
        ...


@dataclass
class HostPermissionPolicy:
    """
    Permission policy that protects Host-owned resources.

    This policy enforces:
    - Host-owned metadata cannot be modified by Agents
    - Operations must stay within workspace boundaries
    - Dangerous operations outside workspace are denied

    Usage:
        policy = HostPermissionPolicy(workspace_resolver, workspace_path)
        policy.require(path, Permission.WRITE)  # Raises if denied
    """

    workspace_resolver: WorkspaceResolver
    workspace_path: Path
    allow_outside_workspace: bool = field(default=False)

    def check(self, path: Path, permission: Permission) -> bool:
        """
        Check if an operation is allowed on a path.

        Args:
            path: The path to check.
            permission: The permission type.

        Returns:
            True if allowed, False if denied.
        """
        resolved_path = path.resolve()
        workspace_root = self.workspace_path.resolve()

        # Check if path is within workspace
        try:
            relative = resolved_path.relative_to(workspace_root)
        except ValueError:
            # Path is outside workspace
            if not self.allow_outside_workspace:
                return False
            # Outside but allowed - still check protected paths
            return True

        # Check for protected paths
        if self.workspace_resolver.is_protected_path(resolved_path, workspace_root):
            # Protected paths can only be read, not written/deleted
            if permission in (Permission.WRITE, Permission.DELETE):
                return False

        return True

    def require(self, path: Path, permission: Permission) -> None:
        """
        Require an operation to be allowed.

        Raises:
            PermissionDeniedError: If the operation is not allowed.
        """
        if not self.check(path, permission):
            resolved_path = path.resolve()
            workspace_root = self.workspace_path.resolve()

            # Determine reason
            try:
                resolved_path.relative_to(workspace_root)
            except ValueError:
                reason = "Path is outside workspace boundaries"
            else:
                if self.workspace_resolver.is_protected_path(resolved_path, workspace_root):
                    reason = "Path is Host-owned and protected from modification"
                else:
                    reason = "Operation not permitted"

            raise PermissionDeniedError(path, permission, reason)


@dataclass
class PermissivePolicy:
    """
    Permissive policy that allows all operations.

    Useful for testing or trusted environments.
    Does NOT protect Host-owned files.
    """

    def check(self, path: Path, permission: Permission) -> bool:
        """Always returns True."""
        return True

    def require(self, path: Path, permission: Permission) -> None:
        """Does nothing (always allows)."""
        pass


@dataclass
class CompositePolicy:
    """
    Policy that combines multiple policies.

    An operation is allowed only if ALL policies allow it.
    """

    policies: list[PermissionPolicy]

    def check(self, path: Path, permission: Permission) -> bool:
        """Check all policies."""
        return all(policy.check(path, permission) for policy in self.policies)

    def require(self, path: Path, permission: Permission) -> None:
        """Require all policies to allow."""
        for policy in self.policies:
            policy.require(path, permission)


def create_default_policy(
    workspace_resolver: WorkspaceResolver,
    workspace_path: Path,
    allow_outside_workspace: bool = False,
) -> PermissionPolicy:
    """
    Create the default permission policy for a workspace.

    Args:
        workspace_resolver: The workspace resolver.
        workspace_path: The workspace root path.
        allow_outside_workspace: Whether to allow operations outside workspace.

    Returns:
        A HostPermissionPolicy instance.
    """
    return HostPermissionPolicy(
        workspace_resolver=workspace_resolver,
        workspace_path=workspace_path,
        allow_outside_workspace=allow_outside_workspace,
    )


__all__ = [
    "Permission",
    "PermissionDeniedError",
    "PermissionPolicy",
    "HostPermissionPolicy",
    "PermissivePolicy",
    "CompositePolicy",
    "create_default_policy",
]
