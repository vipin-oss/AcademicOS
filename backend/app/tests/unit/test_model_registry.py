"""Unit tests for the model registry (Sprint-7 M1).

Registration, lookup, default selection, duplicate rejection, invalid
model/provider handling, the legacy-settings fallback, and the provider
factory (pluggable providers, one construction site).
"""
from __future__ import annotations

import pytest

from app.application.services.model_registry import (
    DEFAULT_MODEL_ID,
    PROVIDER_KIND_RULES,
    ModelRegistry,
    ModelSpec,
    registry_from_settings,
)
from app.infrastructure.assistant.provider_factory import build_provider


class _Settings:
    """Minimal settings stand-in with the legacy fields."""

    assistant_default_model = "default"
    assistant_models_json = ""
    assistant_llm_base_url = None
    assistant_llm_model = "academicos-default"
    assistant_llm_api_key = ""
    assistant_llm_timeout_seconds = 30.0


def test_register_and_lookup():
    registry = ModelRegistry()
    spec = registry.register(ModelSpec(id="a", model="model-a", base_url="http://x/v1"))
    assert registry.get("a") is spec
    assert registry.all() == [spec]
    assert registry.get("a").model == "model-a"
    assert registry.get("a").is_llm


def test_duplicate_registration_rejected():
    registry = ModelRegistry()
    registry.register(ModelSpec(id="a", model="m"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ModelSpec(id="a", model="m2"))


def test_unknown_model_lookup_raises():
    registry = ModelRegistry()
    with pytest.raises(KeyError, match="Unknown model"):
        registry.get("ghost")
    with pytest.raises(KeyError):
        registry.default()  # nothing registered


def test_invalid_model_spec_rejected():
    with pytest.raises(ValueError, match="empty"):
        ModelSpec(id="", model="m")
    with pytest.raises(ValueError, match="empty"):
        ModelSpec(id="a", model="")
    with pytest.raises(ValueError, match="provider kind"):
        ModelSpec(id="a", model="m", provider_kind="unknown")


def test_default_selection():
    registry = ModelRegistry(default_id="b")
    registry.register(ModelSpec(id="a", model="m1"))
    registry.register(ModelSpec(id="b", model="m2"))
    assert registry.default().id == "b"
    # Unknown default id -> deterministic first-registered fallback.
    registry2 = ModelRegistry(default_id="nope")
    registry2.register(ModelSpec(id="x", model="m"))
    assert registry2.default().id == "x"


def test_registry_from_empty_settings_legacy_fallback():
    settings = _Settings()
    registry = registry_from_settings(settings)
    # Rules always registered; default synthesized from legacy settings.
    assert registry.get("rules").provider_kind == PROVIDER_KIND_RULES
    default = registry.default()
    assert default.id == DEFAULT_MODEL_ID
    assert default.provider_kind == PROVIDER_KIND_RULES  # no base_url configured


def test_registry_from_settings_with_llm_legacy():
    settings = _Settings()
    settings.assistant_llm_base_url = "http://llm:8000/v1"
    settings.assistant_llm_model = "my-model"
    registry = registry_from_settings(settings)
    default = registry.default()
    assert default.is_llm
    assert default.base_url == "http://llm:8000/v1"
    assert default.model == "my-model"


def test_registry_from_models_json():
    settings = _Settings()
    settings.assistant_models_json = (
        '[{"id": "main", "base_url": "http://a/v1", "model": "m1"},'
        ' {"id": "alt", "base_url": "http://b/v1", "model": "m2",'
        ' "timeout_seconds": 5}]'
    )
    settings.assistant_default_model = "main"
    registry = registry_from_settings(settings)
    assert registry.default().id == "main"
    assert registry.get("alt").timeout_seconds == 5.0
    assert len(registry.all()) == 3  # rules + main + alt


def test_registry_from_bad_json_raises():
    settings = _Settings()
    settings.assistant_models_json = "{not json"
    with pytest.raises(ValueError, match="valid JSON"):
        registry_from_settings(settings)


def test_build_provider_rules_kind():
    from app.application.assistant.providers import RuleBasedAssistantProvider

    registry = ModelRegistry()
    spec = registry.register(
        ModelSpec(id="r", model="rules-v1", provider_kind=PROVIDER_KIND_RULES)
    )
    provider = build_provider(spec, repository=None)  # type: ignore[arg-type]
    assert isinstance(provider, RuleBasedAssistantProvider)


def test_build_provider_llm_kind_is_fallback_chain():
    from app.application.assistant.providers import FallbackAssistantProvider

    spec = ModelSpec(id="l", model="m", base_url="http://llm:8000/v1")
    provider = build_provider(spec, repository=None)  # type: ignore[arg-type]
    assert isinstance(provider, FallbackAssistantProvider)
    assert provider.name == "llm-v1+rules-v1"


def test_registry_from_settings_with_explicit_rules_entry():
    """A configuration declaring its own 'rules' entry must not collide
    with the implicit rules provider (regression: duplicate-id 500)."""
    settings = _Settings()
    settings.assistant_models_json = (
        '[{"id": "main", "base_url": "http://a/v1", "model": "m1"},'
        ' {"id": "rules", "provider_kind": "rules", "model": "rules-v1"}]'
    )
    settings.assistant_default_model = "main"
    registry = registry_from_settings(settings)
    assert registry.get("rules").provider_kind == PROVIDER_KIND_RULES
    assert registry.default().id == "main"
    assert len(registry.all()) == 2  # main + rules (not duplicated)
