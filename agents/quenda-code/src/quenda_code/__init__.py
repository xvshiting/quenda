"""
Quenda Code Agent - official coding agent for the Quenda framework.

This package provides the agent definition (AGENT.md, instructions, extensions)
for the Quenda Code Agent. It is discovered by the ``kora`` framework via the
``kora.agents`` entry point group.
"""

from __future__ import annotations

from pathlib import Path

from quenda_code.__about__ import __version__

AGENT_DIR = Path(__file__).parent / "agent"
"""Path to the agent package directory containing AGENT.md, config.yaml, etc."""


__all__ = [
    "AGENT_DIR",
    "__version__",
]
