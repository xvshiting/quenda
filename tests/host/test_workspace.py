"""
Tests for Host layer workspace binding.
"""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from quenda.host import (
    WorkspaceBinding,
    WorkspaceResolver,
    User,
)


@pytest.fixture
def temp_storage_root() -> Path:
    """Create temporary storage root."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestWorkspaceBinding:
    """Tests for WorkspaceBinding."""

    def test_create_binding(self) -> None:
        """Test creating a new binding."""
        path = Path("/tmp/test-workspace")
        binding = WorkspaceBinding.create(path)

        assert binding.id.startswith("ws_")
        assert binding.name == "test-workspace"
        # macOS resolves /tmp to /private/tmp
        assert binding.path_hint == str(path.resolve())
        assert isinstance(binding.created_at, datetime)

    def test_create_binding_with_custom_name(self) -> None:
        """Test creating binding with custom name."""
        binding = WorkspaceBinding.create(Path("/tmp/test"), name="My Project")

        assert binding.name == "My Project"

    def test_binding_serialization(self) -> None:
        """Test binding serialization to dict."""
        binding = WorkspaceBinding(
            id="ws_test123",
            name="Test Workspace",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            path_hint="/path/to/workspace",
        )

        data = binding.to_dict()
        assert data["schema_version"] == 1
        assert data["id"] == "ws_test123"
        assert data["name"] == "Test Workspace"
        assert data["binding"]["created_at"] == "2024-01-15T10:30:00"
        assert data["binding"]["path_hint"] == "/path/to/workspace"

    def test_binding_deserialization(self) -> None:
        """Test binding deserialization from dict."""
        data = {
            "schema_version": 1,
            "id": "ws_test456",
            "name": "Restored Workspace",
            "binding": {
                "created_at": "2024-01-15T10:30:00",
                "path_hint": "/original/path",
                "resource_fingerprint": None,
            },
        }

        binding = WorkspaceBinding.from_dict(data)
        assert binding.id == "ws_test456"
        assert binding.name == "Restored Workspace"
        assert binding.created_at == datetime(2024, 1, 15, 10, 30, 0)
        assert binding.path_hint == "/original/path"

    def test_binding_default_id_generation(self) -> None:
        """Test that binding generates unique IDs."""
        binding1 = WorkspaceBinding()
        binding2 = WorkspaceBinding()

        assert binding1.id.startswith("ws_")
        assert binding2.id.startswith("ws_")
        assert binding1.id != binding2.id


class TestWorkspaceResolver:
    """Tests for WorkspaceResolver."""

    def test_resolve_creates_new_binding(self, temp_storage_root: Path) -> None:
        """Test resolving creates new binding when none exists."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            binding = resolver.resolve(workspace_path)

            assert binding.id.startswith("ws_")
            assert binding.name == workspace_path.name
            assert binding.path_hint == str(workspace_path.resolve())

            # Binding file should exist
            binding_file = workspace_path / ".quenda" / "workspace.yaml"
            assert binding_file.exists()

    def test_resolve_loads_existing_binding(self, temp_storage_root: Path) -> None:
        """Test resolving loads existing binding."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            # Create binding first time
            binding1 = resolver.resolve(workspace_path)

            # Resolve again should load same binding
            binding2 = resolver.resolve(workspace_path)

            assert binding1.id == binding2.id
            assert binding1.name == binding2.name

    def test_resolve_without_auto_create(self, temp_storage_root: Path) -> None:
        """Test resolving without auto_create raises error."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            with pytest.raises(ValueError, match="No workspace binding found"):
                resolver.resolve(workspace_path, auto_create=False)

    def test_get_user_workspace_path(self, temp_storage_root: Path) -> None:
        """Test getting user workspace storage path."""
        resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
        user = User(id="user-123")
        binding = WorkspaceBinding(id="ws_test", name="Test")

        path = resolver.get_user_workspace_path(user, "my-agent", binding)

        expected = temp_storage_root / "users" / "user-123" / "agents" / "my-agent" / "workspaces" / "ws_test"
        assert path == expected
        assert path.exists()  # Should be created

    def test_get_user_agent_path(self, temp_storage_root: Path) -> None:
        """Test getting user-agent storage path."""
        resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
        user = User(id="user-456")

        path = resolver.get_user_agent_path(user, "assistant")

        expected = temp_storage_root / "users" / "user-456" / "agents" / "assistant"
        assert path == expected
        assert path.exists()

    def test_user_isolation(self, temp_storage_root: Path) -> None:
        """Test that different users have different paths."""
        resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
        user1 = User(id="user-1")
        user2 = User(id="user-2")
        binding = WorkspaceBinding(id="ws_shared", name="Shared")

        path1 = resolver.get_user_workspace_path(user1, "agent", binding)
        path2 = resolver.get_user_workspace_path(user2, "agent", binding)

        assert path1 != path2
        assert "user-1" in str(path1)
        assert "user-2" in str(path2)

    def test_agent_isolation(self, temp_storage_root: Path) -> None:
        """Test that different agents have different paths."""
        resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
        user = User(id="user-123")
        binding = WorkspaceBinding(id="ws_test", name="Test")

        path1 = resolver.get_user_workspace_path(user, "agent-a", binding)
        path2 = resolver.get_user_workspace_path(user, "agent-b", binding)

        assert path1 != path2
        assert "agent-a" in str(path1)
        assert "agent-b" in str(path2)

    def test_workspace_isolation(self, temp_storage_root: Path) -> None:
        """Test that different workspaces have different paths."""
        resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
        user = User(id="user-123")
        binding1 = WorkspaceBinding(id="ws_one", name="One")
        binding2 = WorkspaceBinding(id="ws_two", name="Two")

        path1 = resolver.get_user_workspace_path(user, "agent", binding1)
        path2 = resolver.get_user_workspace_path(user, "agent", binding2)

        assert path1 != path2
        assert "ws_one" in str(path1)
        assert "ws_two" in str(path2)


