"""AI Core errors (Sprint M11.1).

Application-layer exceptions, following the repository doctrine
(``application/exceptions.py``): framework-free, no HTTP status codes —
the API layer maps them to responses. The route layer will translate
``AiNotConfiguredError`` to 503 and ``UnknownProviderError`` to 422 when
the first generation endpoints land (M11.2+).

M11.1 doctrine: generation on an unconfigured provider is a *domain
state*, not a crash — callers receive ``AiNotConfiguredError`` with a
factual message, and every surface (health API, settings UI) reports
the not-configured state before any call is attempted.
"""
from __future__ import annotations

from app.application.exceptions import ApplicationError


class AiError(ApplicationError):
    """Base class for AI Core errors."""


class AiNotConfiguredError(AiError):
    """The provider has no wired adapter (all M11.1 providers)."""

    code = "ai_not_configured"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UnknownProviderError(AiError):
    """The requested provider id is not part of the catalogue."""

    code = "unknown_ai_provider"

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        super().__init__(f"Unknown AI provider: {provider_id}")


__all__ = ["AiError", "AiNotConfiguredError", "UnknownProviderError"]
