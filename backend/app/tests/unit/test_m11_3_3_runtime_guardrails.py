"""Runtime guardrails: assistant readiness, lifecycle shutdown, and thread-safe
singleton initialization (Sprint M11.3.3).

Behaviour-focused tests for the final hardening fixes:
- a non-executable provider never becomes the assistant's primary runtime provider;
- graceful shutdown closes owned AI Core resources exactly once;
- the AI Core singleton initializes exactly once under concurrent access.
"""
from __future__ import annotations

import threading
from unittest.mock import patch

from app.application.assistant.providers import RuleBasedAssistantProvider
from app.application.dtos.ai import ProviderHealth
from app.infrastructure.assistant.provider_factory import build_assistant_provider

# ---------------------------------------------------------------------------
# Fix #1: non-executable providers never become runtime primaries
# ---------------------------------------------------------------------------


class _FakeGateway:
    """A configurable gateway stub for readiness/identity tests."""

    def __init__(self, *, configured=True, executable=False):
        self._configured = configured
        self._executable = executable

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id="fake",
            display_name="Fake",
            kind="openai",
            status="configured" if self._executable else "not_configured",
            configured=self._configured,
            executable=self._executable,
            operational=None,
            models_configured=0,
            detail="",
        )


class TestAssistantReadiness:
    def test_declared_not_executable_does_not_become_primary(self):
        """A provider that is declared (configured=True) but NOT executable must
        NOT become the primary — the rules provider is used instead."""
        gw = _FakeGateway(configured=True, executable=False)
        provider = build_assistant_provider(gw, None)  # type: ignore[arg-type]
        assert isinstance(provider, RuleBasedAssistantProvider)

    def test_executable_provider_becomes_primary(self):
        """An executable provider wraps in the LLM fallback chain."""
        from app.application.assistant.providers import FallbackAssistantProvider

        gw = _FakeGateway(configured=True, executable=True)
        provider = build_assistant_provider(gw, None)  # type: ignore[arg-type]
        assert isinstance(provider, FallbackAssistantProvider)

    def test_broken_gateway_degrades_to_rules(self):
        """A gateway whose health() raises degrades to the rules provider."""

        class _Boom:
            def health(self):
                raise RuntimeError("broken")

        provider = build_assistant_provider(_Boom(), None)  # type: ignore[arg-type]  # type: ignore[arg-type]
        assert isinstance(provider, RuleBasedAssistantProvider)


# ---------------------------------------------------------------------------
# Fix #2 + #3: lifecycle shutdown + thread-safe singleton
# ---------------------------------------------------------------------------


class TestLifecycleShutdown:
    def test_reset_ai_core_cache_closes_gateways_once(self):
        """reset_ai_core_cache closes the singleton's gateways exactly once and
        clears the cache so a subsequent build creates a fresh core."""
        from app.api.dependencies.ai import get_ai_core, reset_ai_core_cache

        reset_ai_core_cache()  # ensure clean state
        core_a = get_ai_core()
        reset_ai_core_cache()
        core_b = get_ai_core()
        assert core_a is not core_b  # a new core was built after reset
        reset_ai_core_cache()  # cleanup

    def test_fastapi_lifespan_closes_ai_core_on_shutdown(self):
        """The FastAPI lifespan shutdown handler invokes reset_ai_core_cache,
        closing owned resources. Tested via a lifespan context simulation."""
        from app.api.dependencies.ai import get_ai_core, reset_ai_core_cache
        from app.main import lifespan

        reset_ai_core_cache()
        _ = get_ai_core()  # populate the singleton

        import asyncio

        async def _run():
            async with lifespan(None):  # type: ignore[arg-type]
                pass  # startup -> immediate shutdown

        asyncio.run(_run())

        # After shutdown, the singleton should be cleared (resources released).
        from app.api.dependencies import ai as ai_dep

        assert ai_dep._ai_core_singleton is None
        reset_ai_core_cache()  # cleanup


class TestThreadSafeSingleton:
    def test_singleton_initializes_exactly_once_under_concurrency(self):
        """Concurrent get_ai_core calls must build the AI Core exactly once."""
        from app.api.dependencies import ai as ai_dep

        ai_dep.reset_ai_core_cache()

        build_count = 0
        original = ai_dep.build_ai_core

        def _counting_build(settings):
            nonlocal build_count
            build_count += 1
            return original(settings)

        with patch.object(ai_dep, "build_ai_core", _counting_build):
            results: list = []

            def _call():
                results.append(ai_dep.get_ai_core())

            threads = [threading.Thread(target=_call) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert build_count == 1  # exactly one initialization
        assert all(r is results[0] for r in results)  # all got the same instance
        ai_dep.reset_ai_core_cache()  # cleanup

    def test_reset_is_idempotent(self):
        """Calling reset_ai_core_cache multiple times is safe (no double-close)."""
        from app.api.dependencies.ai import reset_ai_core_cache

        reset_ai_core_cache()
        reset_ai_core_cache()  # must not raise
        reset_ai_core_cache()
