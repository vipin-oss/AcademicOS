"""SQLAlchemy adapter for the ObjectRepository port.

The single concrete infrastructure adapter so far. It implements every method of
the frozen ``ObjectRepository`` abstract interface AND the requested public
surface (save / get / exists / delete / list / find). All mapping goes through
the frozen ``SnapshotMapper`` plus the ``ObjectModel``; there is no domain logic
here — only persistence plumbing.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.relationship import RelationshipKind
from app.infrastructure.db.models.object_model import ObjectModel
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.snapshots import (
    AuditSnapshot,
    MetadataSnapshot,
    ObjectSnapshot,
    RelationshipSnapshot,
)


class SQLAlchemyObjectRepository(ObjectRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- internal mapping (Snapshot <-> Model, via SnapshotMapper) ---
    @staticmethod
    def _to_model(obj: UniversalObject) -> ObjectModel:
        snap = SnapshotMapper.to_snapshot(obj)
        return ObjectModel(
            id=snap.id,
            object_type=snap.object_type,
            title=snap.title,
            status=snap.status,
            version=snap.version,
            metadata_json=[m.to_dict() for m in snap.metadata],
            relationships_json=[r.to_dict() for r in snap.relationships],
            audit_json=snap.audit.to_dict() if snap.audit else None,
        )

    @staticmethod
    def _to_snapshot(model: ObjectModel) -> ObjectSnapshot:
        return ObjectSnapshot(
            id=model.id,
            object_type=model.object_type,
            title=model.title,
            status=model.status,
            version=model.version,
            metadata=tuple(MetadataSnapshot(**d) for d in (model.metadata_json or [])),
            relationships=tuple(
                RelationshipSnapshot(**d) for d in (model.relationships_json or [])
            ),
            audit=AuditSnapshot(**model.audit_json) if model.audit_json else None,
        )

    def _to_domain(self, model: ObjectModel) -> UniversalObject:
        return SnapshotMapper.from_snapshot(self._to_snapshot(model))

    # --- requested public surface ---
    def save(self, entity: UniversalObject) -> None:
        self._session.merge(self._to_model(entity))
        self._session.commit()

    def get(self, id: ObjectId) -> UniversalObject | None:
        model = self._session.get(ObjectModel, str(id))
        return self._to_domain(model) if model is not None else None

    def exists(self, id: ObjectId) -> bool:
        return self._session.get(ObjectModel, str(id)) is not None

    def delete(self, id: ObjectId) -> None:
        model = self._session.get(ObjectModel, str(id))
        if model is not None:
            self._session.delete(model)
            self._session.commit()

    def list(self) -> list[UniversalObject]:
        models = self._session.execute(select(ObjectModel)).scalars().all()
        return [self._to_domain(m) for m in models]

    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> list[UniversalObject]:
        stmt = select(ObjectModel)
        if object_type is not None:
            value = object_type.value if isinstance(object_type, ObjectType) else object_type
            stmt = stmt.where(ObjectModel.object_type == value)
        if status is not None:
            value = status.value if isinstance(status, ObjectStatus) else status
            stmt = stmt.where(ObjectModel.status == value)
        if metadata_key is not None:
            clause: dict = {"key": metadata_key}
            if metadata_value is not None:
                clause["value"] = metadata_value
            stmt = stmt.where(ObjectModel.metadata_json.contains([clause]))
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]

    # --- abstract interface satisfaction (delegate to the surface above) ---
    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        if not ids:
            return []
        stmt = select(ObjectModel).where(ObjectModel.id.in_([str(i) for i in ids]))
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in models]

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return self.find(object_type=object_type)

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return self.find(status=status)

    def find_by_metadata(
        self, key: str, value: str | None = None
    ) -> list[UniversalObject]:
        return self.find(metadata_key=key, metadata_value=value)

    def find_related(
        self, object_id: ObjectId, kind: RelationshipKind | None = None
    ) -> list[ObjectId]:
        obj = self.get(object_id)
        if obj is None:
            return []
        return obj.related_ids(kind)
