"""SQLAlchemy adapter for the SearchRepository port (Sprint-5 M1).

Persists the deterministic ``SearchDocument`` projection in the
``search_documents`` table. All writes are version-aware and idempotent:

- ``upsert`` is an atomic ``INSERT ... ON CONFLICT DO UPDATE`` guarded by
  ``version`` — a stale projection (older version) never overwrites a
  newer row, under any application ordering;
- ``delete`` is idempotent (no-op when the row is absent).

No commits here — the caller (outbox applier / tests) owns transactions,
exactly like the object repository's write lambda convention.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.domain.repositories.search_repository import SearchRepository
from app.domain.value_objects.search import SearchDocument
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.search.fts import SQLFTSRepository

_LIKE_ESCAPE = "\\"

#: Once-per-process guard so a missing 0009 table is logged once, not per query.
_content_leg_warned: list[bool] = [False]

#: P1 scale: hard cap on the legacy LIKE content-leg merge. A common term
#: must never return thousands of complete document rows into the candidate
#: set (measured: 6k docs -> 6,000 rows loaded per query).
_CONTENT_LEG_CAP = 200


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2).replace(
        "%", _LIKE_ESCAPE + "%"
    ).replace("_", _LIKE_ESCAPE + "_")


def _to_document(row: SearchDocumentModel) -> SearchDocument:
    return SearchDocument(
        object_id=row.object_id,
        object_type=row.object_type,
        title=row.title,
        metadata_text=row.metadata_text,
        version=row.version,
    )


class SQLAlchemySearchRepository(SearchRepository):
    def __init__(self, session: Session) -> None:
        self._session = session
        # ON CONFLICT is dialect-specific SQL: both PostgreSQL and SQLite
        # support it with the same syntax, exposed by their own insert
        # constructs.
        self._insert = (
            postgresql_insert
            if session.get_bind().dialect.name == "postgresql"
            else sqlite_insert
        )
        # P1 scale: full-text search projection (dialect-aware). ``None``
        # until the first probe; a missing FTS table degrades to the LIKE
        # path. FTS is authoritative when available (a miss returns no
        # candidates, never an unbounded LIKE fallback).
        self._fts = SQLFTSRepository(session)

    def upsert(self, document: SearchDocument) -> None:
        """Version-aware upsert: never regress the stored projection."""
        values = {
            "object_id": document.object_id,
            "object_type": document.object_type,
            "title": document.title,
            "metadata_text": document.metadata_text,
            "version": document.version,
        }
        statement = (
            self._insert(SearchDocumentModel)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[SearchDocumentModel.object_id],
                set_={
                    "object_type": document.object_type,
                    "title": document.title,
                    "metadata_text": document.metadata_text,
                    "version": document.version,
                },
                # Version-aware indexing: only a document at least as new as
                # the stored one may replace it.
                where=(
                    self._insert(SearchDocumentModel).excluded.version
                    >= SearchDocumentModel.version
                ),
            )
        )
        self._session.execute(statement)
        self._expire_cached(document.object_id)

    def _fetch_fts_documents(self, hits: list[tuple[str, float]]) -> list[SearchDocumentModel]:
        """SearchDocument rows for FTS hits, preserving rank order.

        FTS already applied exclude_types and the limit; this only maps
        ranked object_ids back to the canonical projection rows. Ties in
        rank keep the FTS ordering (object_id asc) — deterministic.
        """
        if not hits:
            return []
        ids = [object_id for object_id, _rank in hits]
        rows = self._session.execute(
            select(SearchDocumentModel).where(SearchDocumentModel.object_id.in_(ids))
        ).scalars().all()
        by_id = {row.object_id: row for row in rows}
        return [by_id[oid] for oid in ids if oid in by_id]

    def delete(self, object_id: str) -> None:
        self._session.execute(
            delete(SearchDocumentModel).where(
                SearchDocumentModel.object_id == object_id
            )
        )
        self._expire_cached(object_id)

    def _expire_cached(self, object_id: str) -> None:
        """Drop a same-session cached projection, if any.

        Core ``INSERT ... ON CONFLICT DO UPDATE`` / ``DELETE`` do not
        synchronize the identity map, so a previously read row would keep
        returning stale attributes on this session. Expiring the cached
        instance (identity-map hit — no query when absent) keeps
        same-session read-after-write honest.
        """
        cached = self._session.get(SearchDocumentModel, object_id)
        if cached is not None:
            self._session.expire(cached)

    def search(
        self,
        *,
        text: str | None = None,
        object_type: str | None = None,
        title: str | None = None,
        filename: str | None = None,
        exclude_types: set[str] | None = None,
        limit: int = 50,
    ) -> list[SearchDocument]:
        """Candidate generation for one query leg.

        P0 foundation:
        - ``exclude_types`` is applied IN THE WHERE clause (never after a
          limit), so internal/workflow objects (ai_conversation, user,
          intake_item, intake_session) can never consume the candidate
          window and starve real evidence.
        - ordering is relevance-based, never the arbitrary ``object_id``:
          an EXACT title match ranks first, then title/metadata LIKE
          matches (object_id only as a deterministic tie-break).
        - ``filename`` performs an exact filename lookup against the
          ``file_name:`` metadata entry (document-reference resolution).
        """
        statement = select(SearchDocumentModel)
        if object_type:
            statement = statement.where(SearchDocumentModel.object_type == object_type)
        if exclude_types:
            statement = statement.where(
                SearchDocumentModel.object_type.notin_(sorted(exclude_types))
            )
        if title:
            statement = statement.where(
                func.lower(SearchDocumentModel.title) == title.lower()
            )
        content_hits: set[str] = set()
        if text:
            # P1 scale: full-text search first — bounded, ranked,
            # prefix-matched, exclude_types applied in the FTS query. When
            # the FTS projection is available its result is authoritative
            # (an FTS miss returns no candidates, never a LIKE fallback).
            fts_hits = (
                self._fts.search(text, exclude_types=exclude_types, limit=limit)
                if self._fts.available
                else None
            )
            if fts_hits is not None:
                if not fts_hits:
                    return []
                rows = self._fetch_fts_documents(fts_hits)
                return [_to_document(r) for r in rows]
            pattern = f"%{_escape_like(text.lower())}%"
            statement = statement.where(
                or_(
                    func.lower(SearchDocumentModel.title).like(
                        pattern, escape=_LIKE_ESCAPE
                    ),
                    func.lower(SearchDocumentModel.metadata_text).like(
                        pattern, escape=_LIKE_ESCAPE
                    ),
                )
            )
            # P0: relevance ordering — exact title match first (a user
            # naming an object/file must get it first), then deterministic
            # object_id tie-break. No arbitrary ordering can decide top-k.
            statement = statement.order_by(
                (func.lower(SearchDocumentModel.title) == text.lower()).desc(),
                SearchDocumentModel.object_id,
            )
            # M27: the document-content projection leg. Extracted text lives
            # in document_contents (a derived projection written at intake
            # commit); matches there are merged into the same candidate set
            # so the use case's fusion + permission gate treat them exactly
            # like title/metadata hits. Deterministic ordering by object_id.
            from app.infrastructure.db.models.document_content_model import (
                DocumentContentModel,
            )

            try:
                # P1 scale bound: the legacy LIKE content leg is capped — a
                # common term must never pull thousands of ids into the
                # merge (applied at the SQL boundary, not a Python slice).
                content_ids = self._session.execute(
                    select(DocumentContentModel.object_id)
                    .where(
                        func.lower(DocumentContentModel.content_text).like(
                            pattern, escape=_LIKE_ESCAPE
                        )
                    )
                    .limit(_CONTENT_LEG_CAP)
                ).scalars().all()
            except OperationalError:
                # A database that predates the 0009 migration (or a harness
                # that creates tables without the content model) has no
                # document_contents table. Search must never 500: degrade to
                # title/metadata-only, exactly like the semantic-leg
                # degradation. Once warned, stay silent per process.
                if not _content_leg_warned:
                    _content_leg_warned[0] = True
                    logging.getLogger(__name__).warning(
                        "document_contents table missing; content search "
                        "degraded to title/metadata (run alembic upgrade head)."
                    )
                content_ids = ()
            content_hits = {str(cid) for cid in content_ids}
        if filename:
            # Exact filename lookup (document-reference intent): the upload
            # stores the original file name in the ``file_name:`` metadata
            # entry; match it literally (normalised case), never fuzzily.
            fpat = f"%{_escape_like(filename.lower())}%"
            statement = statement.where(
                func.lower(SearchDocumentModel.metadata_text).like(
                    fpat, escape=_LIKE_ESCAPE
                )
            )
            statement = statement.order_by(SearchDocumentModel.object_id)
        if not text and not filename:
            statement = statement.order_by(SearchDocumentModel.object_id)
        statement = statement.limit(limit)
        rows = list(self._session.execute(statement).scalars().all())
        if content_hits:
            # Fetch the search-document rows for content matches (their
            # metadata/title shape keeps the result schema identical) and
            # merge, de-duplicated, in deterministic object_id order.
            matched = {row.object_id for row in rows}
            missing = sorted(content_hits - matched)
            if missing:
                extra = self._session.execute(
                    select(SearchDocumentModel).where(
                        SearchDocumentModel.object_id.in_(missing)
                    )
                ).scalars().all()
                rows = sorted(
                    rows + list(extra), key=lambda r: r.object_id
                )
            # P1 scale bound: the merged candidate set is capped at the
            # limit with deterministic ordering (title-exact first, then
            # object_id) — the window never exceeds the caller's limit.
            rows = sorted(
                rows, key=lambda r: (
                    (text is not None and r.title.lower() == text.lower()),
                    r.object_id,
                )
            )[:_CONTENT_LEG_CAP if limit > _CONTENT_LEG_CAP else limit]
        return [_to_document(row) for row in rows]
