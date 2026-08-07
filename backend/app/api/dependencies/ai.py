"""AI Core dependency injection (Sprint M11.1; lifecycle owned M11.3.2).

The single FastAPI seam through which routes receive the composed AI Core.
The AI Core is built ONCE (lazy singleton) so it owns one consistent gateway
lifecycle — httpx clients are reused across requests, not leaked per request,
and ``AiCore.close()`` releases them. Test overrides
(``app.dependency_overrides[get_ai_core]``) bypass this cache entirely.
"""
from __future__ import annotations

from app.application.ai.core import AiCore
from app.core.config import settings
from app.infrastructure.ai.provider_factory import build_ai_core

_ai_core_singleton: AiCore | None = None


def get_ai_core() -> AiCore:
    """The process-wide composed AI Core (test-overridable). Built once so the
    AI Core owns gateway lifecycle consistently."""
    global _ai_core_singleton
    if _ai_core_singleton is None:
        _ai_core_singleton = build_ai_core(settings)
    return _ai_core_singleton


def reset_ai_core_cache() -> None:
    """Drop the cached AI Core (and close its gateways). For test/config-reload
    hygiene; production has no shutdown manager by design (ADR-001)."""
    global _ai_core_singleton
    if _ai_core_singleton is not None:
        _ai_core_singleton.close()
        _ai_core_singleton = None


__all__ = ["get_ai_core", "reset_ai_core_cache"]
