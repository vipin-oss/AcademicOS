"""The Universal Object — the single atomic unit of the system.

Frozen reference: Object-Centric Knowledge Graph Blueprint §1 (the 14
universal capabilities) and §1.4 (lifecycle). Every Faculty member, Student,
Course, Grant, Document, etc. is an Object; they differ only by ``object_type``
and by which capabilities are exercised.

This class is the **Aggregate Root** of the object graph: it owns its metadata
and its outgoing relationships, enforces lifecycle/invariant rules, and emits
domain events. It contains *no* persistence, no ORM, no HTTP — it is pure
domain logic and must remain that way for the next 15 years.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.domain.entities.base import AggregateRoot
from app.domain.events import (
    DomainEvent,
    MetadataChanged,
    ObjectArchived,
    ObjectCreated,
    ObjectRenamed,
    ObjectStatusChanged,
    ObjectSuperseded,
    RelationshipAdded,
    RelationshipRemoved,
)
from app.domain.exceptions import InvalidStateTransitionError, RelationshipConflictError
from app.domain.value_objects.audit import AuditFields
from app.domain.value_objects.enums import ObjectStatus, ObjectType, Provenance, RelationshipKind
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.relationship import Relationship

# Base lifecycle transitions (Blueprint §1.4). Type-specific states are
# expressed as metadata, never as transitions here.
_STATUS_TRANSITIONS: dict[ObjectStatus, set[ObjectStatus]] = {
    ObjectStatus.DRAFT: {ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED},
    ObjectStatus.ACTIVE: {ObjectStatus.ARCHIVED, ObjectStatus.SUPERSEDED},
    ObjectStatus.ARCHIVED: {ObjectStatus.ACTIVE},
    ObjectStatus.SUPERSEDED: set(),  # terminal
}


@dataclass(eq=False)
class UniversalObject(AggregateRoot):
    id: ObjectId
    object_type: ObjectType
    title: str
    status: ObjectStatus = ObjectStatus.DRAFT
    metadata: Metadata = field(default_factory=Metadata)
    relationships: list[Relationship] = field(default_factory=list)
    audit: AuditFields | None = None
    version: int = 1

    def __post_init__(self) -> None:
        # AggregateRoot.__init__ is not invoked by the dataclass generator,
        # so ensure the event outbox exists.
        if not hasattr(self, "_domain_events"):
            self._domain_events: list[DomainEvent] = []
        if self.audit is None:
            self.audit = AuditFields(created_by="system")

    # ------------------------------------------------------------------ factory
    @classmethod
    def create(
        cls,
        object_type: ObjectType,
        title: str,
        *,
        created_by: str,
        object_id: ObjectId | None = None,
        status: ObjectStatus = ObjectStatus.DRAFT,
        metadata: Metadata | None = None,
    ) -> "UniversalObject":
        obj_id = object_id or ObjectId.generate(object_type)
        obj = cls(
            id=obj_id,
            object_type=object_type,
            title=title,
            status=status,
            metadata=metadata or Metadata(),
            audit=AuditFields(created_by=created_by),
        )
        obj.add_domain_event(
            ObjectCreated(aggregate_id=obj.id, object_type=object_type.value, title=title)
        )
        return obj

    # ------------------------------------------------------------------- title
    def rename(
        self, new_title: str, actor: str, *, at: dt.datetime | None = None
    ) -> None:
        """Rename the Object (human-asserted display title).

        Follows the same rules as every aggregate mutator: validate, bump the
        version, touch the audit trail, emit a domain event. A no-op rename
        (same title) changes nothing and emits no event.
        """
        if not new_title or not new_title.strip():
            raise ValueError("Title must not be empty.")
        new_title = new_title.strip()
        if new_title == self.title:
            return
        old = self.title
        self.title = new_title
        self.version += 1
        if self.audit is not None:
            self.audit = self.audit.touch(actor, at=at)
        self.add_domain_event(
            ObjectRenamed(aggregate_id=self.id, old_title=old, new_title=new_title, actor=actor)
        )

    # ------------------------------------------------------------------- status
    def change_status(
        self, new_status: ObjectStatus, actor: str, *, at: dt.datetime | None = None
    ) -> None:
        if new_status == self.status:
            return
        if new_status not in _STATUS_TRANSITIONS.get(self.status, set()):
            raise InvalidStateTransitionError(self.status, new_status)
        old = self.status
        self.status = new_status
        self.version += 1
        if self.audit is not None:
            self.audit = self.audit.touch(actor, at=at)
        self.add_domain_event(
            ObjectStatusChanged(
                aggregate_id=self.id, old_status=old, new_status=new_status, actor=actor
            )
        )

    def archive(self, actor: str, *, at: dt.datetime | None = None) -> None:
        self.change_status(ObjectStatus.ARCHIVED, actor, at=at)

    def supersede(
        self, by_object_id: ObjectId, actor: str, *, at: dt.datetime | None = None
    ) -> None:
        self.change_status(ObjectStatus.SUPERSEDED, actor, at=at)
        self.add_relationship(
            by_object_id, RelationshipKind.VERSION_OF, Provenance.ASSERTED, actor=actor, at=at
        )
        self.add_domain_event(
            ObjectSuperseded(aggregate_id=self.id, by_object_id=by_object_id, actor=actor)
        )

    # ------------------------------------------------------------- relationships
    def add_relationship(
        self,
        target: ObjectId,
        kind: RelationshipKind,
        provenance: Provenance = Provenance.ASSERTED,
        *,
        actor: str | None = None,
        confidence: float | None = None,
        evidence: tuple[str, ...] | None = None,
        acl_scope: str | None = None,
        at: dt.datetime | None = None,
    ) -> None:
        rel = Relationship(
            target=target,
            kind=kind,
            provenance=provenance,
            confidence=confidence,
            evidence=evidence or (),
            acl_scope=acl_scope,
        )
        if any(r.identity == rel.identity for r in self.relationships):
            raise RelationshipConflictError(f"Relationship {rel.identity} already exists")
        self.relationships.append(rel)
        self.version += 1
        if actor is not None and self.audit is not None:
            self.audit = self.audit.touch(actor, at=at)
        self.add_domain_event(
            RelationshipAdded(
                aggregate_id=self.id, target=target, kind=kind, provenance=provenance, actor=actor
            )
        )

    def remove_relationship(
        self,
        target: ObjectId,
        kind: RelationshipKind,
        provenance: Provenance = Provenance.ASSERTED,
        *,
        actor: str | None = None,
        at: dt.datetime | None = None,
    ) -> None:
        identity = (target.value, kind.value, provenance.value)
        before = len(self.relationships)
        self.relationships = [r for r in self.relationships if r.identity != identity]
        if len(self.relationships) != before:
            self.version += 1
            if actor is not None and self.audit is not None:
                self.audit = self.audit.touch(actor, at=at)
            self.add_domain_event(
                RelationshipRemoved(
                    aggregate_id=self.id, target=target, kind=kind, provenance=provenance, actor=actor
                )
            )

    # ------------------------------------------------------------------ metadata
    def set_metadata(
        self, entry: MetadataEntry, *, actor: str | None = None, at: dt.datetime | None = None
    ) -> bool:
        """Apply a metadata entry. Returns True if a real change occurred.

        Enforces FR-MET-009: when a human-asserted value exists, a non-human
        write is ignored (``Metadata.with_entry`` keeps the human value), so
        this returns False and emits no event.
        """
        existing = self.metadata.get(entry.key)
        new_metadata = self.metadata.with_entry(entry)
        if new_metadata is self.metadata and existing is not None:
            return False
        changed = existing != new_metadata.get(entry.key)
        self.metadata = new_metadata
        if changed:
            self.version += 1
            if actor is not None and self.audit is not None:
                self.audit = self.audit.touch(actor, at=at)
            self.add_domain_event(
                MetadataChanged(
                    aggregate_id=self.id, key=entry.key, layer=int(entry.layer), actor=actor
                )
            )
        return changed

    # -------------------------------------------------------------- pure queries
    def related_ids(self, kind: RelationshipKind | None = None) -> list[ObjectId]:
        return [r.target for r in self.relationships if kind is None or r.kind == kind]
