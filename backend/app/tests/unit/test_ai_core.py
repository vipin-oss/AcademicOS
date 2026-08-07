"""Unit tests: AiCore aggregation + AI use cases (Sprint M11.1).

Fake gateways only — the core must never depend on adapters.
"""
from __future__ import annotations

import pytest

from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.errors import UnknownProviderError
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import (
    HEALTH_DISABLED,
    HEALTH_ERROR,
    HEALTH_NOT_CONFIGURED,
    HEALTH_OK,
    STATUS_CONFIGURED,
    STATUS_NOT_CONFIGURED,
    ModelInfo,
    ProviderConfig,
    ProviderHealth,
)
from app.application.use_cases.ai.get_ai_health import GetAiHealthUseCase
from app.application.use_cases.ai.list_ai_models import ListAiModelsUseCase
from app.application.use_cases.ai.list_ai_providers import ListAiProvidersUseCase


class _FakeGateway:
    """A configurable fake implementing the gateway surface the core uses."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        kind: str,
        *,
        configured: bool = False,
        models: tuple[ModelInfo, ...] = (),
        detail: str = "",
    ) -> None:
        self.provider_id = provider_id
        self.display_name = display_name
        self.kind = kind
        self._configured = configured
        self._models = models
        self._detail = detail

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            display_name=self.display_name,
            kind=self.kind,
            status=STATUS_CONFIGURED if self._configured else STATUS_NOT_CONFIGURED,
            configured=True,  # declared (fakes represent real catalogue entries)
            executable=self._configured,  # can actually run
            operational=None,
            models_configured=len(self._models),
            detail=self._detail,
            checked_at="2026-08-07T00:00:00+00:00",
        )

    def list_models(self) -> tuple[ModelInfo, ...]:
        return self._models


def _config(**overrides) -> AiConfigView:
    base = {
        "enabled": True,
        "default_provider": "local",
        "default_model": "",
        "temperature": 0.0,
        "max_tokens": 2048,
        "timeout_seconds": 30.0,
        "streaming_enabled": True,
        "feature_flags": {
            "chat": False,
            "rag": False,
            "memory": False,
            "agents": False,
            "document_understanding": False,
            "streaming": True,
        },
    }
    base.update(overrides)
    return AiConfigView(**base)


def _core(
    *,
    gateways=None,
    config: AiConfigView | None = None,
    order: tuple[str, ...] | None = None,
) -> AiCore:
    registry = ProviderRegistry()

    def _register(gateway: _FakeGateway):
        def factory(_config: ProviderConfig | None) -> _FakeGateway:
            return gateway

        registry.register_factory(gateway.kind, factory)

    gateways = gateways or {
        "openai": _FakeGateway("openai", "OpenAI", "openai"),
        "anthropic": _FakeGateway("anthropic", "Anthropic", "anthropic"),
        "google": _FakeGateway("google", "Google", "google"),
        "ollama": _FakeGateway("ollama", "Ollama", "ollama"),
        "local": _FakeGateway("local", "Local", "local"),
    }
    for gateway in gateways.values():
        _register(gateway)
    return AiCore(
        registry=registry,
        gateways=gateways,
        config=config or _config(),
        provider_order=order,
    )


class TestAiCoreHealth:
    def test_not_configured_when_no_provider_is_configured(self):
        core = _core()
        summary = core.health_summary()
        assert summary.status == HEALTH_NOT_CONFIGURED
        assert summary.providers_total == 5
        assert summary.providers_configured == 0
        assert summary.ai_enabled is True

    def test_ok_when_default_provider_is_configured(self):
        local = _FakeGateway("local", "Local", "local", configured=True)
        core = _core(
            gateways={
                "openai": _FakeGateway("openai", "OpenAI", "openai"),
                "local": local,
            },
            order=("openai", "local"),
        )
        summary = core.health_summary()
        assert summary.status == HEALTH_OK
        assert summary.providers_configured == 1

    def test_disabled_when_ai_disabled(self):
        core = _core(config=_config(enabled=False))
        assert core.health_summary().status == HEALTH_DISABLED

    def test_error_when_default_provider_unknown(self):
        core = _core(config=_config(default_provider="oepnai"))
        summary = core.health_summary()
        assert summary.status == HEALTH_ERROR
        assert summary.default_provider_valid is False

    def test_feature_flags_surface_in_summary(self):
        summary = _core().health_summary()
        assert summary.feature_flags["rag"] is False


class TestAiCoreProviders:
    def test_provider_records_in_catalogue_order(self):
        core = _core(order=("google", "openai", "local"))
        records = core.provider_records()
        assert [r.provider_id for r in records] == ["google", "openai", "local"]
        assert all(r.status == STATUS_NOT_CONFIGURED for r in records)
        assert all(r.executable is False for r in records)  # not ready to run

    def test_provider_record_carries_models(self):
        local = _FakeGateway(
            "local",
            "Local",
            "local",
            models=(ModelInfo(provider_id="local", model_id="qwen2.5:7b", configured=False),),
        )
        core = _core(gateways={"local": local}, order=("local",))
        records = core.provider_records()
        assert records[0].models[0].model_id == "qwen2.5:7b"
        assert records[0].models[0].configured is False


class TestAiCoreModels:
    def test_models_aggregated_across_providers(self):
        openai = _FakeGateway(
            "openai",
            "OpenAI",
            "openai",
            models=(ModelInfo(provider_id="openai", model_id="gpt-4o-mini", configured=False),),
        )
        local = _FakeGateway(
            "local",
            "Local",
            "local",
            models=(ModelInfo(provider_id="local", model_id="qwen2.5:7b", configured=False),),
        )
        core = _core(gateways={"openai": openai, "local": local}, order=("openai", "local"))
        summary = core.model_records()
        assert summary.default_provider == "local"
        assert [m.model_id for m in summary.models] == ["gpt-4o-mini", "qwen2.5:7b"]

    def test_no_models_when_nothing_configured(self):
        assert _core().model_records().models == ()


class TestAiCoreGateway:
    def test_gateway_returns_default_provider(self):
        core = _core()
        gateway = core.gateway()
        assert gateway.provider_id == "local"

    def test_gateway_returns_requested_provider(self):
        core = _core()
        assert core.gateway("openai").provider_id == "openai"

    def test_gateway_unknown_provider_raises(self):
        core = _core()
        with pytest.raises(UnknownProviderError):
            core.gateway("bedrock")


class TestAiUseCases:
    def test_get_ai_health(self):
        core = _core()
        summary = GetAiHealthUseCase(core).execute()
        assert summary.status == HEALTH_NOT_CONFIGURED

    def test_list_ai_providers(self):
        core = _core()
        records = ListAiProvidersUseCase(core).execute()
        assert len(records) == 5

    def test_list_ai_models(self):
        core = _core()
        summary = ListAiModelsUseCase(core).execute()
        assert summary.models == ()
