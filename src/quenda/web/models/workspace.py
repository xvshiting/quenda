"""
Workspace data models.
"""

from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    """File type enumeration."""
    FILE = "file"
    DIRECTORY = "directory"


class FileNode(BaseModel):
    """File or directory node."""
    name: str
    path: str
    type: FileType
    size: Optional[int] = None  # For files
    modified_at: Optional[datetime] = None
    children: Optional[List["FileNode"]] = None  # For directories (when recursive)


class WorkspaceInfo(BaseModel):
    """Workspace information."""
    id: str
    name: str
    path: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = False
    file_count: Optional[int] = None
