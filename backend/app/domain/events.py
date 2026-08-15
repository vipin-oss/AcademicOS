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
class ObjectRenamed(DomainEvent):
    old_title: str | None = None
    new_title: str | None = None
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
class ObjectDeleted(DomainEvent):
    """An Object was removed from storage (Sprint-5 M1).

    Emitted by the persistence adapter inside the delete transaction — the
    repository is the single delete path, so every deletion becomes a
    durable, replayable outbox event. Index consumers (search) remove the
    projection when this event is drained; the authoritative row is already
    gone, so nothing else needs the payload beyond identity.
    """

    object_type: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class ObjectSuperseded(DomainEvent):
    by_object_id: ObjectId | None = None
    actor: str | None = None


# ---------------------------------------------------------------------------
# L1 knowledge-plane events (ADR-002 / ADR-021 / ADR-009).
# These ride the same durable outbox relay as the object events and are
# projected by the single index consumer. They are additive; the object
# events above are unchanged.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimProposed(DomainEvent):
    claim_id: str | None = None
    predicate_id: str | None = None
    source_document_id: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class ClaimStatusChanged(DomainEvent):
    claim_id: str | None = None
    old_status: str | None = None
    new_status: str | None = None
    reviewer: str | None = None


@dataclass(frozen=True)
class CdmBlockWritten(DomainEvent):
    document_id: str | None = None
    version: int | None = None
    block_type: str | None = None
    block_count: int | None = None


@dataclass(frozen=True)
class AclScopeChanged(DomainEvent):
    scope: str | None = None


@dataclass(frozen=True)
class SourceRegistered(DomainEvent):
    source_id: str | None = None
    media_kind: str | None = None
    container_source_id: str | None = None
