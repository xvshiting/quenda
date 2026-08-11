"""
Model and provider management API routes.
"""

from typing import List
from fastapi import APIRouter

from quenda.providers import get_provider_registry


router = APIRouter()


@router.get("")
async def list_models():
    """List all available models from all providers."""
    registry = get_provider_registry()
    models = []
    
    for provider in registry.list_providers():
        for model in provider.models:
            models.append({
                "provider_id": provider.id,
                "provider_name": provider.name,
                "model_id": model.id,
                "model_name": model.name,
                "tool_calling": model.tool_calling,
                "vision": getattr(model, "vision", False),
                "context_window": getattr(model, "context_window", None),
            })
    
    return models


@router.get("/providers")
async def list_providers():
    """List all available providers."""
    registry = get_provider_registry()
    providers = []
    
    for provider in registry.list_providers():
        providers.append({
            "id": provider.id,
            "name": provider.name,
            "api_key_env": provider.api_key_env,
            "base_url": provider.base_url,
            "model_count": len(provider.models),
        })
    
    return providers
