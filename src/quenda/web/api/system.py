"""Safe runtime information for the Web UI settings page."""

import os
import platform
import sys
from pathlib import Path

from fastapi import APIRouter

from quenda.capabilities import build_framework_capability_manifest

router = APIRouter()


@router.get("/capabilities")
async def capability_manifest() -> dict[str, object]:
    """Return the same safe capability manifest exposed by the CLI."""
    return build_framework_capability_manifest()


@router.get("")
async def system_info() -> dict[str, object]:
    quenda_home = Path(os.environ.get("QUENDA_HOME", Path.home() / ".quenda")).expanduser()
    return {
        "quenda_home": str(quenda_home),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
    }
