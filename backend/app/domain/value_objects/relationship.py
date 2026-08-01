"""Relationship value object — a typed, directed, attributed edge.

Frozen reference: Object-Centric Knowledge Graph Blueprint §3.1 / §4.

A Relationship is owned by the source Object (it lives in the source
Object's ``relationships`` collection) and points at a ``target`` ObjectId.
It carries the verb (``kind``), the provenance (asserted vs inferred/smart-
link), a confidence, supporting ``evidence`` quotes, and an ``acl_scope`` that
records the stricter permission of its endpoints (R1, no leakage).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.domain.value_objects.enums import Provenance, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass(frozen=True)
class Relationship:
    target: ObjectId
    kind: RelationshipKind
    provenance: Provenance = Provenance.ASSERTED
    confidence: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    acl_scope: str | None = None
    created_at: dt.datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

    @property
    def identity(self) -> tuple[str, str, str]:
        """Stable key for de-duplication within one Object."""
        return (self.target.value, self.kind.value, self.provenance.value)