class TestProtectedPaths:
    """Tests for protected path detection."""

    def test_workspace_yaml_is_protected(self, temp_storage_root: Path) -> None:
        """Test that workspace.yaml is protected."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
            resolver.resolve(workspace_path)  # Create binding

            protected_path = workspace_path / ".quenda" / "workspace.yaml"
            assert resolver.is_protected_path(protected_path, workspace_path)

    def test_other_quenda_files_not_protected(self, temp_storage_root: Path) -> None:
        """Test that other .quenda files are not protected."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)
            resolver.resolve(workspace_path)

            # config.yaml should not be protected (Project-owned)
            config_path = workspace_path / ".quenda" / "config.yaml"
            assert not resolver.is_protected_path(config_path, workspace_path)

    def test_regular_files_not_protected(self, temp_storage_root: Path) -> None:
        """Test that regular files are not protected."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            readme_path = workspace_path / "README.md"
            assert not resolver.is_protected_path(readme_path, workspace_path)

            src_path = workspace_path / "src" / "main.py"
            assert not resolver.is_protected_path(src_path, workspace_path)

    def test_path_outside_workspace(self, temp_storage_root: Path) -> None:
        """Test that paths outside workspace are not considered protected."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            outside_path = Path("/tmp/other") / ".quenda" / "workspace.yaml"
            assert not resolver.is_protected_path(outside_path, workspace_path)


class TestBindingValidation:
    """Tests for binding validation."""

    def test_validate_matching_path(self, temp_storage_root: Path) -> None:
        """Test validation with matching path."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            binding = resolver.resolve(workspace_path)
            assert resolver.validate_binding(binding, workspace_path)

    def test_validate_accepts_path_mismatch(self, temp_storage_root: Path) -> None:
        """Test validation accepts path mismatch (directory moved)."""
        with TemporaryDirectory() as workspace_dir:
            workspace_path = Path(workspace_dir)
            resolver = WorkspaceResolver(user_storage_root=temp_storage_root)

            # Create binding with original path
            binding = WorkspaceBinding(
                id="ws_test",
                path_hint="/original/path",
            )

            # Should still validate (accepts mismatch for now)
            assert resolver.validate_binding(binding, workspace_path)


class TestYAMLParsing:
    """Tests for simple YAML parsing."""

    def test_roundtrip_serialization(self) -> None:
        """Test that serialization roundtrips correctly."""
        from quenda.host.workspace import _write_yaml, _parse_yaml

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"
            original = {
                "schema_version": 1,
                "id": "ws_test123",
                "name": "Test Workspace",
                "binding": {
                    "created_at": "2024-01-15T10:30:00",
                    "path_hint": "/path/to/workspace",
                },
            }

            _write_yaml(path, original)
            loaded = _parse_yaml(path.read_text(encoding="utf-8"))

            assert loaded["schema_version"] == 1
            assert loaded["id"] == "ws_test123"
            assert loaded["name"] == "Test Workspace"
            assert loaded["binding"]["created_at"] == "2024-01-15T10:30:00"
            assert loaded["binding"]["path_hint"] == "/path/to/workspace"