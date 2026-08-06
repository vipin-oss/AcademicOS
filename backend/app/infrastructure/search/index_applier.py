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
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.ports.embedder import Embedder
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.search import SearchDocument
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.db.models.object_version_model import ObjectVersionModel
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.outbox.relay import OutboxRelay
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import (
    to_search_document,
    to_search_text,
)
from app.infrastructure.persistence.snapshots import object_snapshot_from_dict
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
    commit_with_retry,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)

_log = logging.getLogger(__name__)

_BATCH_SIZE = 200


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class SearchIndexApplier:
    """Applies durable events to the search projection (eventual consistency).

    One consumer per session; never runs in the object write path.
    """

    def __init__(
        self,
        session: Session,
        *,
        vector_repository: VectorRepository | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._session = session
        self._relay = OutboxRelay(session)
        self._index = SQLAlchemySearchRepository(session)
        self._objects = SQLAlchemyObjectRepository(session)
        # Sprint-5 M2 — the semantic projection rides the same drain when a
        # vector store and embedder are wired; without them the applier is
        # exactly the M1 lexical consumer.
        self._vector_repository = vector_repository
        self._embedder = embedder

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
            if self._vector_repository is not None:
                self._safe_vector(lambda: self._vector_repository.delete(aggregate_id))
        else:
            self._index.upsert(document)
            if self._vector_repository is not None and self._embedder is not None:
                vector = self._embedder.embed(to_search_text(document))
                self._safe_vector(
                    lambda: self._vector_repository.upsert(
                        _to_vector_document(document, vector)
                    )
                )

    def _safe_vector(self, operation) -> None:
        """Run a semantic-store operation without breaking the drain.

        The lexical index is authoritative; a vector failure is logged and
        the event still completes — the semantic projection lags and the
        rebuild path repairs it. Never a 500 for the lexical consumer.
        """
        try:
            operation()
        except Exception:  # noqa: BLE001 — semantic must never break indexing
            _log.warning("Semantic index update failed; lexical unaffected.", exc_info=True)

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
        # Semantic rebuild from the SAME document set: identical derivation,
        # so rebuild == replay holds for both projections. Best-effort — the
        # lexical index is authoritative and remains untouched by a failure.
        if self._vector_repository is not None and self._embedder is not None:
            self._rebuild_vectors(documents)
        return {"indexed": len(documents)}

    def _rebuild_vectors(self, documents: list[SearchDocument]) -> None:
        """Reconstruct the semantic projection from the document set."""
        try:
            self._vector_repository.clear()
            for document in documents:
                vector = self._embedder.embed(to_search_text(document))
                self._vector_repository.upsert(_to_vector_document(document, vector))
        except Exception:  # noqa: BLE001 — lexical authoritative; retry via rebuild
            _log.warning("Semantic rebuild failed; lexical index untouched.", exc_info=True)

    def _documents_from_version_history(self) -> list[SearchDocument]:
        """Latest version snapshot per object -> search document."""
        latest = (
            select(
                ObjectVersionModel.object_id,
                func.max(ObjectVersionModel.version).label("max_version"),
            )
            .group_by(ObjectVersionModel.object_id)
            .subquery()
        )
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


def _to_vector_document(document: SearchDocument, vector: list[float]) -> VectorDocument:
    """The semantic projection of a search document with its embedding."""
    return VectorDocument(
        object_id=document.object_id,
        object_type=document.object_type,
        title=document.title,
        metadata_text=document.metadata_text,
        version=document.version,
        vector=tuple(vector),
    )
