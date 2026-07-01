"""
Identity management for Kora Host layer.

Provides user identity resolution and multi-tenancy support.
"""

from __future__ import annotations

import getpass
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class User:
    """
    User identity.

    Represents a user in the system. The id is the primary identifier
    used for multi-tenancy and access control.
    """

    id: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class IdentityResolver(Protocol):
    """
    Protocol for resolving user identity.

    Implementations determine the current user from context,
    environment, or external authentication systems.
    """

    def resolve(self, context: dict[str, Any] | None = None) -> User | None:
        """
        Resolve the current user.

        Args:
            context: Optional context for resolution (e.g., request headers).

        Returns:
            The resolved User, or None if not authenticated.
        """
        ...


class EnvIdentityResolver:
    """
    Simple identity resolver from environment variable.

    Useful for development and testing. Reads user ID from
    an environment variable.

    Usage:
        resolver = EnvIdentityResolver("KORA_USER_ID")
        user = resolver.resolve()
        if user:
            print(f"Current user: {user.id}")
    """

    def __init__(self, env_var: str = "KORA_USER_ID") -> None:
        """
        Initialize with environment variable name.

        Args:
            env_var: The environment variable to read user ID from.
        """
        self.env_var = env_var

    def resolve(self, context: dict[str, Any] | None = None) -> User | None:
        """Resolve user from environment variable."""
        user_id = os.environ.get(self.env_var)
        if user_id:
            return User(id=user_id)
        return None


class StaticIdentityResolver:
    """
    Identity resolver with a fixed user.

    Useful for testing or single-user deployments.
    """

    def __init__(self, user: User) -> None:
        """
        Initialize with a fixed user.

        Args:
            user: The user to always return.
        """
        self._user = user

    def resolve(self, context: dict[str, Any] | None = None) -> User | None:
        """Always return the fixed user."""
        return self._user


class DefaultUserResolver:
    """
    Identity resolver for TUI mode that always returns a user.

    Resolution priority:
    1. Environment variable KORA_USER_ID (or custom)
    2. System username
    3. Fixed "default" user

    Unlike EnvIdentityResolver, this never returns None.
    Use this for local/TUI deployments where authentication
    is not required but a user identity is still needed.

    Usage:
        resolver = DefaultUserResolver()
        user = resolver.resolve()  # Always returns a User
        print(f"Running as: {user.id}")
    """

    def __init__(self, env_var: str = "KORA_USER_ID") -> None:
        """
        Initialize with environment variable name.

        Args:
            env_var: The environment variable to check first.
        """
        self.env_var = env_var

    def resolve(self, context: dict[str, Any] | None = None) -> User:
        """
        Resolve user with fallback logic.

        Always returns a User, never None.

        Returns:
            The resolved User.
        """
        # Priority 1: Environment variable
        user_id = os.environ.get(self.env_var)
        if user_id:
            return User(id=user_id)

        # Priority 2: System username
        try:
            username = getpass.getuser()
            return User(id=username, name=username)
        except Exception:
            pass

        # Priority 3: Fixed default user
        return User(id="default")


__all__ = [
    "User",
    "IdentityResolver",
    "EnvIdentityResolver",
    "StaticIdentityResolver",
]
