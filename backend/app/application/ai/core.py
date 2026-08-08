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
    HEALTH_CONFIGURED,
    HEALTH_DISABLED,
    HEALTH_ERROR,
    HEALTH_NOT_CONFIGURED,
    NOT_CONFIGURED_DETAIL,
    PROVIDER_KINDS,
    PROVIDER_LABELS,
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

    def close(self) -> None:
        """Release gateway resources (e.g. httpx clients) owned by the AI Core.

        The AI Core owns the gateway lifecycle (ADR-001 - M11.3.2): one
        consistent lifecycle for every gateway it holds. Best-effort — a
        gateway without ``close()`` (placeholders, fakes) is skipped.
        """
        for gateway in self._gateways.values():
            close = getattr(gateway, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 - cleanup must not raise
                    pass

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
        """DISABLED. Gateway construction outside the catalogue is a
        configuration-authority bypass (ADR-001); production MUST resolve
        providers through :meth:`select_provider` / :meth:`gateway`. Retained
        only so older callers fail loudly instead of silently building an
        untracked gateway."""
        raise UnknownProviderError(
            "AiCore.build_gateway is disabled: resolve providers through "
            "AiCore.gateway / AiCore.select_provider (ADR-001)."
        )

    # ------------------------------------------------------- runtime default
    def effective_default_provider(self) -> str:
        """The runtime-effective default provider id (what ``select_provider``
        uses with no override/pin). Falls back to the configured default name
        when no provider is resolvable, so config/runtime/health agree."""
        if self._default_provider and self._default_provider in self._gateways:
            return self._default_provider
        return self._config.default_provider

    def effective_default_model(self) -> str:
        """The model of the runtime-effective default provider (else the
        configured ``AI_DEFAULT_MODEL``)."""
        gateway = self._effective_gateway()
        if gateway is not None:
            models = gateway.list_models()
            if models:
                return models[0].model_id
        return self._config.default_model

    def _effective_gateway(self):
        if self._default_provider and self._default_provider in self._gateways:
            return self._gateways[self._default_provider]
        return None

    def _default_is_misconfigured(self) -> bool:
        """True when a default was explicitly configured but is neither a
        resolvable provider nor a known kind (a genuine config error)."""
        configured = self._config.default_provider or ""
        if not configured:
            return False
        if configured in self._gateways:
            return False
        return configured not in PROVIDER_KINDS

    # ------------------------------------------------------- health surface
    def health_summary(self) -> AiHealthSummary:
        effective = self._effective_gateway()
        default_executable = effective is not None and effective.health().executable
        if not self._config.enabled:
            status = HEALTH_DISABLED
        elif self._default_is_misconfigured():
            status = HEALTH_ERROR
        elif default_executable:
            status = HEALTH_CONFIGURED
        else:
            status = HEALTH_NOT_CONFIGURED
        return AiHealthSummary(
            status=status,
            ai_enabled=self._config.enabled,
            default_provider=self.effective_default_provider(),
            default_model=self.effective_default_model(),
            default_provider_valid=default_executable,
            providers_total=len(self._provider_order),
            providers_configured=self._executable_kinds(),
            feature_flags=dict(self._config.feature_flags),
            checked_at=_utcnow_iso(),
        )

    def provider_records(self) -> tuple[ProviderRecord, ...]:
        """One row per configured PROVIDER (keyed by its provider_id), so
        multiple providers of the same kind stay distinguishable. A kind with
        no providers yields an honest ``not_configured`` discovery row keyed
        by the kind."""
        records: list[ProviderRecord] = []
        for kind in self._provider_order:
            providers = [gw for gw in self._gateways.values() if _gateway_kind(gw) == kind]
            if providers:
                for gateway in providers:
                    health = gateway.health()
                    records.append(
                        ProviderRecord(
                            provider_id=health.provider_id,
                            display_name=health.display_name,
                            kind=health.kind,
                            status=health.status,
                            configured=health.configured,
                            executable=health.executable,
                            operational=health.operational,
                            models=gateway.list_models(),
                            detail=health.detail,
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
        """The aggregated model catalogue across all configured providers.

        The defaults are the RUNTIME-EFFECTIVE ones (same source as
        :meth:`health_summary`), so ``/ai/models`` and ``/ai/health`` never
        disagree on provider/model identity."""
        models: list[ModelInfo] = []
        for gateway in self._gateways.values():
            models.extend(gateway.list_models())
        return AiModelsSummary(
            default_provider=self.effective_default_provider(),
            default_model=self.effective_default_model(),
            models=tuple(models),
        )

    # ------------------------------------------------------------ internals
    def _executable_kinds(self) -> int:
        """Count discovery kinds that have at least one EXECUTABLE provider
        (real adapter + endpoint) — the runtime-readiness count."""
        executable_kinds = {
            _gateway_kind(gw) for gw in self._gateways.values() if gw.health().executable
        }
        return sum(1 for kind in self._provider_order if kind in executable_kinds)


def _gateway_kind(gateway: LanguageModelGateway) -> str:
    """The kind of a gateway (defaults to its provider_id if unset)."""
    return getattr(gateway, "kind", None) or getattr(gateway, "provider_id", "")


__all__ = ["AiCore"]
