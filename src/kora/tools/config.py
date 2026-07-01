"""
Configuration for Kora tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolsConfig:
    """
    Global configuration for all tools.

    This configuration controls security settings and resource limits.
    """

    # Workspace
    workspace: Path = field(default_factory=Path.cwd)

    # Resource limits
    max_timeout: int = 300
    max_output_bytes: int = 1_000_000

    # Feature flags
    enable_shell: bool = False
    enable_network: bool = False
    enable_code_execution: bool = False

    # Shell settings
    shell_default_timeout: int = 30
    shell_max_timeout: int = 300

    # Network settings
    network_default_timeout: int = 30
    network_max_timeout: int = 60
    network_max_redirects: int = 5

    # Code execution settings
    sandbox_default_timeout: int = 30
    sandbox_max_timeout: int = 60
    sandbox_max_memory_mb: int = 512
    sandbox_max_ast_nodes: int = 5000

    def __post_init__(self) -> None:
        """Ensure workspace is a resolved Path."""
        if isinstance(self.workspace, str):
            self.workspace = Path(self.workspace)
        self.workspace = self.workspace.resolve()
