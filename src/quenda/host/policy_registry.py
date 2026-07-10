"""
Policy registry for Quenda Host layer.

Agent-local policies are Host-owned extension points. The runtime defines
small policy protocols; Host resolves configured policy implementations and
binds them to Agent/Session/Run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


PolicyFactory = Callable[[dict[str, Any]], Any] | Callable[[], Any]


@dataclass
class NamedPolicySpec:
    """One policy candidate before instantiation."""

    name: str
    source: str
    policy: Any | None = None
    factory: PolicyFactory | None = None

    def __post_init__(self) -> None:
        if self.policy is None and self.factory is None:
            raise ValueError(f"NamedPolicySpec '{self.name}' needs policy or factory")


@dataclass
class LoadedPolicyCatalog:
    """Catalog of loaded agent-local policies."""

    policies: dict[str, NamedPolicySpec] = field(default_factory=dict)

    def add(self, spec: NamedPolicySpec) -> None:
        self.policies[spec.name] = spec

    def get(self, name: str) -> NamedPolicySpec | None:
        return self.policies.get(name)

    def has(self, name: str) -> bool:
        return name in self.policies

    def all_names(self) -> list[str]:
        return list(self.policies.keys())


class PolicyRegistryBuilder:
    """Builder for agent-local policy registrations."""

    def __init__(self) -> None:
        self._catalog = LoadedPolicyCatalog()

    def register(self, name: str, policy: Any, *, source: str = "agent_local") -> None:
        if self._catalog.has(name):
            existing = self._catalog.get(name)
            raise ValueError(
                f"Duplicate policy name '{name}': already registered from {existing.source}"
            )
        self._catalog.add(NamedPolicySpec(name=name, source=source, policy=policy))

    def register_factory(
        self,
        name: str,
        factory: PolicyFactory,
        *,
        source: str = "agent_local",
    ) -> None:
        if self._catalog.has(name):
            existing = self._catalog.get(name)
            raise ValueError(
                f"Duplicate policy name '{name}': already registered from {existing.source}"
            )
        self._catalog.add(NamedPolicySpec(name=name, source=source, factory=factory))

    def build(self) -> LoadedPolicyCatalog:
        return self._catalog


__all__ = [
    "LoadedPolicyCatalog",
    "NamedPolicySpec",
    "PolicyFactory",
    "PolicyRegistryBuilder",
]
