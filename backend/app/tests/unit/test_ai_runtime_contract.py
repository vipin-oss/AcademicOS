"""Runtime contract tests: provider/model identity & selection semantics
(Sprint M11.3.1 — semantic ownership, beyond syntax).

These verify the RUNTIME contract the architecture guardrails cannot express
statically: provider_id is the configured identity (distinct from kind),
multiple providers of a kind are distinguishable, selection precedence is
correct, ``AI_DEFAULT_MODEL`` influences the runtime default, and health
reports the effective default consistently.
"""
from __future__ import annotations

import pytest

from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.errors import UnknownProviderError
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import ProviderConfig
from app.infrastructure.ai.llm.openai import OpenAIProvider


def _ai_cfg(default_provider: str = "oa") -> AiConfigView:
    return AiConfigView(
        enabled=True, default_provider=default_provider, default_model="",
        temperature=0.0, max_tokens=2048, timeout_seconds=30.0, streaming_enabled=True,
        feature_flags={"chat": False, "rag": False, "memory": False, "agents": False,
                       "document_understanding": False, "streaming": True},
    )


def _gw(pid: str, model: str = "m", base_url: str = "http://x/v1") -> OpenAIProvider:
    return OpenAIProvider(
        ProviderConfig(provider_id=pid, kind="openai", model=model, base_url=base_url)
    )


def _core(gateways: dict, default_provider: str) -> AiCore:
    return AiCore(
        registry=ProviderRegistry(), gateways=gateways,
        config=_ai_cfg(default_provider), default_provider=default_provider,
    )


class TestProviderIdentity:
    def test_provider_id_is_config_identity_not_kind(self):
        gw = _gw("oa", "gpt-4o-mini")
        assert gw.provider_id == "oa"
        assert gw.kind == "openai"
        assert gw.provider_id != gw.kind  # distinct

    def test_health_and_models_report_same_provider_id(self):
        gw = _gw("oa", "gpt-4o-mini")
        assert gw.health().provider_id == "oa"
        assert gw.list_models()[0].provider_id == "oa"  # consistent identity

    def test_two_providers_same_kind_are_distinguishable(self):
        a, b = _gw("oa", "gpt-4o-mini"), _gw("oa2", "gpt-4o")
        assert a.kind == b.kind == "openai"
        assert a.provider_id != b.provider_id  # distinguishable by provider_id

    def test_unconfigured_provider_id_falls_back_to_kind(self):
        gw = OpenAIProvider()  # no config (discovery)
        assert gw.provider_id == gw.kind == "openai"


class TestSelectionContract:
    def test_precedence_override_beats_pin_beats_default(self):
        core = _core({"oa": _gw("oa"), "alt": _gw("alt")}, default_provider="oa")
        assert core.select_provider() == "oa"                      # default
        assert core.select_provider(pinned="alt") == "alt"         # pin > default
        assert core.select_provider(requested="alt", pinned="oa") == "alt"  # override > pin

    def test_unknown_override_raises(self):
        core = _core({"oa": _gw("oa")}, default_provider="oa")
        with pytest.raises(UnknownProviderError):
            core.select_provider(requested="ghost")

    def test_gateway_resolves_default_and_explicit(self):
        core = _core({"oa": _gw("oa"), "alt": _gw("alt")}, default_provider="oa")
        assert core.gateway().provider_id == "oa"
        assert core.gateway("alt").provider_id == "alt"


class _Settings:
    """Minimal settings stand-in for build_ai_core default resolution."""
    ai_enabled = True
    ai_default_provider = ""
    ai_default_model = ""
    ai_temperature = 0.0
    ai_max_tokens = 2048
    ai_timeout_seconds = 30.0
    ai_streaming_enabled = True
    ai_chat_enabled = False
    ai_rag_enabled = False
    ai_memory_enabled = False
    ai_agents_enabled = False
    ai_document_understanding_enabled = False
    ai_providers_json = ""
    assistant_default_model = ""
    assistant_models_json = ""
    assistant_llm_base_url = None
    assistant_llm_model = ""
    assistant_llm_api_key = ""
    assistant_llm_timeout_seconds = 30.0


class TestDefaultModelInfluencesRuntime:
    def test_ai_default_model_selects_matching_provider(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _Settings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1"},'
            ' {"provider_id": "ob", "kind": "openai", "model": "gpt-4o",'
            ' "base_url": "http://y/v1"}]'
        )
        s.ai_default_model = "gpt-4o"  # must pick provider "ob"
        core = build_ai_core(s)
        assert core.gateway().provider_id == "ob"  # default resolved by model
        assert core.gateway().list_models()[0].model_id == "gpt-4o"

    def test_ai_default_provider_id_takes_precedence_over_model(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _Settings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1"},'
            ' {"provider_id": "ob", "kind": "openai", "model": "gpt-4o",'
            ' "base_url": "http://y/v1"}]'
        )
        s.ai_default_provider = "oa"
        s.ai_default_model = "gpt-4o"  # would pick ob, but explicit provider wins
        core = build_ai_core(s)
        assert core.gateway().provider_id == "oa"


class TestHealthRuntimeConsistency:
    def test_health_reports_effective_default(self):
        core = _core({"oa": _gw("oa", base_url="http://x/v1")}, default_provider="oa")
        summary = core.health_summary()
        assert summary.default_provider == "oa"
        assert summary.default_provider_valid is True  # oa is configured/executable
        assert summary.status == "ok"

    def test_health_not_healthy_when_default_not_executable(self):
        # default "oa" configured with NO base_url -> not executable
        core = _core({"oa": _gw("oa", base_url="")}, default_provider="oa")
        summary = core.health_summary()
        assert summary.default_provider_valid is False
        assert summary.status == "not_configured"

    def test_health_error_on_unknown_default(self):
        core = _core({"oa": _gw("oa")}, default_provider="ghost")
        summary = core.health_summary()
        assert summary.status == "error"
        assert summary.default_provider_valid is False
