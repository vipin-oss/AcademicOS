"""Domain events raised by the UniversalObject aggregate.

Frozen reference: Clean Architecture — aggregates emit domain events that the
application/infrastructure layers later project (to the graph, the timeline,
the activity log, the proactive monitors). The domain owns the *what happened*;
it never owns the *how it is stored or notified*.

All events are immutable value objects. ``aggregate_id`` binds an event to the
Object that produced it.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from app.domain.value_objects.enums import ObjectStatus, Provenance, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass(frozen=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: dt.datetime = field(default_factory=_utcnow)
    aggregate_id: ObjectId | None = None


@dataclass(frozen=True)
class ObjectCreated(DomainEvent):
    object_type: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class ObjectStatusChanged(DomainEvent):
    old_status: ObjectStatus | None = None
    new_status: ObjectStatus | None = None
    actor: str | None = None


@dataclass(frozen=True)
class MetadataChanged(DomainEvent):
    key: str | None = None
    layer: int | None = None
    actor: str | None = None


@dataclass(frozen=True)
class RelationshipAdded(DomainEvent):
    target: ObjectId | None = None
    kind: RelationshipKind | None = None
    provenance: Provenance | None = None
    actor: str | None = None


@dataclass(frozen=True)
class RelationshipRemoved(DomainEvent):
    target: ObjectId | None = None
    kind: RelationshipKind | None = None
    provenance: Provenance | None = None
    actor: str | None = None


@dataclass(frozen=True)
class ObjectArchived(DomainEvent):
    actor: str | None = None


@dataclass(frozen=True)
class ObjectSuperseded(DomainEvent):
    by_object_id: ObjectId | None = None
    actor: str | None = None
