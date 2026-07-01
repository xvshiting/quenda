"""
Tests for the new provider architecture.
"""

import pytest
from unittest.mock import MagicMock, patch

from kora.providers import (
    Model,
    ModelCost,
    ModelSpec,
    Provider,
    ProviderSpec,
    ProviderRegistry,
    get_provider_registry,
)
from kora.providers.api import ApiRegistry, OpenAICompletionsApi, AnthropicMessagesApi
from kora.kernel.types import Message


# =============================================================================
# ModelSpec Tests
# =============================================================================


class TestModelSpec:
    """Tests for ModelSpec."""

    def test_basic_spec(self) -> None:
        """Test creating a basic model spec."""
        spec = ModelSpec(
            id="test-model",
            name="Test Model",
        )
        assert spec.id == "test-model"
        assert spec.name == "Test Model"
        assert spec.tool_calling is True  # default
        assert spec.context_window is None

    def test_spec_with_cost(self) -> None:
        """Test model spec with pricing."""
        spec = ModelSpec(
            id="priced-model",
            name="Priced Model",
            cost=ModelCost(input=1.0, output=2.0),
        )
        assert spec.cost is not None
        assert spec.cost.input == 1.0
        assert spec.cost.output == 2.0

    def test_spec_with_overrides(self) -> None:
        """Test model spec with API overrides."""
        spec = ModelSpec(
            id="custom-model",
            name="Custom Model",
            api="anthropic-messages",
            base_url="https://custom.api.com/v1",
        )
        assert spec.api == "anthropic-messages"
        assert spec.base_url == "https://custom.api.com/v1"


# =============================================================================
# ProviderSpec Tests
# =============================================================================


class TestProviderSpec:
    """Tests for ProviderSpec."""

    def test_basic_provider_spec(self) -> None:
        """Test creating a basic provider spec."""
        spec = ProviderSpec(
            id="test-provider",
            name="Test Provider",
            base_url="https://api.test.com/v1",
        )
        assert spec.id == "test-provider"
        assert spec.base_url == "https://api.test.com/v1"
        assert spec.api == "openai-completions"  # default

    def test_provider_with_models(self) -> None:
        """Test provider with model specs."""
        spec = ProviderSpec(
            id="provider-with-models",
            name="Provider With Models",
            base_url="https://api.example.com/v1",
            models=(
                ModelSpec(id="model-1", name="Model 1"),
                ModelSpec(id="model-2", name="Model 2"),
            ),
        )
        assert len(spec.models) == 2
        assert spec.models[0].id == "model-1"


# =============================================================================
# Provider Tests
# =============================================================================


class TestProvider:
    """Tests for Provider runtime."""

    @pytest.fixture
    def api_registry(self) -> ApiRegistry:
        """Create an API registry with OpenAI completions."""
        registry = ApiRegistry()
        registry.register("openai-completions", OpenAICompletionsApi())
        registry.register("anthropic-messages", AnthropicMessagesApi())
        return registry

    @pytest.fixture
    def provider_spec(self) -> ProviderSpec:
        """Create a test provider spec."""
        return ProviderSpec(
            id="test-provider",
            name="Test Provider",
            base_url="https://api.test.com/v1",
            api_key="${TEST_API_KEY}",
            models=(
                ModelSpec(id="test-model", name="Test Model", tool_calling=True),
            ),
        )

    def test_provider_creation(
        self,
        provider_spec: ProviderSpec,
        api_registry: ApiRegistry,
    ) -> None:
        """Test creating a provider."""
        provider = Provider(spec=provider_spec, api_registry=api_registry)
        assert provider.id == "test-provider"
        assert provider.name == "Test Provider"

    def test_get_model(
        self,
        provider_spec: ProviderSpec,
        api_registry: ApiRegistry,
    ) -> None:
        """Test getting a model from provider."""
        import os
        os.environ["TEST_API_KEY"] = "test-key"

        provider = Provider(spec=provider_spec, api_registry=api_registry)
        model = provider.get_model("test-model")

        assert isinstance(model, Model)
        assert model.id == "test-model"
        assert model.provider is provider

    def test_get_nonexistent_model(
        self,
        provider_spec: ProviderSpec,
        api_registry: ApiRegistry,
    ) -> None:
        """Test getting a model that doesn't exist."""
        provider = Provider(spec=provider_spec, api_registry=api_registry)

        with pytest.raises(KeyError, match="not found"):
            provider.get_model("nonexistent-model")

    def test_list_models(
        self,
        provider_spec: ProviderSpec,
        api_registry: ApiRegistry,
    ) -> None:
        """Test listing models."""
        provider = Provider(spec=provider_spec, api_registry=api_registry)
        models = provider.list_models()

        assert len(models) == 1
        assert models[0].id == "test-model"


