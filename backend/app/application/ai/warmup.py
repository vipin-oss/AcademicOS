"""Model pre-warm and residency state (V3 M1 — audit finding A4).

The V3 audit established that provider HTTP-client pooling, the AI Core
singleton and Ollama-compatible ``keep_alive`` **already exist** in R1. The
only genuinely missing piece was the *boot pre-warm*: without it the first
real user request pays the model-load cost (seconds for a local model), which
is a large part of the observed cold-start latency.

This module is deliberately tiny:

- ``prewarm(ai_core)`` issues ONE minimal generation so the provider loads the
  model into memory and the pooled HTTP client completes its first connection.
- ``warmup_state()`` exposes the result so ``/health`` can report
  ``model_resident`` truthfully (V3 M1 gate).

Discipline:

- Never raises. A failed warm-up degrades the health report; it must never
  block application startup.
- Never fabricates residency. ``resident`` is True only when a real
  generation actually returned.
- No polling, no background thread, no keep-alive loop — ``keep_alive`` on the
  provider config already keeps the model resident (``openai.py`` injects it
  into the request body). Adding a re-warm loop here would be the speculative
  infrastructure V3 forbids.
- **The AI Core is injected, never imported.** This module lives in the
  application layer, so it must not reach into ``app.api`` (enforced by
  ``test_application_guardrails`` / ``test_ai_guardrails``). Composition
  happens at the API/startup boundary, which owns the dependency wiring.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

#: The smallest prompt that still forces a real model load.
_WARMUP_USER = "ok"
_WARMUP_MAX_TOKENS = 1


@dataclass(frozen=True)
class WarmupState:
    """Outcome of the last pre-warm attempt."""

    attempted: bool = False
    resident: bool = False
    model: str = ""
    warmup_ms: float | None = None
    detail: str = ""


_state = WarmupState()
_lock = threading.Lock()


def warmup_state() -> WarmupState:
    """The current (thread-safe) warm-up state."""
    with _lock:
        return _state


def reset_warmup_state() -> None:
    """Drop recorded state (test/config-reload hygiene)."""
    global _state
    with _lock:
        _state = WarmupState()


def prewarm(ai_core) -> WarmupState:
    """Issue one minimal generation so the model becomes resident.

    ``ai_core`` is supplied by the composition root (the FastAPI startup
    hook); this module never resolves it itself — see the layering note in
    the module docstring.

    Returns the resulting :class:`WarmupState`. Never raises.
    """
    global _state

    started = time.perf_counter()
    try:
        if ai_core is None or not ai_core.provider_ids:
            new_state = WarmupState(
                attempted=True, resident=False, detail="no provider configured"
            )
            with _lock:
                _state = new_state
            return new_state

        gateway = ai_core.gateway()
        health = gateway.health()
        if not getattr(health, "executable", False):
            new_state = WarmupState(
                attempted=True,
                resident=False,
                detail="provider not executable (no base_url)",
            )
            with _lock:
                _state = new_state
            return new_state

        from app.application.ai.llm.ports import GenerationPrompt

        prompt = GenerationPrompt(user=_WARMUP_USER, max_tokens=_WARMUP_MAX_TOKENS)
        result = gateway.generate(prompt)
        elapsed = (time.perf_counter() - started) * 1000.0
        new_state = WarmupState(
            attempted=True,
            resident=True,
            model=getattr(result, "model", "") or "",
            warmup_ms=elapsed,
        )
    except Exception as exc:  # noqa: BLE001 — warm-up must never break startup
        new_state = WarmupState(
            attempted=True,
            resident=False,
            warmup_ms=(time.perf_counter() - started) * 1000.0,
            detail=f"{type(exc).__name__}: {exc}"[:200],
        )

    with _lock:
        _state = new_state
    return new_state


__all__ = ["WarmupState", "prewarm", "reset_warmup_state", "warmup_state"]
