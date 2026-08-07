"""AI Core — the composed capability facade (Sprint M11.3 — ADR-001 authority).

The single application-side authority for providers, models, credentials,
base URLs, generation policy AND selection. Features (the assistant, and
future chat/RAG/…) resolve a provider through :meth:`select_provider` and
:meth:`gateway` and NEVER construct a provider or a ``ProviderConfig``.

Catalogue model (M11.3): the catalogue is **provider-id-keyed** — multiple
providers per kind are allowed (e.g. two OpenAI-compatible endpoints). The
health surface projects the five discovery *kinds* (always present), aggregating
the providers of each kind, so ``/ai/health`` stays a stable 5-kind view while
execution addresses individual providers by id.

Pure application code: gateways and registry are injected (the infrastructure
factory composes real adapters; tests inject fakes).
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
    NOT_CONFIGURED_DETAIL,
    PROVIDER_KINDS,
    PROVIDER_LABELS,
    STATUS_CONFIGURED,
    STATUS_NOT_CONFIGURED,
    AiHealthSummary,
    AiModelsSummary,
    ModelInfo,
    ProviderConfig,
    ProviderRecord,
)


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class AiCore:
    """The composed AI capability + selection authority."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        gateways: Mapping[str, LanguageModelGateway],
        config: AiConfigView,
        provider_order: Sequence[str] | None = None,
        default_provider: str | None = None,
    ) -> None:
        self._registry = registry
        self._gateways = dict(gateways)  # provider_id -> gateway
        self._config = config
        # Discovery KIND order for the health surface (always the 5 kinds).
        self._provider_order = tuple(provider_order) if provider_order is not None else PROVIDER_KINDS
        # Default EXECUTION provider id (a provider_id, not a kind). Falls back
        # to the configured default (a kind, for display/validity) when unset.
        self._default_provider = default_provider or config.default_provider

    # ------------------------------------------------------------ accessors
    @property
    def config(self) -> AiConfigView:
        return self._config

    @property
    def provider_order(self) -> tuple[str, ...]:
        """Discovery kind order (the 5 kinds) — for the health surface."""
        return self._provider_order

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Configured provider ids in declaration order (for selection)."""
        return tuple(self._gateways)

    def has_provider(self, provider_id: str) -> bool:
        return provider_id in self._gateways

    # ---------------------------------------------------------- selection
    def gateway(self, provider_id: str | None = None) -> LanguageModelGateway:
        """The gateway for ``provider_id`` (the default when None).

        Unknown ids raise ``UnknownProviderError``. THE seam a feature uses to
        obtain a transport gateway — it never constructs a provider.
        """
        target = provider_id or self._default_provider
        gateway = self._gateways.get(target)
        if gateway is None:
            raise UnknownProviderError(target)
        return gateway

    def select_provider(
        self,
        requested: str | None = None,
        pinned: str | None = None,
    ) -> str:
        """Resolve a provider id: explicit override > conversation pin >
        configured default. Unknown override raises ``UnknownProviderError``.
        AI Core owns provider/model selection (ADR-001).
        """
        if requested:
            if requested not in self._gateways:
                raise UnknownProviderError(requested)
            return requested
        if pinned and pinned in self._gateways:
            return pinned
        if self._default_provider not in self._gateways:
            raise UnknownProviderError(self._default_provider or "<none>")
        return self._default_provider

    def build_gateway(self, config: ProviderConfig) -> LanguageModelGateway:
        """Construct a gateway for an ad-hoc config (delegates to the
        registry). Kept for completeness; production selection uses the
        pre-built provider-id-keyed catalogue."""
        return self._registry.build(config)

    # ------------------------------------------------------- health surface
    def health_summary(self) -> AiHealthSummary:
        if not self._config.enabled:
            status = HEALTH_DISABLED
        elif not self._config.default_provider_valid:
            status = HEALTH_ERROR
        elif self._configured_kinds() > 0:
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
            providers_configured=self._configured_kinds(),
            feature_flags=dict(self._config.feature_flags),
            checked_at=_utcnow_iso(),
        )

    def provider_records(self) -> tuple[ProviderRecord, ...]:
        """One record per discovery KIND, aggregating its providers. A kind
        with no providers yields an honest ``not_configured`` discovery row."""
        records: list[ProviderRecord] = []
        for kind in self._provider_order:
            providers = [gw for gw in self._gateways.values() if _gateway_kind(gw) == kind]
            if providers:
                models = tuple(m for gw in providers for m in gw.list_models())
                configured = any(gw.health().configured for gw in providers)
                ref_health = providers[0].health()
                records.append(
                    ProviderRecord(
                        provider_id=kind,
                        display_name=ref_health.display_name,
                        kind=kind,
                        status=STATUS_CONFIGURED if configured else STATUS_NOT_CONFIGURED,
                        configured=configured,
                        models=models,
                        detail=ref_health.detail,
                    )
                )
            else:
                records.append(
                    ProviderRecord(
                        provider_id=kind,
                        display_name=PROVIDER_LABELS.get(kind, kind),
                        kind=kind,
                        status=STATUS_NOT_CONFIGURED,
                        configured=False,
                        models=(),
                        detail=NOT_CONFIGURED_DETAIL.format(provider_id=kind, kind=kind),
                    )
                )
        return tuple(records)

    def model_records(self) -> AiModelsSummary:
        """The aggregated model catalogue across all configured providers."""
        models: list[ModelInfo] = []
        for gateway in self._gateways.values():
            models.extend(gateway.list_models())
        return AiModelsSummary(
            default_provider=self._config.default_provider,
            default_model=self._config.default_model,
            models=tuple(models),
        )

    # ------------------------------------------------------------ internals
    def _configured_kinds(self) -> int:
        configured_kinds = {
            _gateway_kind(gw) for gw in self._gateways.values() if gw.health().configured
        }
        return sum(1 for kind in self._provider_order if kind in configured_kinds)


def _gateway_kind(gateway: LanguageModelGateway) -> str:
    """The kind of a gateway (defaults to its provider_id if unset)."""
    return getattr(gateway, "kind", None) or getattr(gateway, "provider_id", "")


__all__ = ["AiCore"]
