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
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore
from app.infrastructure.persistence.document_identity_store import SQLDocumentIdentityStore
from app.application.ports.document_identity_store import DocumentIdentityStore
from app.application.services.document_chunking import content_hash
from app.infrastructure.search.fts import SQLFTSRepository
from sqlalchemy.exc import OperationalError as _OperationalError
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore
from app.application.ports.document_chunk_store import DocumentChunkStore
from app.application.services.document_chunking import chunk_text, content_hash
from app.infrastructure.persistence.search_mapping import (
    to_search_document,
    to_search_text,
)
from app.infrastructure.persistence.snapshots import object_snapshot_from_dict
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
    commit_with_retry,
)
from app.infrastructure.persistence.acl_scope_propagator import AclScopePropagator
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
        chunk_store: DocumentChunkStore | None = None,
        identity_store: DocumentIdentityStore | None = None,
    ) -> None:
        self._session = session
        self._relay = OutboxRelay(session)
        self._index = SQLAlchemySearchRepository(session)
        self._objects = SQLAlchemyObjectRepository(session)
        # M27: the document-content projection rides the same consumer —
        # deletions remove the derived content row (idempotent).
        self._content = SQLDocumentContentStore(session)
        # P0 knowledge projection — the SINGLE chunk writer is this applier
        # (one indexing pipeline). The chunk store defaults to the SQL
        # implementation, exactly like the content store.
        self._chunks: DocumentChunkStore = chunk_store or SQLDocumentChunkStore(session)
        # P1 scale & identity: the FULL-TEXT projection and the CONTENT
        # IDENTITY registry ride the SAME consumer (one projection
        # lifecycle). Graceful: a database without the 0011 tables simply
        # skips FTS/registry writes — the drain never breaks.
        self._fts = SQLFTSRepository(session)
        self._identity: DocumentIdentityStore = (
            identity_store or SQLDocumentIdentityStore(session)
        )
        self._fts_warned: list[bool] = [False]
        # P0 observability: per-drain counters (kept OFF the return dict so
        # existing ``apply_pending() == {"applied": n}`` contracts hold).
        self.stats = {
            "chunk_created": 0, "chunk_skipped": 0, "content_backfilled": 0,
            "fts_updated": 0, "identity_synced": 0, "duplicates": 0,
        }
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
        self.stats = {
            "chunk_created": 0, "chunk_skipped": 0, "content_backfilled": 0,
            "fts_updated": 0, "identity_synced": 0, "duplicates": 0,
        }
        while True:
            batch = self._relay.pending(limit=_BATCH_SIZE)
            if not batch:
                break

            # V3 M8 (law 22): object/projection changes ride the outbox; drop
            # cached dossier/fact aggregates so a concurrent read never goes
            # stale across a projection update.
            from app.application.services.fact_cache import invalidate_facts

            invalidate_facts()

            def apply_batch(batch=batch) -> None:  # bound default: stable per-iteration batch
                for event in batch:
                    self._apply_event(event)
                self._relay.mark_delivered(
                    [event["event_id"] for event in batch], at=_utcnow_iso()
                )

            commit_with_retry(self._session, apply_batch)
            applied += len(batch)
        try:
            self.stats["duplicates"] = self._identity.duplicate_count()
        except Exception:  # noqa: BLE001 — registry missing degrades silently
            pass
        return {"applied": applied}

    def _apply_event(self, event: dict) -> None:
        aggregate_id = str(event["aggregate_id"])
        document = self._document_for(aggregate_id)
        if document is None:
            # The aggregate no longer exists in durable state (its
            # ObjectDeleted event, or a deletion whose event is drained
            # after the rows vanished): remove the projections — including
            # the M27 document-content row (idempotent).
            self._index.delete(aggregate_id)
            self._content.delete(aggregate_id)
            # P0: chunks are derived from the content projection — they are
            # removed with it (explicit delete; FK cascade is a second net
            # on PostgreSQL). Deleted objects can never be resurrected by a
            # stale event: every event re-derives the aggregate, and the
            # re-derivation is None for deleted objects.
            self._chunks.delete_by_document(aggregate_id)
            # P1: FTS row and identity entry are removed with the object
            # (idempotent). A deleted document can never reappear through
            # the FTS/content leg — every event re-derives the aggregate.
            self._safe_fts(lambda: self._fts.delete(aggregate_id))
            self._safe_identity(
                lambda: self._remove_identity(aggregate_id)
            )
            if self._vector_repository is not None:
                self._safe_vector(lambda: self._vector_repository.delete(aggregate_id))
        else:
            self._index.upsert(document)
            # P0: keep the chunk projection in sync (single chunk writer).
            # Hash-guarded: metadata-only updates re-derive search_documents
            # but do NOT re-chunk when the normalized content hash is equal.
            self._sync_chunks(aggregate_id, document.version)
            # P1: full-text + identity projections from the SAME derived
            # sources (title/metadata/content/chunks). Hash-guarded
            # upstream: unchanged content skips chunk writes; FTS rows are
            # simply re-derived (idempotent); the registry records the
            # content identity (content_hash — never filename/version).
            self._sync_fts(aggregate_id, document)
            self._sync_identity(aggregate_id)
            # L1 / ADR-009: stamp the source ACL scope onto every derived
            # row for this aggregate (search/content/chunks/FTS/claims/cdm),
            # so retrieval/evidence can pre-filter without an object lookup.
            self._propagate_acl(aggregate_id)
            if self._vector_repository is not None and self._embedder is not None:
                vector = self._embedder.embed(to_search_text(document))
                self._safe_vector(
                    lambda: self._vector_repository.upsert(
                        _to_vector_document(document, vector)
                    )
                )

    def _sync_chunks(self, object_id: str, version: int) -> None:
        """Create/replace the chunk projection for one document (idempotent).

        - content projection missing or empty (direct-upload crash window:
          the outbox event can be drained before the route's second commit)
          -> skip; NO empty/incorrect chunks are created; the rebuild
          repairs the content row and chunks.
        - content hash unchanged AND chunks already present -> skip
          (metadata-only updates never re-chunk).
        - otherwise: deterministic chunk_text over the NORMALIZED content,
          delete-then-insert for the document in the caller's transaction,
          and backfill the content row's hash when it was NULL/stale.
        """
        projection = self._content.get_content_projection(object_id)
        if not projection or not projection.get("content_text", "").strip():
            self.stats["chunk_skipped"] += 1
            return
        text = projection["content_text"]
        h = content_hash(text)
        if (
            projection.get("content_hash") == h
            and self._chunks.count(object_id) > 0
        ):
            self.stats["chunk_skipped"] += 1
            return
        chunks = chunk_text(text)
        self._chunks.replace(
            document_id=object_id,
            version=version,
            source_item_id=projection.get("source_item_id"),
            chunks=chunks,
        )
        self.stats["chunk_created"] += 1
        if projection.get("content_hash") != h:
            self._content.set_content_hash(object_id, h)
            self.stats["content_backfilled"] += 1

    def _sync_fts(self, object_id: str, document) -> None:
        """Re-derive the FTS row for one aggregate from the projections.

        ``document`` is the SearchDocument (title/metadata/version). Content
        text comes from the content projection; chunk text from the chunk
        store. Missing content/chunks degrade to empty strings (structured
        objects index title+metadata only — their searchable evidence).
        """
        projection = self._content.get_content_projection(object_id)
        content_text = (projection or {}).get("content_text", "") or ""
        chunk_rows = []
        try:
            chunk_rows = self._chunks.by_document(object_id)
        except Exception:  # noqa: BLE001 — chunk read must never break FTS
            chunk_rows = []
        chunks_text = "\n".join(row["content"] for row in chunk_rows)
        self._safe_fts(
            lambda: self._fts.upsert(
                object_id=object_id,
                object_type=document.object_type,
                version=document.version,
                title=document.title,
                metadata_text=document.metadata_text,
                content_text=content_text,
                chunks_text=chunks_text,
            )
        )
        self.stats["fts_updated"] += 1

    def _propagate_acl(self, object_id: str) -> None:
        """Stamp acl_scope on every derived row of one aggregate (ADR-009).

        Loads the authoritative object (the single source of its ACL) and
        propagates its scope to the derived projections. Best-effort: a
        missing object is skipped; the FTS leg degrades silently.
        """
        try:
            obj = self._objects.get_by_id(ObjectId.parse(object_id))
        except Exception:  # noqa: BLE001 — never let ACL stamping break a drain
            return
        if obj is None:
            return
        try:
            AclScopePropagator(self._session).propagate(obj)
        except Exception:  # noqa: BLE001 — never let ACL stamping break a drain
            _log.warning("ACL scope propagation failed for %r", object_id, exc_info=True)

    def _sync_identity(self, object_id: str) -> None:
        """Record the document's content identity (content_hash only).

        Identity is the sha256 of the NORMALIZED extracted text — never the
        filename and never the object version. The registry's canonical is
        the smallest object_id among the documents sharing the hash
        (deterministic; duplicate uploads are detected, never merged).
        """
        projection = self._content.get_content_projection(object_id)
        h = (projection or {}).get("content_hash")
        if not h:
            return
        self._safe_identity(
            lambda: self._identity.sync_document(content_hash=h, object_id=object_id)
        )
        self.stats["identity_synced"] += 1

    def _remove_identity(self, object_id: str) -> None:
        """Remove a document's identity contribution.

        Deterministic recompute of the whole registry from the remaining
        content projections (delete-all + re-insert, canonical = smallest
        object_id per hash) — guarantees a deleted canonical is replaced by
        the next representative and stale entries never survive. Delete
        frequency is low; the scan is bounded by the content-projection
        count.
        """
        from app.infrastructure.db.models.document_content_model import (
            DocumentContentModel,
        )

        rows = self._session.execute(
            select(DocumentContentModel.object_id, DocumentContentModel.content_hash)
        ).all()
        self._identity.recompute(
            [
                {"object_id": str(oid), "content_hash": h}
                for oid, h in rows
            ]
        )

    def _safe_fts(self, operation) -> None:
        """Run an FTS write without breaking the drain.

        A missing FTS table (pre-0011 database, or a harness that creates
        tables without the FTS model) degrades to the LIKE path — the
        lexical search index remains authoritative. Logged once per process.
        """
        try:
            operation()
        except _OperationalError:
            if not self._fts_warned[0]:
                self._fts_warned[0] = True
                _log.warning(
                    "document_search_fts table missing; full-text projection "
                    "degraded (run alembic upgrade head / init_db)."
                )

    def _safe_identity(self, operation) -> None:
        """Run an identity-registry write without breaking the drain
        (missing 0011 table degrades silently)."""
        try:
            operation()
        except _OperationalError:
            pass

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
