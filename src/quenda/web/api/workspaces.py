"""
Workspace management API routes.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from quenda.web.services.workspace_service import WorkspaceService
from quenda.web.models.workspace import WorkspaceInfo, FileNode


router = APIRouter()


def get_workspace_service(request: Request) -> WorkspaceService:
    """Get workspace service from app state."""
    return request.app.state.workspace_service


class CreateWorkspaceRequest(BaseModel):
    """Request to create a new workspace."""
    name: str
    path: Optional[str] = None  # If None, creates in default location
    description: Optional[str] = None


class UpdateWorkspaceRequest(BaseModel):
    """Request to update a workspace."""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("", response_model=List[WorkspaceInfo])
async def list_workspaces(
    service: WorkspaceService = Depends(get_workspace_service)
):
    """List all available workspaces."""
    return await service.list_workspaces()


@router.post("", response_model=WorkspaceInfo)
async def create_workspace(
    request: CreateWorkspaceRequest,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Create a new workspace."""
    try:
        return await service.create_workspace(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceInfo)
async def get_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Get workspace details by ID."""
    workspace = await service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.put("/{workspace_id}", response_model=WorkspaceInfo)
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Update a workspace."""
    workspace = await service.update_workspace(workspace_id, request)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Delete a workspace (removes from registry, doesn't delete files)."""
    deleted = await service.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted", "workspace_id": workspace_id}


@router.get("/{workspace_id}/files", response_model=List[FileNode])
async def list_files(
    workspace_id: str,
    path: str = ".",
    recursive: bool = False,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """List files in a workspace."""
    try:
        files = await service.list_files(workspace_id, path, recursive)
        return files
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}/files/{file_path:path}")
async def read_file(
    workspace_id: str,
    file_path: str,
    offset: int = 0,
    limit: Optional[int] = None,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Read a file from workspace."""
    try:
        content = await service.read_file(workspace_id, file_path, offset, limit)
        return {
            "path": file_path,
            "content": content,
            "offset": offset,
            "limit": limit,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}/active")
async def get_active_workspace(
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Get currently active workspace."""
    workspace = await service.get_active_workspace()
    if not workspace:
        raise HTTPException(status_code=404, detail="No active workspace")
    return workspace


@router.post("/{workspace_id}/activate")
async def activate_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_workspace_service)
):
    """Set a workspace as active."""
    workspace = await service.activate_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "activated", "workspace": workspace}
