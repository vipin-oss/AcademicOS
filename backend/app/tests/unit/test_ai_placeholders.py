"""Unit tests: provider placeholders (Sprint M11.1).

The five catalogue providers must behave identically and honestly: no
fake AI, no network, deterministic estimates.
"""
from __future__ import annotations

import pytest

from app.application.ai.errors import AiNotConfiguredError
from app.application.dtos.ai import (
    STATUS_NOT_CONFIGURED,
    GenerationPrompt,
    ProviderConfig,
    StructuredGenerationPrompt,
)
from app.infrastructure.ai.llm.placeholders import (
    AnthropicProvider,
    GoogleProvider,
    LocalProvider,
    OllamaProvider,
    OpenAIProvider,
)

ALL_PROVIDERS = (OpenAIProvider, AnthropicProvider, GoogleProvider, OllamaProvider, LocalProvider)


class TestPlaceholderHealth:
    @pytest.mark.parametrize("cls", ALL_PROVIDERS)
    def test_health_reports_not_configured(self, cls):
        gateway = cls()
        health = gateway.health()
        assert health.provider_id == gateway.provider_id
        assert health.status == STATUS_NOT_CONFIGURED
        assert health.configured is False
        assert health.models_configured == 0
        assert "not configured" in health.detail
        assert health.checked_at  # timestamp present

    @pytest.mark.parametrize("cls", ALL_PROVIDERS)
    def test_identity_attributes(self, cls):
        gateway = cls()
        assert gateway.kind == gateway.provider_id
        assert gateway.display_name
        assert gateway.capabilities


class TestPlaceholderModels:
    def test_no_models_without_config(self):
        assert OpenAIProvider().list_models() == ()

    def test_configured_model_is_declared_but_not_usable(self):
        gateway = OpenAIProvider(
            ProviderConfig(provider_id="oa", kind="openai", model="gpt-4o-mini")
        )
        models = gateway.list_models()
        assert len(models) == 1
        assert models[0].model_id == "gpt-4o-mini"
        assert models[0].configured is False
        assert models[0].provider_id == "oa"

    def test_health_counts_declared_models(self):
        gateway = LocalProvider(
            ProviderConfig(provider_id="lc", kind="local", model="qwen2.5:7b")
        )
        assert gateway.health().models_configured == 1


class TestPlaceholderGeneration:
    @pytest.mark.parametrize("cls", ALL_PROVIDERS)
    def test_generate_raises_not_configured(self, cls):
        gateway = cls()
        with pytest.raises(AiNotConfiguredError) as exc:
            gateway.generate(GenerationPrompt(user="hello"))
        assert "not configured" in str(exc.value)
        assert exc.value.code == "ai_not_configured"

    @pytest.mark.parametrize("cls", ALL_PROVIDERS)
    def test_stream_raises_not_configured(self, cls):
        gateway = cls()
        with pytest.raises(AiNotConfiguredError):
            gateway.stream(GenerationPrompt(user="hello"))

    @pytest.mark.parametrize("cls", ALL_PROVIDERS)
    def test_structured_generate_raises_not_configured(self, cls):
        gateway = cls()
        with pytest.raises(AiNotConfiguredError):
            gateway.structured_generate(
                StructuredGenerationPrompt(user="extract", schema={"type": "object"})
            )


class TestPlaceholderEstimates:
    def test_count_tokens_is_deterministic(self):
        gateway = OpenAIProvider()
        assert gateway.count_tokens("") == 0
        assert gateway.count_tokens("abcd") == 1
        text = "x" * 100
        assert gateway.count_tokens(text) == 25

    def test_estimate_cost_is_zero_without_prices(self):
        gateway = OpenAIProvider()
        assert gateway.estimate_cost(model="m", input_tokens=100, output_tokens=50) == 0.0
