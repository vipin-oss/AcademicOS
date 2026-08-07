"""AI Core dependency injection (Sprint M11.1).

The single FastAPI seam through which routes receive the composed AI
Core. Mirrors the assistant's ``get_assistant_provider`` composition
seam: per-request construction from settings, overridable in tests to
inject fakes — routes never build anything themselves.
"""
from __future__ import annotations

from app.application.ai.core import AiCore
from app.core.config import settings
from app.infrastructure.ai.provider_factory import build_ai_core


def get_ai_core() -> AiCore:
    """The composed AI Core for this request (test-overridable)."""
    return build_ai_core(settings)


__all__ = ["get_ai_core"]
