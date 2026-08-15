"""LanguageModelGateway — the provider-independent LLM seam (Sprint M11.1).

THE interface every generative AI capability composes against. The six
operations from the M11.1 brief (snake_case per repository convention):

    health()               -> ProviderHealth      (listModels in brief:
    list_models()          -> tuple[ModelInfo]     snake_case names below)
    generate()             -> GenerationResult
    stream()               -> Iterator[GenerationEvent]
    structured_generate()  -> StructuredGenerationResult
    count_tokens()         -> int
    estimate_cost()        -> float

Doctrine (matches the repository's port style — cf.
``ports/assistant_provider.py``):

- The gateway is a *capability contract*, never a vendor API. Adapters
  map it onto provider wire formats; application code never knows a
  provider exists.
- M11.1 ships only honest placeholders: ``health`` reports
  ``not_configured``, generation operations raise
  :class:`AiNotConfiguredError` — there are NO fake AI responses.
- ``count_tokens`` / ``estimate_cost`` are deterministic local estimates
  (``ai/llm/estimates.py``) so accounting works before any adapter exists.
- Adapters never construct prompts — prompt construction stays in the
  prompt layer (future sprint), exactly like the assistant doctrine.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from app.application.ai.errors import AiNotConfiguredError
from app.application.dtos.ai import (
    GenerationEvent,
    GenerationPrompt,
    GenerationResult,
    ModelInfo,
    ProviderHealth,
    StructuredGenerationPrompt,
    StructuredGenerationResult,
)

__all__ = [
    "AiNotConfiguredError",
    "GenerationEvent",
    "GenerationPrompt",
    "GenerationResult",
    "LanguageModelGateway",
    "ModelInfo",
    "ProviderHealth",
    "StructuredGenerationPrompt",
    "StructuredGenerationResult",
]


@runtime_checkable
class LanguageModelGateway(Protocol):
    """One generative-AI provider behind the AI Core.

    Implementations MUST be deterministic where the protocol allows
    (stable orderings, no randomness) and MUST raise
    :class:`AiNotConfiguredError` (not fake content) when they cannot
    produce a real result.
    """

    provider_id: str
    """Registry id of this provider (e.g. ``"openai"``)."""

    display_name: str
    """Human-facing label (e.g. ``"OpenAI"``)."""

    kind: str
    """Catalogue kind — one of ``PROVIDER_KINDS``."""

    # ------------------------------------------------------------- health
    def health(self) -> ProviderHealth:
        """Configuration/availability status of this provider.

        Never performs network calls in M11.1 (no adapter exists); future
        adapters may add liveness checks behind the same contract.
        """
        ...

    # -------------------------------------------------------------- models
    def list_models(self) -> tuple[ModelInfo, ...]:
        """The models this provider exposes (configured catalogue).

        Deterministic order (declaration order). Models that are declared
        but not usable yet report ``configured=False``.
        """
        ...

    # ---------------------------------------------------------- generation
    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        """One complete generation. Raises ``AiNotConfiguredError`` when
        the provider has no wired adapter."""
        ...

    def stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        """Stream tokens, then one ``complete`` event (or ``error``).

        M11.1: raises ``AiNotConfiguredError`` immediately on iteration.
        """
        ...

    def structured_generate(
        self, prompt: StructuredGenerationPrompt
    ) -> StructuredGenerationResult:
        """One structured generation against a JSON Schema. Raises
        ``AiNotConfiguredError`` when no adapter is wired."""
        ...

    # ------------------------------------------------------ cost utilities
    def count_tokens(self, text: str) -> int:
        """Deterministic token estimate for ``text`` (no tokenizer, no
        network). The estimate contract is defined in ``estimates.py``."""
        ...

    def estimate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimated USD cost of one call. M11.1 returns 0.0 (no cost
        tables configured); future adapters report configured pricing."""
        ...
