"""Lifecycle registry is the deterministic source for extension metadata."""

from __future__ import annotations

import pytest

from quenda.runtime.lifecycle import (
    FailureMode,
    LifecycleDescriptor,
    LifecycleRegistry,
    LifecycleStage,
    build_default_lifecycle_registry,
)


def test_default_registry_is_deterministic_and_stage_ordered() -> None:
    first = build_default_lifecycle_registry().to_manifest()
    second = build_default_lifecycle_registry().to_manifest()

    assert first == second
    ids = [item["id"] for item in first]
    assert ids.index("initializer") < ids.index("prompt-assembler")
    assert ids.index("prompt-assembler") < ids.index("termination-policy")
    assert next(item for item in first if item["id"] == "context-provider") == {
        "id": "context-provider",
        "stage": "context_assembly",
        "kind": "provider",
        "contract": "quenda.host.extensions.ContextProvider",
        "registration": "extensions/context/*.py",
        "owner": "host",
        "order": 40,
        "failure_mode": "fail_run",
        "mutation": "prompt_sources",
        "chooses_transition": False,
        "cache_impact": "session",
        "status": "active",
    }


def test_registry_rejects_duplicate_extension_ids() -> None:
    registry = LifecycleRegistry()
    descriptor = LifecycleDescriptor(
        id="test-policy",
        stage=LifecycleStage.BEFORE_RUN,
        kind="policy",
        contract="tests.Policy",
        registration="tests",
        owner="runtime",
        order=1,
        failure_mode=FailureMode.FAIL_RUN,
    )
    registry.register(descriptor)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(descriptor)
