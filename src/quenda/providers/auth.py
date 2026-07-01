"""
Authentication resolver for Quenda providers.

Handles resolution of API keys and other authentication credentials.
"""

from __future__ import annotations

import os
from typing import Protocol


class AuthResolver(Protocol):
    """
    Protocol for authentication resolution.

    Implementations can handle:
    - Environment variable patterns: "${MY_API_KEY}"
    - Direct values: "sk-xxx"
    - OAuth tokens, mTLS, etc.
    """

    def resolve(self, credential: str) -> str | None:
        """
        Resolve a credential pattern to its actual value.

        Args:
            credential: The credential pattern or value.

        Returns:
            The resolved credential value, or None if not found.
        """
        ...


class EnvAuthResolver:
    """
    Environment variable based authentication resolver.

    Handles patterns like "${DASHSCOPE_API_KEY}" by looking up
    environment variables.
    """

    def resolve(self, credential: str) -> str | None:
        """Resolve credential, supporting ${ENV_VAR} patterns."""
        if not credential:
            return None

        # Check for environment variable pattern
        if credential.startswith("${") and credential.endswith("}"):
            env_var = credential[2:-1]
            return os.environ.get(env_var)

        # Direct value
        return credential


class CompositeAuthResolver:
    """
    Combines multiple auth resolvers.

    Tries each resolver in order until one succeeds.
    """

    def __init__(self, resolvers: list[AuthResolver]) -> None:
        self.resolvers = resolvers

    def resolve(self, credential: str) -> str | None:
        """Try each resolver in order."""
        for resolver in self.resolvers:
            result = resolver.resolve(credential)
            if result:
                return result
        return None
