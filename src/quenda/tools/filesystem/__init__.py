"""
Filesystem tools for Quenda.

The 5 core filesystem tools:
- list_files: See what exists (covers ls, find, tree)
- search_text: Find where things are (covers grep, rg)
- read_file: See specific content (covers cat, head, tail)
- write_file: Create new files
- apply_patch: Modify existing files
"""

from quenda.tools.filesystem.editing import (
    ApplyPatchTool,
    EditingConfig,
    WriteFileTool,
)
from quenda.tools.filesystem.listing import (
    ListFilesConfig,
    ListFilesTool,
)
from quenda.tools.filesystem.reading import (
    ReadFileConfig,
    ReadFileTool,
)
from quenda.tools.filesystem.searching import (
    SearchTextConfig,
    SearchTextTool,
)

__all__ = [
    # Tools
    "ListFilesTool",
    "SearchTextTool",
    "ReadFileTool",
    "WriteFileTool",
    "ApplyPatchTool",
    # Configs
    "ListFilesConfig",
    "SearchTextConfig",
    "ReadFileConfig",
    "EditingConfig",
]


def get_filesystem_tools(workspace_root: str) -> list:
    """Get all 5 filesystem tools."""
    from pathlib import Path

    workspace = Path(workspace_root)
    return [
        ListFilesTool(workspace),
        SearchTextTool(workspace),
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        ApplyPatchTool(workspace),
    ]
