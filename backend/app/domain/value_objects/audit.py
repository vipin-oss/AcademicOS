"""Audit fields — who created/changed an Object and when.

Frozen reference: Object-Centric Knowledge Graph Blueprint §1.2
(capability #12 Activity Log) and the 14-capability model.

A value object: immutable, comparable by value. ``created_by`` / ``updated_by``
are actor identifiers (a person ObjectId, a system token, or an AI agent id) —
the domain does not care which; that interpretation lives upstream.
"""
from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass, field

# Strictly-monotonic audit clock state. Both symbols are module-private and
# guarded by ``_MONOTONIC_LOCK``; no public API depends on them, so swapping
# the strategy later (e.g. for a cluster-wide sequence) is a local change.
_MONOTONIC_LOCK = threading.Lock()
_MONOTONIC_LAST: dt.datetime | None = None


def _utcnow() -> dt.datetime:
    """Strictly-monotonic UTC clock for audit fields.

    Wall-clock time, but guarantees that consecutive calls within this
    process never return an identical instant. Back-to-back object creations
    therefore receive strictly increasing ``created_at`` values even when the
    OS clock has coarse resolution. This makes "newest created_at wins"
    ordering (memory consolidation and any created_at ordering) deterministic.

    Thread-safe: the monotonic ``_MONOTONIC_LAST`` state is only ever read or
    written under ``_MONOTONIC_LOCK``. The value returned is a normal
    timezone-aware UTC ``datetime``, so serialization and every existing
    consumer are unchanged.
    """
    global _MONOTONIC_LAST
    now = dt.datetime.now(dt.UTC)
    with _MONOTONIC_LOCK:
        if _MONOTONIC_LAST is not None and now <= _MONOTONIC_LAST:
            now = _MONOTONIC_LAST + dt.timedelta(microseconds=1)
        _MONOTONIC_LAST = now
    return now


@dataclass(frozen=True)
class AuditFields:
    created_by: str
    created_at: dt.datetime = field(default_factory=_utcnow)
    updated_by: str | None = None
    updated_at: dt.datetime | None = None

    def touch(self, by: str, *, at: dt.datetime | None = None) -> "AuditFields":
        return AuditFields(
            created_by=self.created_by,
            created_at=self.created_at,
            updated_by=by,
            updated_at=at or _utcnow(),
        )
