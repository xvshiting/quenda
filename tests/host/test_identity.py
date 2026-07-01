"""
Tests for Host layer identity.
"""

import os
import pytest

from kora.host import User, EnvIdentityResolver, StaticIdentityResolver, DefaultUserResolver


class TestUser:
    """Tests for User."""

    def test_user_creation(self) -> None:
        """Test creating a user."""
        user = User(id="user-123", name="Test User")

        assert user.id == "user-123"
        assert user.name == "Test User"
        assert user.metadata == {}

    def test_user_with_metadata(self) -> None:
        """Test user with metadata."""
        user = User(
            id="user-123",
            name="Test User",
            metadata={"role": "admin", "tenant": "acme"},
        )

        assert user.metadata["role"] == "admin"
        assert user.metadata["tenant"] == "acme"

    def test_user_is_frozen(self) -> None:
        """Test that user is immutable."""
        user = User(id="user-123")

        with pytest.raises(Exception):  # FrozenInstanceError
            user.id = "new-id"  # type: ignore


class TestEnvIdentityResolver:
    """Tests for EnvIdentityResolver."""

    def test_resolve_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving user from environment variable."""
        monkeypatch.setenv("KORA_USER_ID", "test-user-123")

        resolver = EnvIdentityResolver()
        user = resolver.resolve()

        assert user is not None
        assert user.id == "test-user-123"

    def test_resolve_with_custom_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving user from custom environment variable."""
        monkeypatch.setenv("CUSTOM_USER", "custom-user-456")

        resolver = EnvIdentityResolver(env_var="CUSTOM_USER")
        user = resolver.resolve()

        assert user is not None
        assert user.id == "custom-user-456"

    def test_resolve_without_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving when environment variable is not set."""
        monkeypatch.delenv("KORA_USER_ID", raising=False)

        resolver = EnvIdentityResolver()
        user = resolver.resolve()

        assert user is None


class TestStaticIdentityResolver:
    """Tests for StaticIdentityResolver."""

    def test_resolve_returns_fixed_user(self) -> None:
        """Test that resolve returns the fixed user."""
        user = User(id="static-user", name="Static User")
        resolver = StaticIdentityResolver(user)

        resolved = resolver.resolve()
        assert resolved is not None
        assert resolved.id == "static-user"
        assert resolved.name == "Static User"

    def test_resolve_with_context(self) -> None:
        """Test that context is ignored for static resolver."""
        user = User(id="static-user")
        resolver = StaticIdentityResolver(user)

        # Context should be ignored
        resolved = resolver.resolve(context={"headers": {"Authorization": "Bearer token"}})
        assert resolved is not None
        assert resolved.id == "static-user"


class TestIdentityEdgeCases:
    """Edge case tests for identity resolution."""

    def test_user_with_complex_metadata(self) -> None:
        """Test user with nested metadata."""
        user = User(
            id="complex-user",
            name="Complex User",
            metadata={
                "roles": ["admin", "developer"],
                "tenant": {
                    "id": "tenant-123",
                    "name": "Acme Corp",
                },
                "preferences": {
                    "theme": "dark",
                    "language": "zh-CN",
                },
            },
        )

        assert user.metadata["roles"] == ["admin", "developer"]
        assert user.metadata["tenant"]["name"] == "Acme Corp"
        assert user.metadata["preferences"]["language"] == "zh-CN"

    def test_env_resolver_with_empty_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving when environment variable is empty."""
        monkeypatch.setenv("KORA_USER_ID", "")

        resolver = EnvIdentityResolver()
        user = resolver.resolve()

        # Empty string is treated as no user (returns None)
        # This matches the implementation: if user_id: return User(...)
        assert user is None

    def test_env_resolver_multiple_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env resolver can be called multiple times."""
        monkeypatch.setenv("KORA_USER_ID", "user-123")

        resolver = EnvIdentityResolver()

        # First call
        user1 = resolver.resolve()
        assert user1 is not None
        assert user1.id == "user-123"

        # Second call should return the same ID (but different User instance)
        user2 = resolver.resolve()
        assert user2 is not None
        assert user2.id == "user-123"

    def test_env_resolver_env_var_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that resolver reflects env var changes."""
        resolver = EnvIdentityResolver()

        # Set initial value
        monkeypatch.setenv("KORA_USER_ID", "user-123")
        user1 = resolver.resolve()
        assert user1 is not None
        assert user1.id == "user-123"

        # Change value
        monkeypatch.setenv("KORA_USER_ID", "user-456")
        user2 = resolver.resolve()
        assert user2 is not None
        assert user2.id == "user-456"

    def test_static_resolver_with_none_name(self) -> None:
        """Test static resolver with user having no name."""
        user = User(id="nameless-user")
        resolver = StaticIdentityResolver(user)

        resolved = resolver.resolve()
        assert resolved is not None
        assert resolved.id == "nameless-user"
        assert resolved.name is None

    def test_user_not_hashable(self) -> None:
        """Test that User is not hashable due to dict metadata field.

        Even though User is a frozen dataclass, it contains a dict field
        (metadata) which is not hashable. This is intentional - metadata
        can have complex nested structures that wouldn't make sense to hash.
        """
        user1 = User(id="user-123", name="User One")
        user2 = User(id="user-123", name="User One")

        # User is frozen but not hashable (has dict field)
        with pytest.raises(TypeError, match="unhashable type"):
            hash(user1)

        # Equality still works
        assert user1 == user2

    def test_user_equality(self) -> None:
        """Test User equality comparison."""
        user1 = User(id="user-123", name="User One")
        user2 = User(id="user-123", name="User One")
        user3 = User(id="user-123", name="User Two")  # Different name
        user4 = User(id="user-456", name="User One")  # Different id

        # Same id and name are equal
        assert user1 == user2

        # Different metadata makes users different
        user_with_meta = User(id="user-123", name="User One", metadata={"key": "value"})
        assert user1 != user_with_meta

        # Different id makes users different
        assert user1 != user4

    def test_env_resolver_with_special_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env resolver with special characters in user ID."""
        monkeypatch.setenv("KORA_USER_ID", "user@example.com")

        resolver = EnvIdentityResolver()
        user = resolver.resolve()

        assert user is not None
        assert user.id == "user@example.com"

    def test_env_resolver_with_unicode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env resolver with unicode in user ID."""
        monkeypatch.setenv("KORA_USER_ID", "用户-123")

        resolver = EnvIdentityResolver()
        user = resolver.resolve()

        assert user is not None
        assert user.id == "用户-123"

    def test_static_resolver_preserves_metadata(self) -> None:
        """Test that static resolver preserves user metadata."""
        user = User(
            id="meta-user",
            metadata={"custom_field": "custom_value"},
        )
        resolver = StaticIdentityResolver(user)

        resolved = resolver.resolve()
        assert resolved is not None
        assert resolved.metadata == {"custom_field": "custom_value"}


