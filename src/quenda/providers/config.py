"""Typed configuration for Agent-declared provider catalogs.

This module owns the translation from inspectable YAML data to Quenda's
existing ProviderSpec/ModelSpec runtime vocabulary.  Transport adapters remain
registered separately; configuration selects one by protocol ID.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quenda.providers.model import ModelSpec
from quenda.providers.provider import ProviderSpec

if TYPE_CHECKING:
    from quenda.providers.registry import ProviderRegistry


_PROVIDER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PROTOCOL_ALIASES = {
    "openai": "openai-completions",
    "anthropic": "anthropic-messages",
}
_PROVIDER_KINDS = {"builtin", "custom", "llama-server"}


@dataclass(frozen=True)
class ProviderConfig:
    """One provider declaration or override from an Agent config file."""

    id: str
    kind: str
    name: str | None = None
    base_url: str | None = None
    api: str | None = None
    api_key: str | None = field(default=None, repr=False)
    headers: Mapping[str, str] = field(default_factory=dict)
    models: tuple[ModelSpec, ...] = ()
    timeout: float | None = None
    max_retries: int | None = None


def parse_provider_configs(data: object) -> tuple[ProviderConfig, ...]:
    """Parse the public ``providers`` mapping from config.yaml data."""
    if data in (None, {}):
        return ()
    if not isinstance(data, Mapping):
        raise ValueError("providers must be a mapping keyed by provider ID")

    providers: list[ProviderConfig] = []
    for raw_id, raw_config in data.items():
        provider_id = _required_provider_id(raw_id)
        if not isinstance(raw_config, Mapping):
            raise ValueError(f"provider {provider_id!r} must be a mapping")

        kind_value = raw_config.get("type")
        if kind_value is None:
            kind = (
                "custom"
                if any(key in raw_config for key in ("url", "base_url", "models"))
                else "builtin"
            )
        else:
            kind = str(kind_value)
        if kind not in _PROVIDER_KINDS:
            raise ValueError(
                f"provider {provider_id!r} has unsupported type {kind!r}; "
                f"expected one of {sorted(_PROVIDER_KINDS)}"
            )

        base_url = _optional_string(
            raw_config.get("base_url", raw_config.get("url")),
            f"provider {provider_id!r} URL",
        )
        if kind in {"custom", "llama-server"} and not base_url:
            raise ValueError(f"provider {provider_id!r} requires url or base_url")

        raw_api = _optional_string(raw_config.get("api"), "provider API")
        api = _PROTOCOL_ALIASES.get(raw_api, raw_api) if raw_api else None
        if kind == "llama-server" and api is None:
            api = "openai-completions"

        models = _parse_models(raw_config.get("models", ()), provider_id)
        if kind in {"custom", "llama-server"} and not models:
            raise ValueError(f"provider {provider_id!r} requires at least one model")

        providers.append(
            ProviderConfig(
                id=provider_id,
                kind=kind,
                name=_optional_string(raw_config.get("name"), "provider name"),
                base_url=base_url,
                api=api,
                api_key=_optional_string(
                    raw_config.get("api_key", raw_config.get("key")),
                    "provider API key",
                ),
                headers=_string_mapping(raw_config.get("headers", {}), "headers"),
                models=models,
                timeout=_optional_float(raw_config.get("timeout"), "timeout"),
                max_retries=_optional_int(
                    raw_config.get("max_retries"), "max_retries"
                ),
            )
        )
    return tuple(providers)


def register_configured_providers(
    providers: Sequence[ProviderConfig],
    registry: ProviderRegistry,
) -> None:
    """Apply Agent provider declarations to the selected ProviderRegistry."""
    for configured in providers:
        base = registry.get_spec(configured.id)
        if configured.kind == "builtin" and base is None:
            raise ValueError(
                f"provider {configured.id!r} is a builtin override, but no such "
                "provider is registered"
            )

        base_models = base.models if base is not None else ()
        models = _merge_models(base_models, configured.models)
        base_url = configured.base_url or (base.base_url if base is not None else None)
        if base_url is None:
            raise ValueError(f"provider {configured.id!r} requires url or base_url")

        api_key = configured.api_key
        if api_key is None and configured.kind == "llama-server":
            api_key = "no-key"
        elif api_key is None and base is not None:
            api_key = base.api_key

        registry.register(
            ProviderSpec(
                id=configured.id,
                name=configured.name
                or (base.name if base is not None else configured.id),
                base_url=base_url,
                api=configured.api
                or (base.api if base is not None else "openai-completions"),
                api_key=api_key,
                headers={
                    **(dict(base.headers) if base is not None else {}),
                    **configured.headers,
                },
                models=models,
                timeout=configured.timeout
                if configured.timeout is not None
                else (base.timeout if base is not None else None),
                max_retries=configured.max_retries
                if configured.max_retries is not None
                else (base.max_retries if base is not None else None),
                metadata={
                    **(dict(base.metadata) if base is not None else {}),
                    "configured_by": "agent-config",
                    "provider_type": configured.kind,
                },
            )
        )


def _parse_models(data: object, provider_id: str) -> tuple[ModelSpec, ...]:
    if data in (None, (), [], {}):
        return ()

    entries: list[tuple[object | None, object]]
    if isinstance(data, Mapping):
        entries = list(data.items())
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        entries = [(None, item) for item in data]
    else:
        raise ValueError(f"provider {provider_id!r} models must be a list or mapping")

    models: list[ModelSpec] = []
    seen_ids: set[str] = set()
    for key, raw_model in entries:
        if isinstance(raw_model, str):
            model_data: Mapping[str, Any] = {"name": raw_model}
        elif isinstance(raw_model, Mapping):
            model_data = raw_model
        else:
            raise ValueError(f"provider {provider_id!r} model entries must be mappings")

        raw_model_id = model_data.get("id", key)
        model_id = _required_model_id(raw_model_id)
        if model_id in seen_ids:
            raise ValueError(f"provider {provider_id!r} repeats model {model_id!r}")
        seen_ids.add(model_id)

        model_name = _optional_string(model_data.get("name"), "model name") or model_id
        input_types = _string_tuple(model_data.get("input", ("text",)), "model input")
        output_types = _string_tuple(model_data.get("output", ("text",)), "model output")
        models.append(
            ModelSpec(
                id=model_id,
                name=model_name,
                input=input_types,
                output=output_types,
                reasoning=_boolean(model_data.get("reasoning"), False),
                tool_calling=_boolean(model_data.get("tool_calling"), True),
                streaming=_boolean(model_data.get("streaming"), True),
                vision=_boolean(model_data.get("vision"), False),
                context_window=_optional_int(
                    model_data.get("context_window"), "context_window"
                ),
                max_output_tokens=_optional_int(
                    model_data.get("max_output_tokens"), "max_output_tokens"
                ),
                api=_normalized_protocol(model_data.get("api")),
                base_url=_optional_string(
                    model_data.get("base_url", model_data.get("url")),
                    "model URL",
                ),
                headers=_string_mapping(model_data.get("headers", {}), "headers"),
            )
        )
    return tuple(models)


def _normalized_protocol(value: object) -> str | None:
    protocol = _optional_string(value, "model API")
    return _PROTOCOL_ALIASES.get(protocol, protocol) if protocol else None


def _required_provider_id(value: object) -> str:
    if not isinstance(value, str) or _PROVIDER_ID.fullmatch(value) is None:
        raise ValueError("provider ID must be a non-empty identifier")
    return value


def _required_model_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("model ID must be a non-empty string")
    return value


def _merge_models(
    base: Sequence[ModelSpec],
    configured: Sequence[ModelSpec],
) -> tuple[ModelSpec, ...]:
    if not configured:
        return tuple(base)
    configured_by_id = {model.id: model for model in configured}
    merged = [configured_by_id.pop(model.id, model) for model in base]
    merged.extend(configured_by_id.values())
    return tuple(merged)


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _optional_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{label} must not be negative")
    return parsed


def _optional_float(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be a number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def _boolean(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise ValueError(f"expected boolean value, got {value!r}")


def _string_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"{label} keys and values must be strings")
    return dict(value)


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, bytes):
        raise ValueError(f"{label} must be a string or list of strings")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must contain only strings")
    return tuple(value)


__all__ = [
    "ProviderConfig",
    "parse_provider_configs",
    "register_configured_providers",
]
