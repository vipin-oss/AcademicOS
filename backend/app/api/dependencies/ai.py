"""AI Core dependency injection (thread-safe singleton — M11.3.3).

The single FastAPI seam through which routes receive the composed AI Core.
The AI Core is built ONCE (lazy singleton) so it owns one consistent gateway
lifecycle - httpx clients are reused across requests, not leaked per request,
and ``AiCore.close()`` releases them.

M11.3.3: initialization and reset are thread-safe (FastAPI runs sync
dependencies in a threadpool, so concurrent first requests could otherwise
build the core twice). Test overrides
(``app.dependency_overrides[get_ai_core]``) bypass this cache entirely.
"""
from __future__ import annotations

import threading

from app.application.ai.core import AiCore
from app.core.config import settings
from app.infrastructure.ai.provider_factory import build_ai_core

_ai_core_singleton: AiCore | None = None
_ai_core_lock = threading.Lock()


def get_ai_core() -> AiCore:
    """The process-wide composed AI Core (test-overridable). Built once,
    thread-safely, so the AI Core owns gateway lifecycle consistently."""
    global _ai_core_singleton
    if _ai_core_singleton is None:
        with _ai_core_lock:
            if _ai_core_singleton is None:  # double-checked locking
                _ai_core_singleton = build_ai_core(settings)
    return _ai_core_singleton


def reset_ai_core_cache() -> None:
    """Drop the cached AI Core (and close its gateways) exactly once,
    thread-safely. Used by the FastAPI shutdown lifecycle and for
    test/config-reload hygiene."""
    global _ai_core_singleton
    with _ai_core_lock:
        if _ai_core_singleton is not None:
            _ai_core_singleton.close()
            _ai_core_singleton = None


__all__ = ["get_ai_core", "reset_ai_core_cache"]
