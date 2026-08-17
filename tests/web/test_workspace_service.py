"""Workspace service boundary tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from quenda.web.services.workspace_service import WorkspaceService


@pytest.mark.asyncio
async def test_parent_path_cannot_escape_registered_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    service = WorkspaceService(tmp_path / "workspaces.json")
    registered = await service.create_workspace(
        SimpleNamespace(name="project", path=str(workspace), description=None)
    )

    with pytest.raises(ValueError, match="outside workspace"):
        await service.read_file(registered.id, "../secret.txt")

    with pytest.raises(ValueError, match="outside workspace"):
        await service.list_files(registered.id, "..")
