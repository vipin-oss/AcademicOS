"""Provider placeholders — the honest "Not Configured" gateways (M11.1).

One class per catalogue provider, all sharing the placeholder behavior:
health reports ``not_configured``, generation operations raise
``AiNotConfiguredError`` (there are NO fake AI responses), token/cost
estimates work (deterministic, pure). These files are the future homes
of the real adapters — a later sprint replaces the body of one class
without touching the registry, core, routes or frontend.

Identity (M11.3.1): ``provider_id`` is the configured catalogue identity
(from ``ProviderConfig.provider_id``); ``kind`` is the family. They are
distinct, and multiple providers of the same kind stay distinguishable.
When no config is present (the unconfigured discovery case) ``provider_id``
falls back to ``kind``.

No network, no SDKs, no credentials anywhere in this module.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from app.application.ai.errors import AiNotConfiguredError
from app.application.ai.llm.estimates import estimate_cost_usd, estimate_tokens
from app.application.dtos.ai import (
    KIND_CAPABILITIES,
    NOT_CONFIGURED_DETAIL,
    PROVIDER_KIND_ANTHROPIC,
    PROVIDER_KIND_GOOGLE,
    PROVIDER_KIND_LOCAL,
    PROVIDER_KIND_OLLAMA,
    STATUS_NOT_CONFIGURED,
    GenerationEvent,
    GenerationPrompt,
    GenerationResult,
    ModelInfo,
    ProviderConfig,
    ProviderHealth,
    StructuredGenerationPrompt,
    StructuredGenerationResult,
)


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class NotConfiguredGateway:
    """Shared placeholder behavior for every catalogue provider."""

    display_name: str = ""
    kind: str = ""
    capabilities: tuple[str, ...] = ()

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config

    # ------------------------------------------------------------- identity
    @property
    def provider_id(self) -> str:
        """The configured catalogue identity, NOT the kind. Falls back to the
        kind for the unconfigured discovery case (no config)."""
        if self._config is not None and self._config.provider_id:
            return self._config.provider_id
        return self.kind

    # ------------------------------------------------------------- health
    def health(self) -> ProviderHealth:
        models = self.list_models()
        return ProviderHealth(
            provider_id=self.provider_id,
            display_name=self.display_name,
            kind=self.kind,
            status=STATUS_NOT_CONFIGURED,
            configured=self._config is not None,  # declared
            executable=False,  # no real adapter is wired
            operational=None,
            models_configured=len(models),
            detail=NOT_CONFIGURED_DETAIL.format(
                provider_id=self.provider_id, kind=self.kind
            ),
            checked_at=_utcnow_iso(),
        )

    # -------------------------------------------------------------- models
    def list_models(self) -> tuple[ModelInfo, ...]:
        """The models *declared* in configuration, marked not usable."""
        if self._config is not None and self._config.model:
            return (
                ModelInfo(
                    provider_id=self._config.provider_id,
                    model_id=self._config.model,
                    display_name=self._config.model,
                    capabilities=self.capabilities,
                    configured=False,
                ),
            )
        return ()

    # ---------------------------------------------------------- generation
    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        raise self._not_configured()

    def stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        raise self._not_configured()

    def structured_generate(
        self, prompt: StructuredGenerationPrompt
    ) -> StructuredGenerationResult:
        raise self._not_configured()

    # ------------------------------------------------------ cost utilities
    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def estimate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        del model
        return estimate_cost_usd(
            input_tokens=input_tokens, output_tokens=output_tokens
        )

    # ------------------------------------------------------------ internals
    def _not_configured(self) -> AiNotConfiguredError:
        return AiNotConfiguredError(
            f"Provider '{self.provider_id}' is not configured: no adapter is "
            f"wired for kind '{self.kind}'."
        )


class AnthropicProvider(NotConfiguredGateway):
    display_name = "Anthropic"
    kind = PROVIDER_KIND_ANTHROPIC
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_ANTHROPIC]


class GoogleProvider(NotConfiguredGateway):
    display_name = "Google"
    kind = PROVIDER_KIND_GOOGLE
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_GOOGLE]


class OllamaProvider(NotConfiguredGateway):
    display_name = "Ollama"
    kind = PROVIDER_KIND_OLLAMA
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_OLLAMA]


class LocalProvider(NotConfiguredGateway):
    display_name = "Local"
    kind = PROVIDER_KIND_LOCAL
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_LOCAL]


__all__ = [
    "AnthropicProvider",
    "GoogleProvider",
    "LocalProvider",
    "NotConfiguredGateway",
    "OllamaProvider",
]
