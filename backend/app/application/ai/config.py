"""AI configuration view (Sprint M11.1).

A frozen, application-pure projection of the AI settings the core needs.
``from_settings`` maps the pydantic ``Settings`` object (the repository's
existing config transport) onto this view, keeping the AI layer decoupled
from any concrete settings implementation.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.ai import PROVIDER_KINDS

#: Feature flags surfaced by /ai/health (all default OFF in M11.1).
FEATURE_FLAG_KEYS: tuple[str, ...] = (
    "chat",
    "rag",
    "memory",
    "agents",
    "document_understanding",
    "streaming",
)


@dataclass(frozen=True)
class AiConfigView:
    """Everything the AI Core reads from configuration."""

    enabled: bool
    default_provider: str
    default_model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    streaming_enabled: bool
    feature_flags: dict[str, bool]

    @classmethod
    def from_settings(cls, settings) -> AiConfigView:
        """Project the pydantic settings onto the AI view.

        ``default_provider`` is *not* validated here: an unknown value is
        reported honestly by the health surface (``default_provider_valid``)
        instead of crashing startup or every request.
        """
        return cls(
            enabled=bool(settings.ai_enabled),
            default_provider=str(settings.ai_default_provider or "local"),
            default_model=str(settings.ai_default_model or ""),
            temperature=float(settings.ai_temperature),
            max_tokens=int(settings.ai_max_tokens),
            timeout_seconds=float(settings.ai_timeout_seconds),
            streaming_enabled=bool(settings.ai_streaming_enabled),
            feature_flags={
                "chat": bool(settings.ai_chat_enabled),
                "rag": bool(settings.ai_rag_enabled),
                "memory": bool(settings.ai_memory_enabled),
                "agents": bool(settings.ai_agents_enabled),
                "document_understanding": bool(
                    settings.ai_document_understanding_enabled
                ),
                "streaming": bool(settings.ai_streaming_enabled),
                "summarization": bool(getattr(settings, "ai_summarization_enabled", False)),
                "semantic_search": bool(getattr(settings, "ai_semantic_search_enabled", False)),
            },
        )

    @property
    def default_provider_valid(self) -> bool:
        return self.default_provider in PROVIDER_KINDS


__all__ = ["AiConfigView", "FEATURE_FLAG_KEYS"]
