"""
Quenda - A lightweight Agent framework.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("quenda")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0"

from quenda.capabilities import build_framework_capability_manifest

# Providers
from quenda.providers import (
    Model,
    ModelCost,
    ModelSpec,
    Provider,
    ProviderSpec,
    get_provider_registry,
)
from quenda.runtime import Agent, Session
from quenda.tools import tool

__all__ = [
    "__version__",
    "build_framework_capability_manifest",
    "Agent",
    "Session",
    "tool",
    # Providers
    "Model",
    "ModelSpec",
    "ModelCost",
    "Provider",
    "ProviderSpec",
    "get_provider_registry",
]
