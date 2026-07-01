"""
Workspace binding for Kora Host layer.

Provides workspace identity and binding resolution as defined in ADR-004.

Core model:
    Physical Folder -> workspace.yaml (binding) -> workspace_id -> user-agent-workspace state
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from kora.host.identity import User


@dataclass
class WorkspaceBinding:
    """
    Host-owned workspace binding.

    This represents the binding file at `<workspace>/.kora/workspace.yaml`.
    It maps a physical folder to a logical workspace identity.

    This file is Host-owned and protected - Agents cannot modify it.

    Attributes:
        schema_version: Schema version for future compatibility.
        id: Logical workspace identifier (e.g., "ws_abc123").
        name: Human-readable workspace name.
        created_at: When the binding was created.
        path_hint: Original path when binding was created (for validation).
        resource_fingerprint: Optional fingerprint for resource validation.
    """

    schema_version: int = 1
    id: str = field(default_factory=lambda: f"ws_{uuid4().hex[:8]}")
    name: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    path_hint: str | None = None
    resource_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for YAML/JSON output."""
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "binding": {
                "created_at": self.created_at.isoformat(),
                "path_hint": self.path_hint,
                "resource_fingerprint": self.resource_fingerprint,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceBinding:
        """Deserialize from dictionary."""
        binding_data = data.get("binding", {})
        return cls(
            schema_version=data.get("schema_version", 1),
            id=data["id"],
            name=data.get("name"),
            created_at=datetime.fromisoformat(binding_data.get("created_at", datetime.now().isoformat())),
            path_hint=binding_data.get("path_hint"),
            resource_fingerprint=binding_data.get("resource_fingerprint"),
        )

    @classmethod
    def create(cls, path: Path, name: str | None = None) -> WorkspaceBinding:
        """
        Create a new workspace binding for a path.

        Args:
            path: The workspace directory path.
            name: Optional human-readable name (defaults to directory name).

        Returns:
            A new WorkspaceBinding instance.
        """
        return cls(
            id=f"ws_{uuid4().hex[:8]}",
            name=name or path.name,
            created_at=datetime.now(),
            path_hint=str(path.resolve()),
        )


# YAML-like simple serialization (no external dependency)
def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data as simple YAML format."""
    lines = []

    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                if sub_value is None:
                    continue
                # Quote strings that might need it
                if isinstance(sub_value, str):
                    lines.append(f"  {sub_key}: \"{sub_value}\"")
                else:
                    lines.append(f"  {sub_key}: {sub_value}")
        elif isinstance(value, str):
            lines.append(f"{key}: \"{value}\"")
        else:
            lines.append(f"{key}: {value}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_yaml(content: str) -> dict[str, Any]:
    """Parse simple YAML content."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_dict: dict[str, Any] | None = None

    for line in content.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue

        # Handle nested dict (2-space indent)
        if line.startswith("  ") and current_dict is not None:
            sub_key, sub_value = line.strip().split(":", 1)
            sub_key = sub_key.strip()
            sub_value = sub_value.strip().strip("\"'")
            # Try to parse as int if possible
            try:
                sub_value = int(sub_value)
            except ValueError:
                pass
            current_dict[sub_key] = sub_value
            continue

        # Top-level key-value
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value == "":
                # Start of nested dict
                current_key = key
                current_dict = {}
                result[key] = current_dict
            else:
                # Regular value
                current_key = None
                current_dict = None
                value = value.strip("\"'")
                try:
                    value = int(value)
                except ValueError:
                    pass
                result[key] = value

    return result


class WorkspaceResolver:
    """
    Resolver for workspace binding.

    Handles reading, creating, and validating workspace bindings
    in physical folders.

    Usage:
        resolver = WorkspaceResolver()

        # Resolve existing or create new
        binding = resolver.resolve(workspace_path)

        # Get user workspace storage path
        storage_path = resolver.get_user_workspace_path(user, agent_name, binding)
    """

    # Protected paths that Agents cannot modify
    PROTECTED_PATHS = frozenset([
        ".kora/workspace.yaml",
        ".kora/workspace.json",
    ])

    def __init__(self, user_storage_root: Path | None = None) -> None:
        """
        Initialize resolver.

        Args:
            user_storage_root: Root directory for user storage.
                Defaults to ~/.kora/
        """
        self.user_storage_root = user_storage_root or Path.home() / ".kora"

    def resolve(self, workspace_path: Path, auto_create: bool = True) -> WorkspaceBinding:
        """
        Resolve workspace binding for a path.

        If binding exists, loads and validates it.
        If not and auto_create=True, creates a new binding.

        Args:
            workspace_path: The physical workspace directory.
            auto_create: Whether to create binding if none exists.

        Returns:
            The resolved WorkspaceBinding.

        Raises:
            ValueError: If binding validation fails.
        """
        workspace_path = workspace_path.resolve()
        binding_path = workspace_path / ".kora" / "workspace.yaml"

        if binding_path.exists():
            return self._load_binding(binding_path)
        elif auto_create:
            return self._create_binding(workspace_path, binding_path)
        else:
            raise ValueError(f"No workspace binding found at {workspace_path}")

    def _load_binding(self, binding_path: Path) -> WorkspaceBinding:
        """Load binding from file."""
        content = binding_path.read_text(encoding="utf-8")
        data = _parse_yaml(content)
        return WorkspaceBinding.from_dict(data)

    def _create_binding(self, workspace_path: Path, binding_path: Path) -> WorkspaceBinding:
        """Create and save new binding."""
        binding = WorkspaceBinding.create(workspace_path)

        # Ensure .kora directory exists
        binding_path.parent.mkdir(parents=True, exist_ok=True)

        # Write binding file
        _write_yaml(binding_path, binding.to_dict())

        return binding

    def validate_binding(self, binding: WorkspaceBinding, workspace_path: Path) -> bool:
        """
        Validate that binding matches expected workspace.

        Checks:
        - path_hint matches current path (or is known)
        - workspace_id is registered (future: check against known IDs)

        Args:
            binding: The workspace binding.
            workspace_path: Current workspace path.

        Returns:
            True if binding is valid.
        """
        current_path = str(workspace_path.resolve())

        # For now, basic validation: path hint matches or we accept unknown
        if binding.path_hint:
            # Path hint should match or be a known alternative
            if binding.path_hint == current_path:
                return True
            # Future: check against registered known paths
            # For now, accept mismatch but log warning

        return True  # Accept all bindings for now

    def get_user_workspace_path(
        self,
        user: User,
        agent_name: str,
        binding: WorkspaceBinding,
    ) -> Path:
        """
        Get user-agent-workspace storage path.

        Returns the directory for user-specific agent state for this workspace.

        Layout: ~/.kora/users/<user_id>/agents/<agent_name>/workspaces/<workspace_id>/

        Args:
            user: The user.
            agent_name: The agent name.
            binding: The workspace binding.

        Returns:
            The storage path.
        """
        path = (
            self.user_storage_root
            / "users"
            / user.id
            / "agents"
            / agent_name
            / "workspaces"
            / binding.id
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_user_agent_path(self, user: User, agent_name: str) -> Path:
        """
        Get user-agent storage path (workspace-independent).

        Layout: ~/.kora/users/<user_id>/agents/<agent_name>/

        Args:
            user: The user.
            agent_name: The agent name.

        Returns:
            The storage path.
        """
        path = self.user_storage_root / "users" / user.id / "agents" / agent_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_user_workspace_skills_path(
        self,
        user: User,
        binding: WorkspaceBinding,
    ) -> Path:
        """
        Get user-workspace skills path.

        This is where user-specific skills for a workspace are stored.
        Skills here are isolated per user and per workspace.

        Layout: ~/.kora/users/<user_id>/workspaces/<workspace_id>/skills/

        Args:
            user: The user.
            binding: The workspace binding.

        Returns:
            The skills path.
        """
        path = (
            self.user_storage_root
            / "users"
            / user.id
            / "workspaces"
            / binding.id
            / "skills"
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def is_protected_path(self, path: Path, workspace_root: Path) -> bool:
        """
        Check if a path is protected (Host-owned).

        Agents cannot write to protected paths.

        Args:
            path: The path to check.
            workspace_root: The workspace root directory.

        Returns:
            True if path is protected.
        """
        try:
            relative = path.relative_to(workspace_root)
            relative_str = str(relative)
            return relative_str in self.PROTECTED_PATHS
        except ValueError:
            # Path is not under workspace root
            return False


__all__ = [
    "WorkspaceBinding",
    "WorkspaceResolver",
]