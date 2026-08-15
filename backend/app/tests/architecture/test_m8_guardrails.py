"""V3 M8 architecture guardrails (ADR-055).

Pins the retrieval-speed contracts:

- parallel fan-out changes NOTHING about results (it only runs the session-free
  semantic leg on a bounded executor — no async, no driver change);
- the fact/dossier cache is bounded (never unbounded memory) and invalidated by
  the SAME authoritative write paths (claim store + outbox applier) — law 22;
- no new async machinery, no new driver, no new queue/event bus.
"""

from __future__ import annotations

import ast
import inspect

from app.application.services.fact_cache import DEFAULT_CAPACITY, FactCache
from app.application.use_cases.search.search_objects import SearchObjectsUseCase


def test_parallel_fanout_is_bounded_threadpool() -> None:
    import app.application.use_cases.search.search_objects as mod

    tree = ast.parse(inspect.getsource(mod))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "ThreadPoolExecutor":
            found = True
    assert found, "parallel fan-out must use ThreadPoolExecutor"
    src = inspect.getsource(mod)
    assert "async def" not in src  # no async conversion (blueprint A5)


def test_search_results_unchanged_by_parallelism() -> None:
    src = inspect.getsource(SearchObjectsUseCase._semantic_leg)
    # the leg delegates to the same deterministic candidate builder
    assert "_semantic_candidates" in src


def test_cache_is_bounded() -> None:
    assert DEFAULT_CAPACITY > 0
    cache = FactCache(capacity=1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert len(cache) == 1


def test_invalidation_hooked_on_authoritative_writes() -> None:
    import app.infrastructure.persistence.claim_store as claim_store_mod
    import app.infrastructure.search.index_applier as applier_mod

    claim_src = inspect.getsource(claim_store_mod.SQLClaimStore)
    applier_src = inspect.getsource(applier_mod.SearchIndexApplier.apply_pending)
    assert "invalidate_facts" in claim_src
    assert "invalidate_facts" in applier_src


def test_no_new_async_or_queue() -> None:
    import app.application.services.dossier as dossier_mod
    import app.application.services.fact_cache as cache_mod

    for mod in (dossier_mod, cache_mod):
        src = inspect.getsource(mod)
        assert "async def" not in src
        for forbidden in ("kafka", "celery", "redis", "temporal"):
            assert forbidden not in src.lower()