class TestDefaultUserResolver:
    """Tests for DefaultUserResolver."""

    def test_resolve_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving user from environment variable."""
        monkeypatch.setenv("KORA_USER_ID", "env-user-123")

        resolver = DefaultUserResolver()
        user = resolver.resolve()

        assert user.id == "env-user-123"
        assert user.name is None

    def test_resolve_with_custom_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving user from custom environment variable."""
        monkeypatch.setenv("CUSTOM_USER", "custom-user-456")

        resolver = DefaultUserResolver(env_var="CUSTOM_USER")
        user = resolver.resolve()

        assert user.id == "custom-user-456"

    def test_resolve_falls_back_to_system_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test falling back to system username when env var not set."""
        monkeypatch.delenv("KORA_USER_ID", raising=False)

        resolver = DefaultUserResolver()
        user = resolver.resolve()

        # Should return system username (not "default")
        assert user.id != "default"
        assert user.name is not None
        assert user.id == user.name  # System username used for both

    def test_resolve_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test falling back to 'default' user when system username unavailable."""
        monkeypatch.delenv("KORA_USER_ID", raising=False)

        resolver = DefaultUserResolver()

        # Patch getpass.getuser to raise exception
        import kora.host.identity as identity_module
        original_getuser = identity_module.getpass.getuser

        def mock_getuser() -> str:
            raise OSError("No user")

        identity_module.getpass.getuser = mock_getuser
        try:
            user = resolver.resolve()
            assert user.id == "default"
        finally:
            identity_module.getpass.getuser = original_getuser

    def test_never_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that resolve never returns None."""
        monkeypatch.delenv("KORA_USER_ID", raising=False)

        resolver = DefaultUserResolver()
        user = resolver.resolve()

        assert user is not None
        assert isinstance(user, User)

    def test_env_var_takes_priority_over_system_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env var takes priority over system username."""
        monkeypatch.setenv("KORA_USER_ID", "priority-user")

        resolver = DefaultUserResolver()
        user = resolver.resolve()

        assert user.id == "priority-user"

    def test_multiple_resolvers_independent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that multiple resolvers are independent."""
        monkeypatch.setenv("USER_A", "user-a")
        monkeypatch.setenv("USER_B", "user-b")

        resolver_a = DefaultUserResolver(env_var="USER_A")
        resolver_b = DefaultUserResolver(env_var="USER_B")

        assert resolver_a.resolve().id == "user-a"
        assert resolver_b.resolve().id == "user-b"

    def test_resolver_reflects_env_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that resolver reflects environment variable changes."""
        resolver = DefaultUserResolver()

        monkeypatch.setenv("KORA_USER_ID", "first-user")
        assert resolver.resolve().id == "first-user"

        monkeypatch.setenv("KORA_USER_ID", "second-user")
        assert resolver.resolve().id == "second-user"

        monkeypatch.delenv("KORA_USER_ID", raising=False)
        user = resolver.resolve()
        assert user.id != "first-user"
        assert user.id != "second-user"
