"""Outbox-fed search index consumer (Sprint-5 M1 — Global Search Foundation).

The single writer of the persistent search projection, driven entirely by
the durable outbox relay (Sprint-4 M1) — index consumers ride the relay,
never backfill (roadmap invariant 6):

- ``apply_pending`` drains undelivered events oldest-first. Every event for
  an aggregate re-derives that aggregate's CURRENT search document from
  durable state — the latest version snapshot (Sprint-4 M2), falling back
  to the authoritative object only for objects that predate version
  snapshots. Events for aggregates that no longer exist remove the
  projection (deletion is a durable ``ObjectDeleted`` event, emitted by
  the repository in the same transaction as the delete).
- ``rebuild`` reconstructs the whole index from version snapshots in one
  atomic transaction — the acceptance guarantee that rebuilding from
  version history reproduces the same search documents as replaying the
  outbox (both paths share the same per-object resolution below).

Consistency contract: at-least-once with idempotent writes. A batch's
document writes and its ``mark_delivered`` commit atomically; a crash
before the commit simply re-applies the batch next time (upserts are
version-aware, marks are WHERE-guarded), so duplicates are impossible.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.search import SearchDocument
from app.infrastructure.db.models.object_version_model import ObjectVersionModel
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.outbox.relay import OutboxRelay
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import to_search_document
from app.infrastructure.persistence.snapshots import object_snapshot_from_dict
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
    commit_with_retry,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)

_BATCH_SIZE = 200


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class SearchIndexApplier:
    """Applies durable events to the search projection (eventual consistency).

    One consumer per session; never runs in the object write path.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._relay = OutboxRelay(session)
        self._index = SQLAlchemySearchRepository(session)
        self._objects = SQLAlchemyObjectRepository(session)

    # ------------------------------------------------------------------ drain
    def apply_pending(self) -> dict:
        """Apply all undelivered events to the index (idempotent).

        Returns ``{"applied": n}`` — the number of events drained. A
        poisoned event aborts the drain (transaction rolled back, nothing
        marked) so the failure is visible and replayable.
        """
        applied = 0
        while True:
            batch = self._relay.pending(limit=_BATCH_SIZE)
            if not batch:
                break

            def apply_batch(batch=batch) -> None:  # bound default: stable per-iteration batch
                for event in batch:
                    self._apply_event(event)
                self._relay.mark_delivered(
                    [event["event_id"] for event in batch], at=_utcnow_iso()
                )

            commit_with_retry(self._session, apply_batch)
            applied += len(batch)
        return {"applied": applied}

    def _apply_event(self, event: dict) -> None:
        aggregate_id = str(event["aggregate_id"])
        document = self._document_for(aggregate_id)
        if document is None:
            # The aggregate no longer exists in durable state (its
            # ObjectDeleted event, or a deletion whose event is drained
            # after the rows vanished): remove the projection.
            self._index.delete(aggregate_id)
        else:
            self._index.upsert(document)

    # --------------------------------------------------------------- rebuild
    def rebuild(self) -> dict:
        """Reconstruct the index from durable state, atomically.

        Source of truth for the rebuild: every object's LATEST version
        snapshot (identical to what the drain would derive); objects that
        predate version snapshots fall back to their authoritative state.
        Returns ``{"indexed": n}``.
        """
        documents = self._documents_from_version_history()
        documents.extend(self._documents_without_version_history())
        seen: set[str] = set()
        documents = [d for d in documents if not (d.object_id in seen or seen.add(d.object_id))]

        def write() -> None:
            self._session.execute(delete(SearchDocumentModel))
            for document in documents:
                self._index.upsert(document)

        commit_with_retry(self._session, write)
        return {"indexed": len(documents)}

    def _documents_from_version_history(self) -> list[SearchDocument]:
        """Latest version snapshot per object -> search document."""
        latest = select(
            ObjectVersionModel.object_id,
            func.max(ObjectVersionModel.version).label("max_version"),
        ).group_by(ObjectVersionModel.object_id)
        rows = self._session.execute(
            select(ObjectVersionModel)
            .join(
                latest,
                (ObjectVersionModel.object_id == latest.c.object_id)
                & (ObjectVersionModel.version == latest.c.max_version),
            )
            .order_by(ObjectVersionModel.object_id)
        ).scalars().all()
        return [
            to_search_document(object_snapshot_from_dict(row.snapshot))
            for row in rows
        ]

    def _documents_without_version_history(self) -> list[SearchDocument]:
        """Pre-0004 objects (no version rows) -> search document from the
        authoritative object. Empty on fresh installs."""
        with_history = set(
            self._session.execute(
                select(ObjectVersionModel.object_id).distinct()
            ).scalars().all()
        )
        return [
            to_search_document(SnapshotMapper.to_snapshot(obj))
            for obj in self._objects.list()
            if str(obj.id) not in with_history
        ]

    # ---------------------------------------------------------- resolution
    def _document_for(self, aggregate_id: str) -> SearchDocument | None:
        """The CURRENT search document for one aggregate, from durable state.

        Prefers the latest version snapshot (identical to what a rebuild
        produces); falls back to the authoritative object for aggregates
        that predate version snapshots. ``None`` when the aggregate no
        longer exists.
        """
        row = self._session.execute(
            select(ObjectVersionModel)
            .where(ObjectVersionModel.object_id == aggregate_id)
            .order_by(ObjectVersionModel.version.desc())
            .limit(1)
        ).scalars().first()
        if row is not None:
            return to_search_document(object_snapshot_from_dict(row.snapshot))
        obj = self._objects.get_by_id(ObjectId.parse(aggregate_id))
        if obj is None:
            return None
        return to_search_document(SnapshotMapper.to_snapshot(obj))
