"""AI Core composition root (Sprint M11.1; revised M11.2.1 — ADR-001).

THE single transport-composition authority for AcademicOS. This module owns
the only gateway constructor in the codebase — :func:`build_gateway` — and
the only place a concrete provider class is imported or instantiated. Every
gateway in the system, catalogue or feature, is created here:

- :func:`build_ai_core` builds the discovery catalogue (one gateway per
  provider kind) from ``AI_PROVIDERS_JSON`` via :func:`build_gateway`.
- :class:`AiCore.build_gateway` exposes the same constructor to features (the
  assistant consumes the AI Core; it never imports a concrete provider).

No route, use case, service, or other feature module may import or construct a
concrete provider — the architecture guardrails
(``test_ai_composition_authority``) enforce this. Lives in the infrastructure
layer because it composes infrastructure adapters.

``LlmProviderError`` / retry constants are re-exported here so the assistant's
translator depends on the composition root, not on a concrete provider module.
"""
from __future__ import annotations

from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.errors import UnknownProviderError
from app.application.ai.llm.ports import LanguageModelGateway
from app.application.ai.providers.config import configs_by_kind, parse_provider_configs
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

#: Kind -> provider class. The ``openai`` kind is the REAL adapter
#: (Sprint M11.2 — ADR-001): it owns the generative transport. The other
#: four remain honest "Not Configured" placeholders until their sprints.
#: This mapping — and ONLY this mapping — knows the concrete classes.
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
    """THE single gateway constructor (ADR-001).

    The only function in the codebase that instantiates a concrete provider.
    All gateway creation flows through here:

    - the AI Core catalogue (via :func:`build_ai_core`'s registry factories);
    - features that need an ad-hoc gateway, through :meth:`AiCore.build_gateway`
      (which delegates to the registry, whose factories call this function).

    ``kind`` resolves the concrete class when ``config`` is ``None`` (an
    unconfigured catalogue slot). ``client`` / ``retry_*`` are the test
    transport-injection knobs (only the real OpenAI adapter honours them; the
    honest placeholders ignore them via their simpler constructors, reached
    only when ``client is None``).
    """
    resolved_kind = config.kind if config is not None else kind
    if resolved_kind is None or resolved_kind not in _PROVIDER_CLASSES:
        raise UnknownProviderError(resolved_kind or "")
    cls = _PROVIDER_CLASSES[resolved_kind]
    if client is not None:
        # Transport injection (tests): only the real adapter accepts a client.
        return cls(
            config,
            client=client,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
    return cls(config)


def build_ai_core(settings) -> AiCore:
    """Compose the AI Core from application settings.

    Never raises for missing AI configuration — an empty
    ``AI_PROVIDERS_JSON`` yields the honest not-configured catalogue.
    Malformed configuration raises ``ValueError`` (a server fault, per
    the ``registry_from_settings`` doctrine). Every catalogue gateway is
    built through :func:`build_gateway` — there is no second constructor.
    """
    configs = parse_provider_configs(settings.ai_providers_json)
    by_kind = configs_by_kind(configs)

    registry = ProviderRegistry()
    for kind in PROVIDER_KINDS:
        # The registry factories are thin closures over the SINGLE constructor.
        registry.register_factory(
            kind, lambda config, k=kind: build_gateway(config, kind=k)
        )

    gateways = registry.build_catalogue(PROVIDER_KINDS, by_kind)
    return AiCore(
        registry=registry,
        gateways=gateways,
        config=AiConfigView.from_settings(settings),
        provider_order=PROVIDER_KINDS,
    )


__all__ = [
    "RETRY_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS",
    "LlmProviderError",
    "build_ai_core",
    "build_gateway",
]
