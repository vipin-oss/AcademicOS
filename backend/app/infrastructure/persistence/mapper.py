"""SnapshotMapper — lossless Domain <-> Snapshot conversion.

This is the single seam between the Domain and any future persistence
technology. The Domain never knows about snapshots; the mapper translates both
ways and preserves every value (enums by value, datetimes by ISO-8601, ids by
string). No SQLAlchemy, no DB, no framework — only ``app.domain`` and stdlib.
"""
from __future__ import annotations

import datetime as _dt

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.audit import AuditFields
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.relationship import Relationship

from app.infrastructure.persistence.snapshots import (
    AuditSnapshot,
    MetadataSnapshot,
    ObjectSnapshot,
    RelationshipSnapshot,
)


def _parse_dt(value: str) -> _dt.datetime:
    """Parse an ISO-8601 snapshot timestamp back into a datetime.

    An empty string (should not occur for live Domain objects) falls back to UTC
    now so reconstruction never fails; round-trips of real objects are exact.
    """
    return _dt.datetime.fromisoformat(value) if value else _dt.datetime.now(_dt.timezone.utc)


class SnapshotMapper:
    """Converts between ``UniversalObject`` and ``ObjectSnapshot`` losslessly."""

    @staticmethod
    def to_snapshot(obj: UniversalObject) -> ObjectSnapshot:
        return ObjectSnapshot(
            id=str(obj.id),
            object_type=obj.object_type.value,
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            metadata=tuple(
                MetadataSnapshot(
                    key=e.key,
                    value=e.value,
                    layer=int(e.layer),
                    source=e.source.value,
                    confidence=e.confidence,
                    recorded_at=e.recorded_at.isoformat(),
                )
                for e in obj.metadata.entries
            ),
            relationships=tuple(
                RelationshipSnapshot(
                    target=str(r.target),
                    kind=r.kind.value,
                    provenance=r.provenance.value,
                    confidence=r.confidence,
                    evidence=tuple(r.evidence),
                    acl_scope=r.acl_scope,
                    created_at=r.created_at.isoformat(),
                )
                for r in obj.relationships
            ),
            audit=(
                AuditSnapshot(
                    created_by=obj.audit.created_by,
                    created_at=obj.audit.created_at.isoformat(),
                    updated_by=obj.audit.updated_by,
                    updated_at=obj.audit.updated_at.isoformat()
                    if obj.audit.updated_at is not None
                    else None,
                )
                if obj.audit is not None
                else None
            ),
        )

    @staticmethod
    def from_snapshot(snap: ObjectSnapshot) -> UniversalObject:
        return UniversalObject(
            id=ObjectId.parse(snap.id),
            object_type=ObjectType(snap.object_type),
            title=snap.title,
            status=ObjectStatus(snap.status),
            version=snap.version,
            metadata=Metadata(
                entries=tuple(
                    MetadataEntry(
                        key=m.key,
                        value=m.value,
                        layer=MetadataLayer(m.layer),
                        source=Provenance(m.source),
                        confidence=m.confidence,
                        recorded_at=_parse_dt(m.recorded_at),
                    )
                    for m in snap.metadata
                )
            ),
            relationships=[
                Relationship(
                    target=ObjectId.parse(r.target),
                    kind=RelationshipKind(r.kind),
                    provenance=Provenance(r.provenance),
                    confidence=r.confidence,
                    evidence=tuple(r.evidence),
                    acl_scope=r.acl_scope,
                    created_at=_parse_dt(r.created_at),
                )
                for r in snap.relationships
            ],
            audit=(
                AuditFields(
                    created_by=snap.audit.created_by,
                    created_at=_parse_dt(snap.audit.created_at),
                    updated_by=snap.audit.updated_by,
                    updated_at=_parse_dt(snap.audit.updated_at)
                    if snap.audit.updated_at is not None
                    else None,
                )
                if snap.audit is not None
                else None
            ),
        )
