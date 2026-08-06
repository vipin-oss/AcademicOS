"""SQLAlchemy adapter for the ObjectRepository port.

The single concrete infrastructure adapter so far. It implements every method of
the frozen ``ObjectRepository`` abstract interface AND the requested public
surface (save / get / exists / delete / list / find). All mapping goes through
the frozen ``SnapshotMapper`` plus the ``ObjectModel`` and the
``ObjectRelationshipModel`` edge table (R1 — Object Graph physical model);
there is no domain logic here — only persistence plumbing.

Relationship persistence: ``save`` replaces the whole edge set of an object in
the same transaction as the object row (delete + insert), preserving the
aggregate's list order via row order. Reads load edges in bulk, grouped by
source, with one query.

Optimistic concurrency (R3): ``save`` compares the stored row's ``version``
against the version the aggregate was loaded at (``_expected_version``) and
raises ``OptimisticConcurrencyError`` on mismatch — stale snapshots are never
merged over newer rows. New aggregates are inserted; a duplicate id surfaces
as the same conflict.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.application.services.outbox import to_outbox_row
from app.domain.entities.object import UniversalObject
from app.domain.events import ObjectDeleted
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.relationship import RelationshipKind
from app.infrastructure.db.models.object_model import ObjectModel
from app.infrastructure.db.models.object_relationship_model import (
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import ObjectVersionModel
from app.infrastructure.db.models.outbox_model import OutboxEventModel
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.snapshots import (
    AuditSnapshot,
    MetadataSnapshot,
    ObjectSnapshot,
    RelationshipSnapshot,
)

# Transient lock contention (SQLite single-writer reality): bounded, fixed
# backoff — deterministic by contract, no jitter, no unbounded stalls. The
# driver's own busy timeout waits inside each attempt, so five attempts
# tolerate seconds-scale contention bursts on loaded machines.
_LOCK_RETRY_ATTEMPTS = 5
_LOCK_RETRY_BACKOFF_SECONDS = (0.05, 0.1, 0.2, 0.4)  # slept before retries 2..5
_SQLITE_BUSY = 5  # primary sqlite error code for lock contention
_LOCK_MESSAGE_TOKENS = ("database is locked", "database table is locked", "database is busy")

# R2 — repository projections: the only sortable columns (scalar object
# columns; metadata/audit live in JSON and are not orderable in SQL).
_FIND_SORT_COLUMNS = {
    "id": ObjectModel.id,
    "object_type": ObjectModel.object_type,
    "title": ObjectModel.title,
    "status": ObjectModel.status,
    "version": ObjectModel.version,
}
_FIND_ORDERS = ("asc", "desc")


def _is_lock_contention(exc: OperationalError) -> bool:
    """True ONLY for transient lock contention — never for real errors (I/O,
    constraint, syntax), which must fail fast and surface immediately."""

    orig = getattr(exc, "orig", None)
    if getattr(orig, "sqlite_errorcode", None) == _SQLITE_BUSY:
        return True
    message = str(exc).lower()
    return any(token in message for token in _LOCK_MESSAGE_TOKENS)


def commit_with_retry(session: Session, write: Callable[[], None]) -> None:
    """Write + commit with bounded protection against lock contention.

    The single shared retry boundary for every persistence writer (the
    object repository's save/delete and the search index applier). A
    transient "database is locked" is inherent to a single-writer DB whose
    readers (live progress polls) overlap the writers' commits; without a
    retry it escapes and can wedge a flow in a non-terminal state. The
    write must be idempotent (same snapshot merged again, same upsert,
    same WHERE-guarded mark), so a fixed backoff and re-issue is honest.
    Non-lock errors raise on first failure; lock errors raise after the
    bound is spent.
    """

    for attempt in range(_LOCK_RETRY_ATTEMPTS):
        try:
            write()
            session.commit()
            return
        except OperationalError as exc:
            session.rollback()
            if not _is_lock_contention(exc) or attempt == _LOCK_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_LOCK_RETRY_BACKOFF_SECONDS[attempt])


class SQLAlchemyObjectRepository(ObjectRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _commit_with_retry(self, write: Callable[[], None]) -> None:
        """Write + commit with bounded protection against lock contention.

        Shared with the search index applier via the module-level
        ``commit_with_retry`` — the single retry boundary for persistence
        writers.
        """

        commit_with_retry(self._session, write)

    # --- internal mapping (Snapshot <-> Model, via SnapshotMapper) ---
    @staticmethod
    def _edge_models_from_snapshot(snap: ObjectSnapshot) -> list[ObjectRelationshipModel]:
        """One edge row per RelationshipSnapshot, in aggregate list order.

        Insertion order becomes the physical row order (autoincrement ``id``),
        so reading back ``ORDER BY id`` reproduces the aggregate's
        relationship list exactly.
        """
        return [
            ObjectRelationshipModel(
                source_id=snap.id,
                target_id=r.target,
                kind=r.kind,
                provenance=r.provenance,
                confidence=r.confidence,
                evidence=list(r.evidence),
                acl_scope=r.acl_scope,
                created_at=r.created_at,
            )
            for r in snap.relationships
        ]

    @staticmethod
    def _relationship_snapshot_from_edge(
        edge: ObjectRelationshipModel,
    ) -> RelationshipSnapshot:
        return RelationshipSnapshot(
            target=edge.target_id,
            kind=edge.kind,
            provenance=edge.provenance,
            confidence=edge.confidence,
            evidence=tuple(edge.evidence or ()),
            acl_scope=edge.acl_scope,
            created_at=edge.created_at,
        )

    def _load_relationships(
        self, ids: Sequence[str]
    ) -> dict[str, list[ObjectRelationshipModel]]:
        """All edges for the given source ids, grouped by source, in row order."""
        if not ids:
            return {}
        rows = self._session.execute(
            select(ObjectRelationshipModel)
            .where(ObjectRelationshipModel.source_id.in_(ids))
            .order_by(ObjectRelationshipModel.id)
        ).scalars().all()
        grouped: dict[str, list[ObjectRelationshipModel]] = {}
        for row in rows:
            grouped.setdefault(row.source_id, []).append(row)
        return grouped

    def _to_snapshot(
        self, model: ObjectModel, relationships: Sequence[ObjectRelationshipModel]
    ) -> ObjectSnapshot:
        return ObjectSnapshot(
            id=model.id,
            object_type=model.object_type,
            title=model.title,
            status=model.status,
            version=model.version,
            metadata=tuple(MetadataSnapshot(**d) for d in (model.metadata_json or [])),
            relationships=tuple(
                self._relationship_snapshot_from_edge(e) for e in relationships
            ),
            audit=AuditSnapshot(**model.audit_json) if model.audit_json else None,
        )

    def _to_domain(
        self, model: ObjectModel, relationships: Sequence[ObjectRelationshipModel]
    ) -> UniversalObject:
        obj = SnapshotMapper.from_snapshot(self._to_snapshot(model, relationships))
        # R3: record the version the aggregate was loaded at, so a later
        # save() can refuse to overwrite a row a concurrent writer advanced.
        obj._expected_version = model.version
        return obj

    # --- requested public surface ---
    def save(self, entity: UniversalObject, *, outbox_events: Sequence[dict] = ()) -> None:
        """Persist the aggregate with optimistic concurrency (R3).

        A freshly created aggregate (never loaded from storage) is inserted;
        a duplicate id means a concurrent creator won the race and surfaces
        as ``OptimisticConcurrencyError``. A loaded aggregate is written with
        a compare-and-swap on ``version``: the row must still carry the
        version the aggregate was loaded at (``entity._expected_version``),
        otherwise a concurrent writer landed and the save is refused — never
        a silent lost update.

        The snapshot and the write lambda are built once; lock-contention
        retries re-issue the same lambda, which is idempotent (same CAS
        predicate, same edge set, same version/outbox rows).

        Sprint-4 Milestone B — when this save stores a version the object has
        never had (create, or an update whose version changed), an immutable
        ``object_versions`` row holding the frozen ``ObjectSnapshot`` is
        appended in the SAME transaction. A save that does not change the
        version writes no version row.

        Sprint-5 M1 — events still pending on the aggregate (``domain_events``)
        are additionally persisted as durable outbox rows in the same
        transaction, so every save path feeds the relay. The explicit
        ``outbox_events`` rows and the aggregate's pending events are
        disjoint by construction (callers pop before passing rows).
        """
        snap = SnapshotMapper.to_snapshot(entity)
        edge_models = self._edge_models_from_snapshot(snap)
        expected_version = entity._expected_version
        # Sprint-4 Milestone B — version snapshots: this save introduces a
        # new version only when it writes one the object has never stored (a
        # create, or an update whose version actually changed). Re-saving an
        # unchanged aggregate records nothing.
        captures_version = expected_version is None or snap.version != expected_version
        values = {
            "object_type": snap.object_type,
            "title": snap.title,
            "status": snap.status,
            "version": snap.version,
            "metadata_json": [m.to_dict() for m in snap.metadata],
            "audit_json": snap.audit.to_dict() if snap.audit else None,
        }

        def write() -> None:
            if expected_version is None:
                try:
                    self._session.execute(
                        insert(ObjectModel).values(id=snap.id, **values)
                    )
                except IntegrityError:
                    self._session.rollback()
                    raise OptimisticConcurrencyError(
                        f"Object {snap.id} was created concurrently."
                    ) from None
            else:
                result = self._session.execute(
                    update(ObjectModel)
                    .where(
                        ObjectModel.id == snap.id,
                        ObjectModel.version == expected_version,
                    )
                    .values(**values)
                )
                if result.rowcount == 0:
                    self._session.rollback()
                    raise OptimisticConcurrencyError(
                        f"Object {snap.id} changed since it was loaded "
                        f"(expected version {expected_version})."
                    )
            self._session.execute(
                delete(ObjectRelationshipModel).where(
                    ObjectRelationshipModel.source_id == snap.id
                )
            )
            self._session.add_all(edge_models)
            # Durable outbox rows ride the SAME transaction (and the same
            # lock-contention retry) as the aggregate write, so a committed
            # object never loses its events.
            for row in outbox_events:
                self._session.add(OutboxEventModel(**row))
            # Sprint-5 M1 — every write path is durable: events still
            # pending on the aggregate (use cases that do not pop them
            # before saving) ride the same transaction, so the relay can
            # index any object lifecycle, not just the document path.
            # Read-only: popped aggregates add nothing, and the in-memory
            # projection (pop_domain_events) is left untouched.
            for event in entity.domain_events:
                self._session.add(OutboxEventModel(**to_outbox_row(event)))
            # Immutable version record: the frozen snapshot rides the SAME
            # transaction (and retry) as the aggregate write, so a committed
            # save always leaves a complete version history behind it. A
            # retry re-issues this lambda and re-adds the row; the previous
            # attempt's copy was rolled back, so no duplicate can survive.
            if captures_version:
                self._session.add(
                    ObjectVersionModel(
                        object_id=snap.id,
                        version=snap.version,
                        snapshot=snap.to_dict(),
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )

        self._commit_with_retry(write)
        entity._expected_version = snap.version

    def get(self, id: ObjectId) -> UniversalObject | None:
        model = self._session.get(ObjectModel, str(id))
        if model is None:
            return None
        relationships = self._load_relationships([str(id)]).get(str(id), [])
        return self._to_domain(model, relationships)

    def exists(self, id: ObjectId) -> bool:
        return self._session.get(ObjectModel, str(id)) is not None

    def delete(self, id: ObjectId) -> None:
        model = self._session.get(ObjectModel, str(id))
        if model is not None:
            def write() -> None:
                # Explicit edge deletion keeps SQLite behaviour identical to
                # PostgreSQL's ON DELETE CASCADE.
                self._session.execute(
                    delete(ObjectRelationshipModel).where(
                        ObjectRelationshipModel.source_id == str(id)
                    )
                )
                # Same doctrine for version snapshots (Milestone B): no
                # orphaned history rows on either engine.
                self._session.execute(
                    delete(ObjectVersionModel).where(
                        ObjectVersionModel.object_id == str(id)
                    )
                )
                self._session.delete(model)
                # Sprint-5 M1: a durable, replayable deletion marker rides
                # the SAME transaction, so index consumers (search) remove
                # the projection when the event is drained. The repository
                # is the single delete path — every deletion is covered
                # here, no caller changes needed.
                event = ObjectDeleted(
                    aggregate_id=id,
                    object_type=model.object_type,
                    title=model.title,
                )
                self._session.add(OutboxEventModel(**to_outbox_row(event)))

            self._commit_with_retry(write)

    def list(self) -> list[UniversalObject]:
        models = self._session.execute(select(ObjectModel)).scalars().all()
        return self._to_domain_many(models)

    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        if page < 1:
            raise ValueError("page must be >= 1.")
        if page_size < 0:
            raise ValueError("page_size must be >= 0.")
        if sort_by is not None and sort_by not in _FIND_SORT_COLUMNS:
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
        if order not in _FIND_ORDERS:
            raise ValueError(f"Unsupported order: {order!r}")

        stmt = self._apply_object_filters(
            select(ObjectModel),
            object_type=object_type,
            status=status,
            metadata_key=metadata_key,
            metadata_value=metadata_value,
        )
        if page_size > 0 and sort_by is None:
            # Deterministic pages need a stable order; default to id.
            sort_by = "id"
        if sort_by is not None:
            sort_column = _FIND_SORT_COLUMNS[sort_by]
            if order == "asc":
                stmt = stmt.order_by(sort_column.asc(), ObjectModel.id.asc())
            else:
                stmt = stmt.order_by(sort_column.desc(), ObjectModel.id.asc())
        if page_size > 0:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(stmt).scalars().all()
        return self._to_domain_many(models)

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        stmt = self._apply_object_filters(
            select(func.count(ObjectModel.id)),
            object_type=object_type,
            status=status,
            metadata_key=metadata_key,
            metadata_value=metadata_value,
        )
        return int(self._session.execute(stmt).scalar() or 0)

    @staticmethod
    def _apply_object_filters(
        stmt,
        *,
        object_type: ObjectType | None,
        status: ObjectStatus | None,
        metadata_key: str | None,
        metadata_value: str | None,
    ):
        """Apply the shared filter predicates to a SELECT (find or count)."""
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
        return stmt

    def _to_domain_many(self, models: Sequence[ObjectModel]) -> list[UniversalObject]:
        """Bulk load: one edge query for all objects instead of N+1."""
        relationships = self._load_relationships([m.id for m in models])
        return [
            self._to_domain(m, relationships.get(m.id, [])) for m in models
        ]

    # --- abstract interface satisfaction (delegate to the surface above) ---
    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        if not ids:
            return []
        stmt = select(ObjectModel).where(ObjectModel.id.in_([str(i) for i in ids]))
        models = self._session.execute(stmt).scalars().all()
        return self._to_domain_many(models)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return self.find(object_type=object_type)

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return self.find(status=status)

    def find_by_metadata(
        self, key: str, value: str | None = None
    ) -> list[UniversalObject]:
        return self.find(metadata_key=key, metadata_value=value)

    def find_inbound(
        self, object_id: ObjectId, kind: RelationshipKind | None = None
    ) -> list[ObjectId]:
        """Inbound traversal: every source whose edge points at ``object_id``."""
        stmt = select(ObjectRelationshipModel.source_id).where(
            ObjectRelationshipModel.target_id == str(object_id)
        )
        if kind is not None:
            stmt = stmt.where(ObjectRelationshipModel.kind == kind.value)
        stmt = stmt.order_by(ObjectRelationshipModel.id)
        return [
            ObjectId.parse(source)
            for source in self._session.execute(stmt).scalars().all()
        ]

    def find_related(
        self, object_id: ObjectId, kind: RelationshipKind | None = None
    ) -> list[ObjectId]:
        """Direct edge query — the physical table makes traversal a lookup."""
        stmt = select(ObjectRelationshipModel.target_id).where(
            ObjectRelationshipModel.source_id == str(object_id)
        )
        if kind is not None:
            stmt = stmt.where(ObjectRelationshipModel.kind == kind.value)
        stmt = stmt.order_by(ObjectRelationshipModel.id)
        return [
            ObjectId.parse(target)
            for target in self._session.execute(stmt).scalars().all()
        ]
