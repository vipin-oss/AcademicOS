"""Provider placeholders — the honest "Not Configured" gateways (M11.1).

One class per catalogue provider, all sharing the placeholder behavior:
health reports ``not_configured``, generation operations raise
``AiNotConfiguredError`` (there are NO fake AI responses), token/cost
estimates work (deterministic, pure). These files are the future homes
of the real adapters — a later sprint replaces the body of one class
without touching the registry, core, routes or frontend.

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
    """Shared placeholder behavior for every M11.1 provider."""

    provider_id: str = ""
    display_name: str = ""
    kind: str = ""
    capabilities: tuple[str, ...] = ()

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config

    # ------------------------------------------------------------- health
    def health(self) -> ProviderHealth:
        models = self.list_models()
        return ProviderHealth(
            provider_id=self.provider_id,
            display_name=self.display_name,
            kind=self.kind,
            status=STATUS_NOT_CONFIGURED,
            configured=False,
            models_configured=len(models),
            detail=NOT_CONFIGURED_DETAIL.format(
                provider_id=self.provider_id, kind=self.kind
            ),
            checked_at=_utcnow_iso(),
        )

    # -------------------------------------------------------------- models
    def list_models(self) -> tuple[ModelInfo, ...]:
        """The models *declared* in configuration, marked not usable.

        ``configured=False`` keeps the settings surface honest: the admin
        sees the intended model, but no adapter can serve it yet.
        """
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
        # No cost tables in M11.1 — an honest 0.0, never a fabricated price.
        del model
        return estimate_cost_usd(
            input_tokens=input_tokens, output_tokens=output_tokens
        )

    # ------------------------------------------------------------ internals
    def _not_configured(self) -> AiNotConfiguredError:
        return AiNotConfiguredError(
            f"Provider '{self.provider_id}' is not configured: no adapter is "
            f"wired for kind '{self.kind}' (planned for a later M11 sprint)."
        )


class AnthropicProvider(NotConfiguredGateway):
    provider_id = PROVIDER_KIND_ANTHROPIC
    display_name = "Anthropic"
    kind = PROVIDER_KIND_ANTHROPIC
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_ANTHROPIC]


class GoogleProvider(NotConfiguredGateway):
    provider_id = PROVIDER_KIND_GOOGLE
    display_name = "Google"
    kind = PROVIDER_KIND_GOOGLE
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_GOOGLE]


class OllamaProvider(NotConfiguredGateway):
    provider_id = PROVIDER_KIND_OLLAMA
    display_name = "Ollama"
    kind = PROVIDER_KIND_OLLAMA
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_OLLAMA]


class LocalProvider(NotConfiguredGateway):
    provider_id = PROVIDER_KIND_LOCAL
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
