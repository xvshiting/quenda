"""
Runtime ports - capability protocols that Runtime needs.

These are interfaces that Runtime defines and needs, while Host (or other layers)
provides the implementations. This follows the Dependency Inversion Principle:

    Runtime defines what it needs (ports)
            ↑
    Host provides implementations (adapters)

Naming: We use "port" instead of "protocol" in the directory name to emphasize
that these are capability interfaces that Runtime depends on, not just any protocols.

Key principle: Host decides, Runtime executes, Kernel is unaware.
"""

from quenda.runtime.ports.storage import Storage
from quenda.runtime.ports.compression import CompressionPolicy

__all__ = [
    "Storage",
    "CompressionPolicy",
]
