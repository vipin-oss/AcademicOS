"""Audit fields — who created/changed an Object and when.

Frozen reference: Object-Centric Knowledge Graph Blueprint §1.2
(capability #12 Activity Log) and the 14-capability model.

A value object: immutable, comparable by value. ``created_by`` / ``updated_by``
are actor identifiers (a person ObjectId, a system token, or an AI agent id) —
the domain does not care which; that interpretation lives upstream.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
