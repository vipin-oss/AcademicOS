"""AI Core composition root (Sprint M11.3 — ADR-001 configuration authority).

THE single authority for providers, models, credentials, base URLs, generation
policy AND selection. ``AI_PROVIDERS_JSON`` is the authoritative provider
configuration; when it is empty, providers are synthesized from the legacy
``ASSISTANT_*`` settings (DEPRECATED compat — existing deployments keep
working unchanged).

This module owns the only gateway constructor (:func:`build_gateway`) and
:func:`build_ai_core`, which builds the provider-id-keyed catalogue (multiple
providers per kind allowed). Features resolve providers through
``AiCore.select_provider`` / ``AiCore.gateway`` and never construct a provider
or a ``ProviderConfig``.

Lives in the infrastructure layer (it composes infrastructure adapters).
``LlmProviderError`` / retry constants are re-exported for the assistant
translator, which depends on this composition root, not on a concrete provider.
"""
from __future__ import annotations

import json

from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.errors import UnknownProviderError
from app.application.ai.llm.ports import LanguageModelGateway
from app.application.ai.providers.config import parse_provider_configs
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import PROVIDER_KINDS, ProviderConfig
from app.infrastructure.ai.llm.openai import (
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    LlmProviderError,
    OpenAIProvider,
)
from app.infrastructure.ai.llm.placeholders import (
    AnthropicProvider,
    GoogleProvider,
    LocalProvider,
    OllamaProvider,
)

#: Kind -> provider class. The ONLY place the concrete classes are known.
_PROVIDER_CLASSES: dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "ollama": OllamaProvider,
    "local": LocalProvider,
}


