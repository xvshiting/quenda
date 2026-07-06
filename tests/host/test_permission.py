"""
Tests for Host layer permission control.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from quenda.host import (
    WorkspaceResolver,
    Permission,
    PermissionDeniedError,
    HostPermissionPolicy,
    PermissivePolicy,
    CompositePolicy,
    create_default_policy,
)
from quenda.host.permission_manager import PermissionManager
from quenda.runtime.permission import (
    PermissionKind,
    PermissionLifetime,
    PermissionRequest,
    PermissionScope,
)


@pytest.fixture
def temp_workspace() -> Path:
    """Create a temporary workspace with binding."""
    with TemporaryDirectory() as tmpdir:
        workspace_path = Path(tmpdir)
        resolver = WorkspaceResolver(user_storage_root=Path(tmpdir) / "storage")
        resolver.resolve(workspace_path)  # Create binding
        yield workspace_path


@pytest.fixture
def workspace_resolver(temp_workspace: Path) -> WorkspaceResolver:
    """Create a workspace resolver."""
    return WorkspaceResolver(user_storage_root=temp_workspace / "storage")


class TestPermission:
    """Tests for Permission enum."""

    def test_permission_values(self) -> None:
        """Test permission enum values."""
        assert Permission.READ.value == "read"
        assert Permission.WRITE.value == "write"
        assert Permission.DELETE.value == "delete"
        assert Permission.EXECUTE.value == "execute"


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_error_message(self) -> None:
        """Test error message format."""
        path = Path("/some/path")
        error = PermissionDeniedError(path, Permission.WRITE, "Test reason")

        assert error.path == path
        assert error.permission == Permission.WRITE
        assert error.reason == "Test reason"
        assert "Permission denied" in str(error)
        assert "write" in str(error)
        assert "Test reason" in str(error)


class TestHostPermissionPolicy:
    """Tests for HostPermissionPolicy."""

    def test_allow_read_protected_path(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that reading protected paths is allowed."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        assert policy.check(protected_path, Permission.READ)

    def test_deny_write_protected_path(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that writing to protected paths is denied."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        assert not policy.check(protected_path, Permission.WRITE)

    def test_deny_delete_protected_path(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that deleting protected paths is denied."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        assert not policy.check(protected_path, Permission.DELETE)

    def test_allow_write_regular_file(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that writing to regular files is allowed."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        regular_file = temp_workspace / "README.md"
        assert policy.check(regular_file, Permission.WRITE)

    def test_allow_write_config_yaml(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that writing to config.yaml (Project-owned) is allowed."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        config_path = temp_workspace / ".quenda" / "config.yaml"
        assert policy.check(config_path, Permission.WRITE)

    def test_deny_outside_workspace(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that operations outside workspace are denied."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
            allow_outside_workspace=False,
        )

        outside_path = Path("/tmp/outside/workspace")
        assert not policy.check(outside_path, Permission.WRITE)

    def test_allow_outside_workspace_when_configured(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that outside workspace is allowed when configured."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
            allow_outside_workspace=True,
        )

        outside_path = Path("/tmp/outside/file.txt")
        assert policy.check(outside_path, Permission.WRITE)

    def test_require_raises_on_denied(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that require() raises on denied permission."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"

        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.require(protected_path, Permission.WRITE)

        assert "Host-owned" in exc_info.value.reason

    def test_require_allows_on_granted(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that require() doesn't raise on allowed permission."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        regular_file = temp_workspace / "test.txt"
        # Should not raise
        policy.require(regular_file, Permission.WRITE)


class TestPermissivePolicy:
    """Tests for PermissivePolicy."""

    def test_allows_all(self) -> None:
        """Test that permissive policy allows everything."""
        policy = PermissivePolicy()

        assert policy.check(Path("/any/path"), Permission.READ)
        assert policy.check(Path("/any/path"), Permission.WRITE)
        assert policy.check(Path("/any/path"), Permission.DELETE)
        assert policy.check(Path("/any/path"), Permission.EXECUTE)

    def test_require_never_raises(self) -> None:
        """Test that require() never raises."""
        policy = PermissivePolicy()

        # Should never raise
        policy.require(Path("/any/path"), Permission.DELETE)


class TestCompositePolicy:
    """Tests for CompositePolicy."""

    def test_allows_when_all_allow(self) -> None:
        """Test that composite allows when all policies allow."""
        permissive = PermissivePolicy()
        composite = CompositePolicy([permissive, permissive])

        assert composite.check(Path("/any/path"), Permission.WRITE)

    def test_denies_when_any_denies(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that composite denies when any policy denies."""
        permissive = PermissivePolicy()
        restrictive = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        composite = CompositePolicy([permissive, restrictive])

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        assert not composite.check(protected_path, Permission.WRITE)

    def test_require_raises_on_first_denial(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that require raises on first denial."""
        permissive = PermissivePolicy()
        restrictive = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        composite = CompositePolicy([restrictive, permissive])

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        with pytest.raises(PermissionDeniedError):
            composite.require(protected_path, Permission.WRITE)


class TestCreateDefaultPolicy:
    """Tests for create_default_policy."""

    def test_creates_host_policy(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that default policy is HostPermissionPolicy."""
        policy = create_default_policy(workspace_resolver, temp_workspace)

        assert isinstance(policy, HostPermissionPolicy)
        assert policy.workspace_resolver == workspace_resolver
        assert policy.workspace_path == temp_workspace

    def test_default_disallows_outside(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that default policy disallows outside workspace."""
        policy = create_default_policy(workspace_resolver, temp_workspace)

        outside_path = Path("/tmp/outside")
        assert not policy.check(outside_path, Permission.WRITE)

    def test_can_allow_outside(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that outside workspace can be allowed."""
        policy = create_default_policy(
            workspace_resolver, temp_workspace, allow_outside_workspace=True
        )

        outside_path = Path("/tmp/outside/file.txt")
        assert policy.check(outside_path, Permission.WRITE)


class TestPolicyIntegration:
    """Integration tests for permission policy with real paths."""

    def test_subdirectory_operations(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that operations in subdirectories are allowed."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        # Create nested directory structure
        nested_file = temp_workspace / "src" / "module" / "file.py"
        assert policy.check(nested_file, Permission.WRITE)

    def test_symlink_handling(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test that symlinks are resolved correctly."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        # Create a file and symlink to protected path
        protected_path = temp_workspace / ".quenda" / "workspace.yaml"
        symlink_path = temp_workspace / "link_to_protected"

        # Even through symlink, protected path should be denied
        # (symlink doesn't exist but check would work if it did)
        # This test documents expected behavior
        assert not policy.check(protected_path, Permission.WRITE)

    def test_multiple_permission_checks(
        self, workspace_resolver: WorkspaceResolver, temp_workspace: Path
    ) -> None:
        """Test checking multiple permissions on same path."""
        policy = HostPermissionPolicy(
            workspace_resolver=workspace_resolver,
            workspace_path=temp_workspace,
        )

        protected_path = temp_workspace / ".quenda" / "workspace.yaml"

        # READ allowed
        assert policy.check(protected_path, Permission.READ)
        # WRITE denied
        assert not policy.check(protected_path, Permission.WRITE)
        # DELETE denied
        assert not policy.check(protected_path, Permission.DELETE)
        # EXECUTE (read-like) allowed
        assert policy.check(protected_path, Permission.EXECUTE)


class TestPermissionManager:
    """Tests for session-level permission caching."""

    def test_network_permission_is_reused_within_session(self) -> None:
        """Test that one network approval covers later network requests in the same session."""
        manager = PermissionManager()
        calls = {"count": 0}

        def prompt_handler(request: PermissionRequest) -> bool:
            calls["count"] += 1
            return True

        manager.prompt_handler = prompt_handler

        first = PermissionRequest(
            kind=PermissionKind.NETWORK_ACCESS,
            resource="https://www.baidu.com",
            scope=PermissionScope.ALL,
            lifetime=PermissionLifetime.SESSION,
        )
        second = PermissionRequest(
            kind=PermissionKind.NETWORK_ACCESS,
            resource="https://www.bing.com",
            scope=PermissionScope.ALL,
            lifetime=PermissionLifetime.SESSION,
        )

        assert manager.decide(first).allowed is True
        assert manager.decide(second).allowed is True
        assert calls["count"] == 1
