"""Unit tests: AI DTOs (Sprint M11.1)."""
from __future__ import annotations

import pytest

from app.application.dtos.ai import (
    PROVIDER_KIND_OPENAI,
    PROVIDER_KINDS,
    GenerationEvent,
    GenerationPrompt,
    GenerationResult,
    ModelInfo,
    ProviderConfig,
    ProviderHealth,
    ProviderRecord,
    StructuredGenerationPrompt,
    StructuredGenerationResult,
    TokenUsage,
    health_summary_dict,
    model_info_dict,
    models_summary_dict,
    provider_record_dict,
)


class TestProviderConfig:
    def test_valid_config(self):
        cfg = ProviderConfig(provider_id="openai-main", kind="openai", model="gpt-4o-mini")
        assert cfg.provider_id == "openai-main"
        assert cfg.kind == "openai"
        assert cfg.model == "gpt-4o-mini"
        assert cfg.streaming_enabled is True

    def test_empty_provider_id_rejected(self):
        with pytest.raises(ValueError):
            ProviderConfig(provider_id="  ", kind="openai")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError, match="Unknown provider kind"):
            ProviderConfig(provider_id="x", kind="bedrock")

    def test_invalid_numeric_ranges_rejected(self):
        with pytest.raises(ValueError):
            ProviderConfig(provider_id="x", kind="openai", timeout_seconds=0)
        with pytest.raises(ValueError):
            ProviderConfig(provider_id="x", kind="openai", max_tokens=0)
        with pytest.raises(ValueError):
            ProviderConfig(provider_id="x", kind="openai", temperature=2.5)


class TestModelInfo:
    def test_valid(self):
        info = ModelInfo(
            provider_id="openai",
            model_id="gpt-4o-mini",
            display_name="GPT-4o mini",
            context_window=128000,
            capabilities=("chat", "stream"),
            configured=False,
        )
        assert info.context_window == 128000
        assert info.configured is False

    def test_empty_ids_rejected(self):
        with pytest.raises(ValueError):
            ModelInfo(provider_id="", model_id="m")
        with pytest.raises(ValueError):
            ModelInfo(provider_id="p", model_id=" ")

    def test_bad_context_window_rejected(self):
        with pytest.raises(ValueError):
            ModelInfo(provider_id="p", model_id="m", context_window=0)


class TestGenerationContracts:
    def test_generation_prompt_requires_user(self):
        with pytest.raises(ValueError):
            GenerationPrompt(user="")
        with pytest.raises(ValueError):
            GenerationPrompt(user="ok", temperature=3.0)
        with pytest.raises(ValueError):
            GenerationPrompt(user="ok", max_tokens=0)

    def test_generation_result_requires_model(self):
        with pytest.raises(ValueError):
            GenerationResult(text="hi", model="")

    def test_token_usage_negative_rejected(self):
        with pytest.raises(ValueError):
            TokenUsage(input_tokens=-1, output_tokens=0)

    def test_generation_event_kinds(self):
        assert GenerationEvent(kind="token", delta="x").kind == "token"
        assert GenerationEvent(kind="complete").kind == "complete"
        with pytest.raises(ValueError):
            GenerationEvent(kind="nope")

    def test_structured_prompt_requires_schema(self):
        with pytest.raises(ValueError):
            StructuredGenerationPrompt(user="q", schema={})
        with pytest.raises(ValueError):
            StructuredGenerationPrompt(user="q", schema=[1, 2])

    def test_structured_result_requires_object(self):
        with pytest.raises(ValueError):
            StructuredGenerationResult(value=[1], raw_text="x", model="m")


class TestHealthViews:
    def test_provider_health_status_validation(self):
        with pytest.raises(ValueError):
            ProviderHealth(
                provider_id="openai",
                display_name="OpenAI",
                kind="openai",
                status="bogus",
                configured=False,
                models_configured=0,
                detail="",
            )

    def test_provider_record_dict(self):
        record = ProviderRecord(
            provider_id="openai",
            display_name="OpenAI",
            kind="openai",
            status="not_configured",
            configured=False,
            models=(ModelInfo(provider_id="openai", model_id="m", configured=False),),
            detail="not wired",
        )
        payload = provider_record_dict(record)
        assert payload["provider_id"] == "openai"
        assert payload["models"][0]["model_id"] == "m"
        assert payload["models"][0]["configured"] is False
        assert payload["models"][0]["capabilities"] == []

    def test_serialization_helpers_are_deterministic(self):
        info = ModelInfo(provider_id="p", model_id="m", capabilities=("chat",))
        assert model_info_dict(info) == model_info_dict(info)
        assert health_summary_dict.__name__  # importable
        assert models_summary_dict.__name__  # importable


class TestCatalogue:
    def test_provider_kinds_are_stable(self):
        assert PROVIDER_KINDS == (
            "openai",
            "anthropic",
            "google",
            "ollama",
            "local",
        )
        assert PROVIDER_KIND_OPENAI == "openai"