# =============================================================================
# ProviderRegistry Tests
# =============================================================================


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    @pytest.fixture
    def registry(self) -> ProviderRegistry:
        """Create a fresh registry."""
        from kora.providers.api import get_api_registry
        return ProviderRegistry(api_registry=get_api_registry())

    def test_register_provider(self, registry: ProviderRegistry) -> None:
        """Test registering a provider."""
        spec = ProviderSpec(
            id="custom-provider",
            name="Custom Provider",
            base_url="https://api.custom.com/v1",
            models=(ModelSpec(id="model-1", name="Model 1"),),
        )

        registry.register(spec)

        assert registry.has_provider("custom-provider")
        assert "custom-provider" in registry.list_providers()

    def test_get_model(self, registry: ProviderRegistry) -> None:
        """Test getting a model by provider and model ID."""
        import os
        os.environ["TEST_API_KEY"] = "test-key"

        spec = ProviderSpec(
            id="test",
            name="Test",
            base_url="https://api.test.com/v1",
            api_key="${TEST_API_KEY}",
            models=(ModelSpec(id="m1", name="M1"),),
        )

        registry.register(spec)
        model = registry.get_model("test", "m1")

        assert model.id == "m1"
        assert model.provider.id == "test"

    def test_get_nonexistent_provider(self, registry: ProviderRegistry) -> None:
        """Test getting a provider that doesn't exist."""
        with pytest.raises(KeyError, match="Provider.*not found"):
            registry.get_model("nonexistent", "model")

    def test_unregister_provider(self, registry: ProviderRegistry) -> None:
        """Test unregistering a provider."""
        spec = ProviderSpec(
            id="to-remove",
            name="To Remove",
            base_url="https://api.test.com/v1",
        )

        registry.register(spec)
        assert registry.has_provider("to-remove")

        result = registry.unregister("to-remove")
        assert result is True
        assert not registry.has_provider("to-remove")


# =============================================================================
# Built-in Providers Tests
# =============================================================================


class TestBuiltinProviders:
    """Tests for built-in provider specifications."""

    def test_openai_spec(self) -> None:
        """Test OpenAI spec."""
        from kora.providers.builtins import OPENAI_SPEC

        assert OPENAI_SPEC.id == "openai"
        assert len(OPENAI_SPEC.models) > 0
        assert any(m.id == "gpt-4o" for m in OPENAI_SPEC.models)

    def test_anthropic_spec(self) -> None:
        """Test Anthropic spec."""
        from kora.providers.builtins import ANTHROPIC_SPEC

        assert ANTHROPIC_SPEC.id == "anthropic"
        assert ANTHROPIC_SPEC.api == "anthropic-messages"
        assert any(m.id == "claude-3-5-sonnet-20241022" for m in ANTHROPIC_SPEC.models)

    def test_dashscope_spec(self) -> None:
        """Test DashScope spec."""
        from kora.providers.builtins import DASHSCOPE_SPEC

        assert DASHSCOPE_SPEC.id == "dashscope"
        assert any(m.id == "qwen-max" for m in DASHSCOPE_SPEC.models)

    def test_deepseek_spec(self) -> None:
        """Test DeepSeek spec."""
        from kora.providers.builtins import DEEPSEEK_SPEC

        assert DEEPSEEK_SPEC.id == "deepseek"
        assert DEEPSEEK_SPEC.api == "openai-completions"
        assert any(m.id == "deepseek-chat" for m in DEEPSEEK_SPEC.models)

    def test_deepseek_anthropic_spec(self) -> None:
        """Test DeepSeek Anthropic-compatible spec."""
        from kora.providers.builtins import DEEPSEEK_ANTHROPIC_SPEC

        assert DEEPSEEK_ANTHROPIC_SPEC.id == "deepseek-anthropic"
        assert DEEPSEEK_ANTHROPIC_SPEC.api == "anthropic-messages"
        assert DEEPSEEK_ANTHROPIC_SPEC.base_url == "https://api.deepseek.com/anthropic"
        assert any(m.id == "deepseek-v4-flash" for m in DEEPSEEK_ANTHROPIC_SPEC.models)

    def test_moonshot_spec(self) -> None:
        """Test Moonshot spec."""
        from kora.providers.builtins import MOONSHOT_SPEC

        assert MOONSHOT_SPEC.id == "moonshot"
        assert any(m.id == "moonshot-v1-8k" for m in MOONSHOT_SPEC.models)

    def test_jdcloud_spec(self) -> None:
        """Test JD Cloud spec."""
        from kora.providers.builtins import JDCLOUD_SPEC

        assert JDCLOUD_SPEC.id == "jdcloud"
        assert any(m.id == "glm-5" for m in JDCLOUD_SPEC.models)

    def test_ollama_spec(self) -> None:
        """Test Ollama spec."""
        from kora.providers.builtins import OLLAMA_SPEC

        assert OLLAMA_SPEC.id == "ollama"
        assert "localhost" in OLLAMA_SPEC.base_url


# =============================================================================
# Global Registry Tests
# =============================================================================


class TestGlobalRegistry:
    """Tests for the global provider registry."""

    def test_get_global_registry(self) -> None:
        """Test getting the global registry."""
        registry = get_provider_registry()
        assert isinstance(registry, ProviderRegistry)

    def test_global_registry_has_builtins(self) -> None:
        """Test that global registry has built-in providers."""
        registry = get_provider_registry()

        providers = registry.list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "dashscope" in providers
        assert "deepseek" in providers
        assert "deepseek-anthropic" in providers
        assert "moonshot" in providers
        assert "ollama" in providers
