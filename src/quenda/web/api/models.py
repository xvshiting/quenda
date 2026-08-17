"""Read-only model and provider catalog routes."""

import os

from fastapi import APIRouter

from quenda.providers import get_provider_registry

router = APIRouter()


@router.get("")
async def list_models() -> list[dict[str, object]]:
    """List model specifications from all registered providers."""
    registry = get_provider_registry()
    result: list[dict[str, object]] = []
    for provider_id in registry.list_providers():
        provider = registry.get_provider(provider_id)
        if provider is None:
            continue
        for model in provider.list_models():
            result.append(
                {
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "model_id": model.id,
                    "model_name": model.name,
                    "tool_calling": model.tool_calling,
                    "vision": model.vision,
                    "context_window": model.context_window,
                }
            )
    return result


@router.get("/providers")
async def list_providers() -> list[dict[str, object]]:
    """List provider metadata without exposing credentials."""
    registry = get_provider_registry()
    result: list[dict[str, object]] = []
    for provider_id in registry.list_providers():
        provider = registry.get_provider(provider_id)
        if provider is None:
            continue
        credential_env = (
            provider.spec.api_key[2:-1]
            if provider.spec.api_key
            and provider.spec.api_key.startswith("${")
            and provider.spec.api_key.endswith("}")
            else None
        )
        result.append(
            {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.spec.base_url,
                "model_count": len(provider.list_models()),
                "credential_env": credential_env,
                "configured": bool(os.environ.get(credential_env))
                if credential_env
                else None,
            }
        )
    return result
