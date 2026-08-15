"""In-process bounded cache for rung-0 facts and dossier aggregates (V3 M8).

Blueprint law 22: caching rides ONE invalidation mechanism. The authoritative
write paths — the claim store (facts change when a human confirms/rejects/
corrects/supersedes) and the outbox applier (projections change when objects
change) — invalidate this cache directly. It is best-effort: a stale-free
read is guaranteed only after the corresponding invalidation, which every
writer performs.

Thread-safe (a simple lock-guarded dict with LRU eviction). Bounded, so it can
never grow unbounded memory (SCALE_LAW: memory budgets, never unbounded).
"""

from __future__ import annotations

import threading
from collections import OrderedDict

#: Default cache capacity (bounded — never unbounded memory).
DEFAULT_CAPACITY = 512


class FactCache:
    """A bounded, thread-safe LRU cache keyed by an arbitrary hashable key."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._capacity = max(1, int(capacity))
        self._lock = threading.Lock()
        self._store: OrderedDict[object, object] = OrderedDict()

    def get(self, key: object) -> object | None:
        with self._lock:
            value = self._store.get(key)
            if value is not None:
                self._store.move_to_end(key)
            return value

    def put(self, key: object, value: object) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._capacity:
                self._store.popitem(last=False)

    def invalidate(self, key: object) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


#: Process-lifetime singleton shared by rung-0 and the dossier service, and
#: invalidated by the claim store + outbox applier.
FACT_CACHE = FactCache()


def invalidate_facts() -> None:
    """Drop every cached fact/dossier aggregate (called on any authoritative
    write to the claim plane or the object/projection plane)."""
    FACT_CACHE.invalidate_all()


__all__ = ["FACT_CACHE", "FactCache", "invalidate_facts"]
