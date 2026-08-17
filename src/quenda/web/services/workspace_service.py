"""
Workspace service - business logic for workspace management.
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import json

from quenda.web.models.workspace import WorkspaceInfo, FileNode, FileType


class WorkspaceService:
    """Service for managing workspaces."""
    
    def __init__(self, workspaces_file: Optional[Path] = None):
        """
        Initialize workspace service.
        
        Args:
            workspaces_file: File to store workspace registry. If None, uses default.
        """
        self.workspaces_file = workspaces_file or Path.home() / ".quenda" / "workspaces.json"
        self.workspaces_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load workspace registry
        self._workspaces: dict = self._load_registry()
        self._active_workspace_id: Optional[str] = None
    
    def _load_registry(self) -> dict:
        """Load workspace registry from file."""
        if self.workspaces_file.exists():
            with open(self.workspaces_file, "r") as f:
                return json.load(f)
        return {"workspaces": {}, "active": None}
    
    def _save_registry(self):
        """Save workspace registry to file."""
        with open(self.workspaces_file, "w") as f:
            json.dump(self._workspaces, f, indent=2)
    
    async def list_workspaces(self) -> List[WorkspaceInfo]:
        """List all registered workspaces."""
        workspaces = []
        for ws_id, ws_data in self._workspaces.get("workspaces", {}).items():
            workspaces.append(WorkspaceInfo(
                id=ws_id,
                name=ws_data["name"],
                path=ws_data["path"],
                description=ws_data.get("description"),
                created_at=datetime.fromisoformat(ws_data["created_at"]),
                updated_at=datetime.fromisoformat(ws_data["updated_at"]),
                is_active=(ws_id == self._workspaces.get("active")),
            ))
        return workspaces
    
    async def create_workspace(self, request) -> WorkspaceInfo:
        """Create a new workspace."""
        import uuid
        
        ws_id = str(uuid.uuid4())[:8]
        ws_path = Path(request.path) if request.path else Path.cwd() / request.name
        
        # Create directory if it doesn't exist
        ws_path.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        ws_data = {
            "name": request.name,
            "path": str(ws_path.absolute()),
            "description": request.description,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        self._workspaces["workspaces"][ws_id] = ws_data
        self._save_registry()
        
        return WorkspaceInfo(
            id=ws_id,
            name=request.name,
            path=str(ws_path),
            description=request.description,
            created_at=now,
            updated_at=now,
        )
    
    async def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Get workspace by ID."""
        ws_data = self._workspaces.get("workspaces", {}).get(workspace_id)
        if not ws_data:
            return None
        
        return WorkspaceInfo(
            id=workspace_id,
            name=ws_data["name"],
            path=ws_data["path"],
            description=ws_data.get("description"),
            created_at=datetime.fromisoformat(ws_data["created_at"]),
            updated_at=datetime.fromisoformat(ws_data["updated_at"]),
            is_active=(workspace_id == self._workspaces.get("active")),
        )
    
    async def update_workspace(self, workspace_id: str, request) -> Optional[WorkspaceInfo]:
        """Update a workspace."""
        ws_data = self._workspaces.get("workspaces", {}).get(workspace_id)
        if not ws_data:
            return None
        
        # Update fields
        if request.name:
            ws_data["name"] = request.name
        if request.description is not None:
            ws_data["description"] = request.description
        
        ws_data["updated_at"] = datetime.now().isoformat()
        self._save_registry()
        
        return await self.get_workspace(workspace_id)
    
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace from registry (doesn't delete files)."""
        if workspace_id not in self._workspaces.get("workspaces", {}):
            return False
        
        del self._workspaces["workspaces"][workspace_id]
        if self._workspaces.get("active") == workspace_id:
            self._workspaces["active"] = None
        self._save_registry()
        
        return True
    
    async def list_files(self, workspace_id: str, path: str = ".", recursive: bool = False) -> List[FileNode]:
        """List files in a workspace."""
        ws_data = self._workspaces.get("workspaces", {}).get(workspace_id)
        if not ws_data:
            raise ValueError(f"Workspace '{workspace_id}' not found")
        
        ws_path = Path(ws_data["path"]).expanduser().resolve()
        target_path = (ws_path / path).resolve()
        
        if not target_path.exists():
            raise ValueError(f"Path '{path}' does not exist in workspace")
        
        if not target_path.is_relative_to(ws_path):
            raise ValueError(f"Path '{path}' is outside workspace")
        
        files = []
        
        if recursive:
            for item in target_path.rglob("*"):
                if item.is_relative_to(ws_path):
                    files.append(self._path_to_file_node(item, ws_path))
        else:
            for item in target_path.iterdir():
                files.append(self._path_to_file_node(item, ws_path))
        
        return files
    
    async def read_file(self, workspace_id: str, file_path: str, offset: int = 0, limit: Optional[int] = None) -> str:
        """Read a file from workspace."""
        ws_data = self._workspaces.get("workspaces", {}).get(workspace_id)
        if not ws_data:
            raise ValueError(f"Workspace '{workspace_id}' not found")
        
        ws_path = Path(ws_data["path"]).expanduser().resolve()
        target_path = (ws_path / file_path).resolve()
        
        if not target_path.exists():
            raise FileNotFoundError(f"File '{file_path}' not found")
        
        if not target_path.is_relative_to(ws_path):
            raise ValueError(f"File '{file_path}' is outside workspace")
        
        with open(target_path, "r") as f:
            lines = f.readlines()
        
        if limit:
            return "".join(lines[offset:offset+limit])
        else:
            return "".join(lines[offset:])
    
    async def get_active_workspace(self) -> Optional[WorkspaceInfo]:
        """Get currently active workspace."""
        active_id = self._workspaces.get("active")
        if not active_id:
            return None
        return await self.get_workspace(active_id)
    
    async def activate_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Set a workspace as active."""
        if workspace_id not in self._workspaces.get("workspaces", {}):
            return None
        
        self._workspaces["active"] = workspace_id
        self._save_registry()
        
        return await self.get_workspace(workspace_id)
    
    def _path_to_file_node(self, path: Path, ws_root: Path) -> FileNode:
        """Convert a Path to FileNode."""
        stat = path.stat()
        return FileNode(
            name=path.name,
            path=str(path.relative_to(ws_root)),
            type=FileType.DIRECTORY if path.is_dir() else FileType.FILE,
            size=stat.st_size if path.is_file() else None,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
        )