def build_gateway(
    config: ProviderConfig | None,
    *,
    kind: str | None = None,
    client=None,
    retry_attempts: int = RETRY_ATTEMPTS,
    retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> LanguageModelGateway:
    """THE single gateway constructor (ADR-001). The only function that
    instantiates a concrete provider. See ``AiCore.build_gateway`` for the
    feature-facing seam; the catalogue is built here through this function."""
    resolved_kind = config.kind if config is not None else kind
    if resolved_kind is None or resolved_kind not in _PROVIDER_CLASSES:
        raise UnknownProviderError(resolved_kind or "")
    cls = _PROVIDER_CLASSES[resolved_kind]
    if client is not None:
        return cls(
            config,
            client=client,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
    return cls(config)



def build_gateway_from_params(
    *,
    kind: str = "openai",
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    client=None,
    retry_attempts: int = RETRY_ATTEMPTS,
    retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> LanguageModelGateway:
    """Construct a gateway from raw parameters (AI Core owns the config).

    The configuration-authority seam: ``ProviderConfig`` is constructed HERE
    (inside the AI Core), never by a feature. Used by the assistant
    translator's legacy test-injection constructor so it does not build a
    ``ProviderConfig`` itself (ADR-001 - the config-authority guardrail).
    """
    config = ProviderConfig(
        provider_id=kind, kind=kind, model=model,
        base_url=base_url, api_key=api_key,
    )
    return build_gateway(
        config, client=client,
        retry_attempts=retry_attempts, retry_backoff_seconds=retry_backoff_seconds,
    )

def build_ai_core(settings) -> AiCore:
    """Compose the AI Core — the single provider/model/config authority.

    ``AI_PROVIDERS_JSON`` is authoritative. When empty, providers are
    synthesized from the legacy ``ASSISTANT_*`` settings (DEPRECATED compat)
    so existing deployments keep working. Malformed ``AI_PROVIDERS_JSON``
    raises ``ValueError`` (a server fault); the legacy path is only reached
    when ``AI_PROVIDERS_JSON`` is empty.
    """
    configs = parse_provider_configs(settings.ai_providers_json)
    if not configs:
        configs = _legacy_provider_configs(settings)  # DEPRECATED compat

    registry = ProviderRegistry()
    for kind in PROVIDER_KINDS:
        registry.register_factory(
            kind, lambda config, k=kind: build_gateway(config, kind=k)
        )

    # Provider-id-keyed catalogue (multiple providers per kind allowed).
    gateways: dict[str, LanguageModelGateway] = {}
    for config in configs:
        gateways[config.provider_id] = registry.build(config)

    default_pid = _resolve_default_provider_id(settings, gateways)
    return AiCore(
        registry=registry,
        gateways=gateways,
        config=AiConfigView.from_settings(settings),
        provider_order=PROVIDER_KINDS,
        default_provider=default_pid,
    )


def _legacy_provider_configs(settings) -> tuple[ProviderConfig, ...]:
    """DEPRECATED: synthesize AI Core providers from legacy ``ASSISTANT_*``
    settings when ``AI_PROVIDERS_JSON`` is empty. Existing deployments keep
    working; new deployments should use ``AI_PROVIDERS_JSON``. The rules
    provider is intentionally NOT synthesized here — it is the assistant's
    always-on deterministic fallback, not an AI Core provider."""
    max_tokens = int(getattr(settings, "ai_max_tokens", 2048))
    temperature = float(getattr(settings, "ai_temperature", 0.0))
    streaming = bool(getattr(settings, "ai_streaming_enabled", True))
    configs: list[ProviderConfig] = []
    raw = (getattr(settings, "assistant_models_json", "") or "").strip()
    if raw:
        try:
            entries = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"assistant_models_json is not valid JSON: {exc}") from exc
        if not isinstance(entries, list):
            raise ValueError("assistant_models_json must be a JSON list.")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("provider_kind") or "llm") != "llm":
                continue  # rules/other -> not an AI Core provider
            configs.append(
                ProviderConfig(
                    provider_id=str(entry.get("id") or ""),
                    kind="openai",
                    model=str(entry.get("model") or ""),
                    base_url=str(entry.get("base_url") or ""),
                    api_key=str(entry.get("api_key") or ""),
                    timeout_seconds=float(entry.get("timeout_seconds") or 30.0),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    streaming_enabled=streaming,
                )
            )
    elif getattr(settings, "assistant_llm_base_url", None):
        configs.append(
            ProviderConfig(
                provider_id="default",
                kind="openai",
                model=str(getattr(settings, "assistant_llm_model", "") or ""),
                base_url=str(settings.assistant_llm_base_url),
                api_key=str(getattr(settings, "assistant_llm_api_key", "") or ""),
                timeout_seconds=float(getattr(settings, "assistant_llm_timeout_seconds", 30.0)),
                max_tokens=max_tokens,
                temperature=temperature,
                streaming_enabled=streaming,
            )
        )
    return tuple(configs)


def _resolve_default_provider_id(settings, gateways: dict) -> str:
    """Resolve the default EXECUTION provider id.

    Precedence (M11.3.1): ``AI_DEFAULT_PROVIDER`` (as a provider id) >
    ``AI_DEFAULT_MODEL`` (the provider whose configured model matches) >
    ``AI_DEFAULT_PROVIDER`` (as a kind) > legacy ``assistant_default_model``
    (deprecated) > first configured provider. ``AI_DEFAULT_MODEL`` therefore
    genuinely influences runtime selection, and the authoritative settings
    take precedence over the legacy compat setting.
    """
    ai_default_provider = str(getattr(settings, "ai_default_provider", "") or "")
    ai_default_model = str(getattr(settings, "ai_default_model", "") or "")
    legacy = str(getattr(settings, "assistant_default_model", "") or "")

    if ai_default_provider and ai_default_provider in gateways:
        return ai_default_provider
    if ai_default_model:
        for pid, gateway in gateways.items():
            if getattr(gateway, "model", "") == ai_default_model:
                return pid
    if ai_default_provider:
        for pid, gateway in gateways.items():
            if getattr(gateway, "kind", None) == ai_default_provider:
                return pid
    if legacy and legacy in gateways:
        return legacy
    if legacy:
        for pid, gateway in gateways.items():
            if getattr(gateway, "kind", None) == legacy:
                return pid
    return next(iter(gateways), "")


__all__ = [
    "RETRY_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS",
    "LlmProviderError",
    "build_ai_core",
    "build_gateway",
    "build_gateway_from_params",
]
