"""AI Core composition root (Sprint M11.1).

The single construction site for the AI Core — mirrors
``infrastructure/assistant/provider_factory.py`` doctrine: lives in the
infrastructure layer because it composes infrastructure adapters; no
route, use case or service builds a core itself.

M11.1 registers the five placeholder factories (the discovery catalogue)
and builds every gateway from ``AI_PROVIDERS_JSON``. A future sprint
adds a real adapter by registering its factory here — nothing else in
the system changes (the "implement only an adapter" contract).
"""
from __future__ import annotations

from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.providers.config import configs_by_kind, parse_provider_configs
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import PROVIDER_KINDS
from app.infrastructure.ai.llm.openai import OpenAIProvider
from app.infrastructure.ai.llm.placeholders import (
    AnthropicProvider,
    GoogleProvider,
    LocalProvider,
    OllamaProvider,
)

#: Kind -> provider class. The ``openai`` kind is the REAL adapter
#: (Sprint M11.2 — ADR-001): it owns the generative transport and is the
#: single such owner in the codebase. The other four remain honest
#: "Not Configured" placeholders until their sprints. Registering a real
#: adapter here — and only here — is the entire change the rest of the
#: system sees.
_PROVIDER_CLASSES: dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "ollama": OllamaProvider,
    "local": LocalProvider,
}


def build_ai_core(settings) -> AiCore:
    """Compose the AI Core from application settings.

    Never raises for missing AI configuration — an empty
    ``AI_PROVIDERS_JSON`` yields the honest not-configured catalogue.
    Malformed configuration raises ``ValueError`` (a server fault, per
    the ``registry_from_settings`` doctrine).
    """
    configs = parse_provider_configs(settings.ai_providers_json)
    by_kind = configs_by_kind(configs)

    registry = ProviderRegistry()
    for kind in PROVIDER_KINDS:
        provider_cls = _PROVIDER_CLASSES[kind]
        registry.register_factory(
            kind, lambda config, cls=provider_cls: cls(config)
        )

    gateways = registry.build_catalogue(PROVIDER_KINDS, by_kind)
    return AiCore(
        registry=registry,
        gateways=gateways,
        config=AiConfigView.from_settings(settings),
        provider_order=PROVIDER_KINDS,
    )


__all__ = ["build_ai_core"]
