"""AI Core — the composed capability facade (Sprint M11.1).

``AiCore`` is the single application-side object the API layer talks to:
it owns the provider catalogue (gateways), the configuration view, and
the aggregate queries the health surface exposes (health summary,
provider records, model catalogue). Future sprints extend it with the
router/context/agent capabilities — the constructor grows, the surface
stays.

Pure application code: gateways and registry are injected (the
infrastructure factory composes real adapters; tests inject fakes).
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from app.application.ai.config import AiConfigView
from app.application.ai.errors import UnknownProviderError
from app.application.ai.llm.ports import LanguageModelGateway
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import (
    HEALTH_DISABLED,
    HEALTH_ERROR,
    HEALTH_NOT_CONFIGURED,
    HEALTH_OK,
    STATUS_CONFIGURED,
    AiHealthSummary,
    AiModelsSummary,
    ModelInfo,
    ProviderRecord,
)


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class AiCore:
    """The composed AI capability surface (infrastructure-only in M11.1)."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        gateways: Mapping[str, LanguageModelGateway],
        config: AiConfigView,
        provider_order: Sequence[str] | None = None,
    ) -> None:
        self._registry = registry
        self._gateways = dict(gateways)
        self._config = config
        # Deterministic catalogue order: explicit order, else registration
        # order, else sorted ids.
        if provider_order is None:
            known = registry.known_kinds()
            provider_order = known or tuple(sorted(self._gateways))
        self._provider_order = tuple(provider_order)

    # ------------------------------------------------------------ accessors
    @property
    def config(self) -> AiConfigView:
        return self._config

    @property
    def provider_order(self) -> tuple[str, ...]:
        return self._provider_order

    def gateway(self, provider_id: str | None = None) -> LanguageModelGateway:
        """The gateway for ``provider_id`` (default provider when None).

        Unknown ids raise ``UnknownProviderError`` — the single lookup
        seam future sprints use before any generation call.
        """
        target = provider_id or self._config.default_provider
        gateway = self._gateways.get(target)
        if gateway is None:
            raise UnknownProviderError(target)
        return gateway

    # ------------------------------------------------------- health surface
    def health_summary(self) -> AiHealthSummary:
        if not self._config.enabled:
            status = HEALTH_DISABLED
        elif not self._config.default_provider_valid:
            status = HEALTH_ERROR
        elif self._providers_configured() > 0:
            status = HEALTH_OK
        else:
            status = HEALTH_NOT_CONFIGURED
        return AiHealthSummary(
            status=status,
            ai_enabled=self._config.enabled,
            default_provider=self._config.default_provider,
            default_model=self._config.default_model,
            default_provider_valid=self._config.default_provider_valid,
            providers_total=len(self._provider_order),
            providers_configured=self._providers_configured(),
            feature_flags=dict(self._config.feature_flags),
            checked_at=_utcnow_iso(),
        )

    def provider_records(self) -> tuple[ProviderRecord, ...]:
        """One record per catalogue provider, in deterministic order."""
        records: list[ProviderRecord] = []
        for provider_id in self._provider_order:
            gateway = self._gateways.get(provider_id)
            if gateway is None:
                continue
            health = gateway.health()
            records.append(
                ProviderRecord(
                    provider_id=health.provider_id,
                    display_name=health.display_name,
                    kind=health.kind,
                    status=health.status,
                    configured=health.configured,
                    models=gateway.list_models(),
                    detail=health.detail,
                )
            )
        return tuple(records)

    def model_records(self) -> AiModelsSummary:
        """The aggregated model catalogue across all providers."""
        models: list[ModelInfo] = []
        for provider_id in self._provider_order:
            gateway = self._gateways.get(provider_id)
            if gateway is None:
                continue
            models.extend(gateway.list_models())
        return AiModelsSummary(
            default_provider=self._config.default_provider,
            default_model=self._config.default_model,
            models=tuple(models),
        )

    # ------------------------------------------------------------ internals
    def _providers_configured(self) -> int:
        return sum(
            1
            for provider_id in self._provider_order
            if (g := self._gateways.get(provider_id)) is not None
            and g.health().status == STATUS_CONFIGURED
        )


__all__ = ["AiCore"]
