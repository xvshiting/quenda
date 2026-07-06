"""
Capability-based model routing for Quenda Runtime.

This module implements ADR-028: Capability-Based Model Routing.

The routing system enables automatic model selection based on the
capabilities required by the effective context (e.g., vision for images).

Key components:
- ModelRequirementResolver: Analyzes messages to determine required capabilities
- ModelRouter: Selects appropriate model based on capabilities
- CapabilityGuard: Validates model satisfies required capabilities
- ModelRoutingResult: Data class capturing routing decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quenda.kernel.types import Message, ModelCapability, ModelRequirements
    from quenda.providers.model import Model, ModelSpec


@dataclass(frozen=True)
class ModelRoutingResult:
    """
    Result of model routing decision.

    Captures the routing decision for observability and debugging.
    Does not modify Session state - routing is per-run/per-turn.

    Attributes:
        requested_role: The model role initially requested (e.g., "default").
        resolved_role: The actual role resolved after capability check.
        model: The selected model instance.
        required_capabilities: Set of capabilities required for this turn.
        reason: Human-readable explanation of the routing decision.
    """

    requested_role: str
    resolved_role: str
    model: Model
    required_capabilities: set[str]
    reason: str


class ModelRequirementResolver:
    """
    Resolves required capabilities from effective context.

    Analyzes all messages in the effective context to determine
    what capabilities are needed for the current turn.

    This checks not just the current user message, but ALL messages
    that will be sent to the model (including tool results, history, etc.).

    Example:
        >>> resolver = ModelRequirementResolver()
        >>> requirements = resolver.resolve(messages)
        >>> print(requirements.capabilities)
        {'text', 'vision'}
    """

    def resolve(self, messages: list[Message]) -> "ModelRequirements":
        """
        Analyze messages to determine required capabilities.

        Args:
            messages: The effective context messages for this turn.

        Returns:
            ModelRequirements with required capabilities.
        """
        from quenda.kernel.types import ImageContent, ModelCapability, ModelRequirements

        capabilities: set[ModelCapability] = {ModelCapability.TEXT}

        for message in messages:
            content = message.content

            # Handle structured content (multimodal)
            if isinstance(content, list | tuple):
                for block in content:
                    # Check for image content
                    if hasattr(block, "type") and block.type == "image":
                        capabilities.add(ModelCapability.VISION)
                    elif isinstance(block, ImageContent):
                        capabilities.add(ModelCapability.VISION)

            # Check for tool results with image content
            if isinstance(content, list | tuple):
                for block in content:
                    if hasattr(block, "image_content") and block.image_content is not None:
                        capabilities.add(ModelCapability.VISION)

        return ModelRequirements(capabilities=capabilities)


class ModelRouter:
    """
    Routes to appropriate model based on capabilities.

    The router uses a capability-based selection strategy:
    1. If default model satisfies required capabilities, use default
    2. Otherwise, route to configured capability-specific model
    3. If no suitable model configured, raise error

    Configuration is provided via models dict with role keys:
        {
            "default": Model(...),
            "vision": Model(...),
        }

    Example:
        >>> router = ModelRouter()
        >>> result = router.route(
        ...     requirements=requirements,
        ...     default_model=default,
        ...     capability_models={"vision": vision_model},
        ... )
        >>> print(result.resolved_role)
        'vision'
    """

    def route(
        self,
        requirements: "ModelRequirements",
        default_model: "Model",
        capability_models: dict[str, "Model"] | None = None,
        explicit_model: "Model | None" = None,
    ) -> ModelRoutingResult:
        """
        Route to appropriate model based on requirements.

        Priority:
        1. Explicit model (user selected via /model or API)
        2. Default model if it satisfies requirements
        3. Capability-specific model (vision, audio, etc.)
        4. Error if no suitable model found

        Args:
            requirements: Required capabilities for this turn.
            default_model: The default model to use if it satisfies requirements.
            capability_models: Mapping of capability name to model
                (e.g., {"vision": vision_model}).
            explicit_model: User-explicitly selected model (highest priority).

        Returns:
            ModelRoutingResult with the routing decision.

        Raises:
            UnsupportedFeatureError: If no model satisfies requirements.
        """
        from quenda.providers.model import capabilities_of

        capability_models = capability_models or {}
        required_caps = requirements.capabilities
        required_names = {cap.value for cap in required_caps}

        # Priority 1: Explicit model selection
        if explicit_model is not None:
            model_caps = capabilities_of(explicit_model.spec)
            model_cap_names = {cap.value for cap in model_caps}

            # Check if explicit model satisfies requirements
            missing = required_names - model_cap_names
            if missing:
                from quenda.providers.errors import UnsupportedFeatureError

                raise UnsupportedFeatureError.for_missing_capabilities(
                    model_id=f"{explicit_model.provider.id}/{explicit_model.id}",
                    missing=missing,
                    configured_capability_models={
                        cap: f"{m.provider.id}/{m.id}"
                        for cap, m in capability_models.items()
                    },
                )

            return ModelRoutingResult(
                requested_role="explicit",
                resolved_role="explicit",
                model=explicit_model,
                required_capabilities=required_names,
                reason="explicit model selection",
            )

        # Priority 2: Default model if it satisfies requirements
        default_caps = capabilities_of(default_model.spec)
        default_cap_names = {cap.value for cap in default_caps}

        if default_cap_names.issuperset(required_names):
            return ModelRoutingResult(
                requested_role="default",
                resolved_role="default",
                model=default_model,
                required_capabilities=required_names,
                reason="default model satisfies requirements",
            )

        # Priority 3: Route to capability-specific model
        # Find the first capability we need that default doesn't have
        missing_caps = required_names - default_cap_names

        for cap_name in sorted(missing_caps):  # Sort for determinism
            cap_model = capability_models.get(cap_name)
            if cap_model is not None:
                # Verify the capability model also satisfies all requirements
                cap_model_caps = capabilities_of(cap_model.spec)
                cap_model_cap_names = {cap.value for cap in cap_model_caps}

                if cap_model_cap_names.issuperset(required_names):
                    return ModelRoutingResult(
                        requested_role="default",
                        resolved_role=cap_name,
                        model=cap_model,
                        required_capabilities=required_names,
                        reason=f"routing to {cap_name} model for capability: {cap_name}",
                    )

        # Priority 4: No suitable model found
        from quenda.providers.errors import UnsupportedFeatureError

        missing_str = ", ".join(sorted(missing_caps))
        available_str = ", ".join(sorted(capability_models.keys())) if capability_models else "none"

        raise UnsupportedFeatureError(
            message=(
                f"No model configured for required capabilities: {missing_str}.\n"
                f"Available capability models: {available_str}.\n"
                f"Configure a model for these capabilities in config.yaml."
            ),
            missing_capabilities=missing_caps,
        )


class CapabilityGuard:
    """
    Validates that a model satisfies required capabilities.

    This is a final validation step before model invocation.
    It raises clear errors if the model cannot handle the
    required capabilities.

    Example:
        >>> guard = CapabilityGuard()
        >>> guard.ensure_supported(model, requirements)
        # Raises UnsupportedFeatureError if not supported
    """

    def ensure_supported(
        self,
        model: "Model",
        requirements: "ModelRequirements",
        configured_capability_models: dict[str, str] | None = None,
    ) -> None:
        """
        Validate that model supports required capabilities.

        Args:
            model: The model to validate.
            requirements: Required capabilities.
            configured_capability_models: Mapping for suggestions in error message.

        Raises:
            UnsupportedFeatureError: If model doesn't support required capabilities.
        """
        from quenda.providers.model import capabilities_of

        model_caps = capabilities_of(model.spec)
        model_cap_names = {cap.value for cap in model_caps}
        required_names = {cap.value for cap in requirements.capabilities}

        missing = required_names - model_cap_names

        if missing:
            from quenda.providers.errors import UnsupportedFeatureError

            raise UnsupportedFeatureError.for_missing_capabilities(
                model_id=f"{model.provider.id}/{model.id}",
                missing=missing,
                configured_capability_models=configured_capability_models,
            )


# Singleton instances for convenience
_default_resolver = ModelRequirementResolver()
_default_router = ModelRouter()
_default_guard = CapabilityGuard()


def resolve_requirements(messages: list[Message]) -> "ModelRequirements":
    """Convenience function using default resolver."""
    return _default_resolver.resolve(messages)


def route_model(
    requirements: "ModelRequirements",
    default_model: "Model",
    capability_models: dict[str, "Model"] | None = None,
    explicit_model: "Model | None" = None,
) -> ModelRoutingResult:
    """Convenience function using default router."""
    return _default_router.route(
        requirements=requirements,
        default_model=default_model,
        capability_models=capability_models,
        explicit_model=explicit_model,
    )


def ensure_capabilities_supported(
    model: "Model",
    requirements: "ModelRequirements",
    configured_capability_models: dict[str, str] | None = None,
) -> None:
    """Convenience function using default guard."""
    _default_guard.ensure_supported(model, requirements, configured_capability_models)
