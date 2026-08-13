"""Full-text search projection (P1 Knowledge-Layer Scale & Identity).

Dialect-aware full-text indexing over the EXISTING database, derived data
only — never a source of truth:

- PostgreSQL: a ``document_search_fts`` table with a ``tsvector`` GENERATED
  column (``to_tsvector('simple', ...)`` — deterministic, language-
  independent) and a GIN index (migration 0011);
- SQLite (dev/tests): an FTS5 virtual table with the same logical columns
  (created by ``ensure_fts_schema`` via ``init_db.py`` / test fixtures).

The table is maintained by the SAME single index consumer
(``SearchIndexApplier``) and the rebuild path — exactly ONE projection
lifecycle. It is derived from ``search_documents`` + ``document_contents``
+ ``document_chunks`` (title/metadata/content/chunks text); the
authoritative state lives in the objects and their projections.

Determinism: ``simple`` config (lowercase + punctuation stripping), prefix
matching per token, deterministic tie-break by ``object_id``. ``exclude_types``
is applied in the query (WHERE on PostgreSQL; single-query filtering on
SQLite — never an N+1 loop). Query results are bounded by ``limit``.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

FTS_TABLE = "document_search_fts"

#: PostgreSQL DDL — generated tsvector over the four text fields.
_PG_DDL = """
CREATE TABLE IF NOT EXISTS document_search_fts (
    object_id VARCHAR PRIMARY KEY,
    object_type VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    metadata_text TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    chunks_text TEXT NOT NULL DEFAULT '',
    acl_scope VARCHAR,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(title, '') || ' ' || coalesce(metadata_text, '') || ' ' ||
            coalesce(content_text, '') || ' ' || coalesce(chunks_text, '')
        )
    ) STORED
);
CREATE INDEX IF NOT EXISTS ix_document_search_fts_vec
    ON document_search_fts USING GIN (search_vector);
"""

#: SQLite DDL — FTS5 virtual table (UNINDEXED columns are metadata).
_SQLITE_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS document_search_fts USING fts5(
    object_id UNINDEXED,
    object_type UNINDEXED,
    version UNINDEXED,
    title,
    metadata_text,
    content_text,
    chunks_text,
    acl_scope UNINDEXED
);
"""


def ensure_fts_schema(engine: Engine) -> None:
    """Create the FTS projection tables if absent (idempotent).

    Called by ``init_db.py`` (SQLite quickstart) and test fixtures;
    production PostgreSQL gets the same schema via migration 0011.
    """
    ddl = _PG_DDL if engine.dialect.name == "postgresql" else _SQLITE_DDL
    with engine.begin() as conn:
        conn.execute(text(ddl))


def fts_tokens(query: str) -> list[str]:
    """Deterministic tokenization for FTS queries (mirrors ``simple``)."""
    return re.findall(r"[a-z0-9]+", (query or "").lower())


def _pg_tsquery(query: str) -> str:
    tokens = fts_tokens(query)
    if not tokens:
        return ""
    return " & ".join(f"{tok}:*" for tok in tokens)


def _sqlite_match(query: str) -> str:
    tokens = fts_tokens(query)
    if not tokens:
        return ""
    return " AND ".join(f'"{tok.replace(chr(34), chr(34) * 2)}"*' for tok in tokens)


class SQLFTSRepository:
    """FTS read/write adapter over the current session (no commits)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._available: bool | None = None

    # ------------------------------------------------------------ availability
    @property
    def available(self) -> bool:
        """Whether the FTS table exists (probed once per instance)."""
        if self._available is None:
            try:
                self._session.execute(
                    text(f"SELECT 1 FROM {FTS_TABLE} LIMIT 1")
                ).scalars().all()
                self._available = True
            except OperationalError:
                self._available = False
        return self._available

    # ----------------------------------------------------------------- writes
    def upsert(
        self,
        *,
        object_id: str,
        object_type: str,
        version: int,
        title: str,
        metadata_text: str,
        content_text: str,
        chunks_text: str,
        acl_scope: str | None = None,
    ) -> None:
        """Insert/replace one FTS row (idempotent; caller owns the tx)."""
        if self._session.get_bind().dialect.name == "postgresql":
            self._session.execute(
                text(
                    f"""
                    INSERT INTO {FTS_TABLE}
                        (object_id, object_type, version, title, metadata_text,
                         content_text, chunks_text, acl_scope)
                    VALUES (:oid, :otype, :ver, :title, :meta, :content, :chunks, :acl)
                    ON CONFLICT (object_id) DO UPDATE SET
                        object_type = EXCLUDED.object_type,
                        version = EXCLUDED.version,
                        title = EXCLUDED.title,
                        metadata_text = EXCLUDED.metadata_text,
                        content_text = EXCLUDED.content_text,
                        chunks_text = EXCLUDED.chunks_text,
                        acl_scope = EXCLUDED.acl_scope
                    """
                ),
                {
                    "oid": object_id, "otype": object_type, "ver": version,
                    "title": title, "meta": metadata_text,
                    "content": content_text, "chunks": chunks_text, "acl": acl_scope,
                },
            )
        else:
            # FTS5 has no ON CONFLICT — delete-then-insert (idempotent).
            self._session.execute(
                text(f"DELETE FROM {FTS_TABLE} WHERE object_id = :oid"),
                {"oid": object_id},
            )
            self._session.execute(
                text(
                    f"INSERT INTO {FTS_TABLE} "
                    "(object_id, object_type, version, title, metadata_text, "
                    "content_text, chunks_text, acl_scope) "
                    "VALUES (:oid, :otype, :ver, :title, :meta, :content, :chunks, :acl)"
                ),
                {
                    "oid": object_id, "otype": object_type, "ver": version,
                    "title": title, "meta": metadata_text,
                    "content": content_text, "chunks": chunks_text, "acl": acl_scope,
                },
            )

    def delete(self, object_id: str) -> None:
        """Remove one FTS row (idempotent)."""
        try:
            self._session.execute(
                text(f"DELETE FROM {FTS_TABLE} WHERE object_id = :oid"),
                {"oid": object_id},
            )
        except OperationalError:
            pass  # missing table -> nothing to delete

    def clear(self) -> None:
        """Remove every FTS row (rebuild path)."""
        self._session.execute(text(f"DELETE FROM {FTS_TABLE}"))

    def delete_many(self, object_ids: list[str]) -> None:
        """Remove FTS rows for a specific set of object ids (ownership-
        scoped rebuild: a document-content rebuild must not wipe rows it
        does not own)."""
        if not object_ids:
            return
        self._session.execute(
            text(f"DELETE FROM {FTS_TABLE} WHERE object_id IN :ids"),
            {"ids": tuple(object_ids)},
        )

    # ------------------------------------------------------------------ search
    def search(
        self,
        text_query: str,
        *,
        exclude_types: set[str] | None = None,
        limit: int = 50,
    ) -> list[tuple[str, float]]:
        """Ranked ``(object_id, rank)`` for a free-text query.

        Prefix-matched per token (AND semantics). ``exclude_types`` is
        applied in SQL on PostgreSQL and inside a single query on SQLite
        (never an N+1 per-candidate loop). Bounded by ``limit``; ties
        broken by ``object_id`` ascending (deterministic).
        """
        if not self.available:
            return []
        if self._session.get_bind().dialect.name == "postgresql":
            q = _pg_tsquery(text_query)
            if not q:
                return []
            sql = (
                f"SELECT object_id, ts_rank(search_vector, to_tsquery('simple', :q)) AS r "
                f"FROM {FTS_TABLE} "
                f"WHERE search_vector @@ to_tsquery('simple', :q)"
            )
            params: dict = {"q": q}
            if exclude_types:
                sql += " AND object_type NOT IN :excl"
                params["excl"] = tuple(sorted(exclude_types))
            sql += " ORDER BY r DESC, object_id ASC LIMIT :lim"
            params["lim"] = limit
            rows = self._session.execute(text(sql), params).all()
            return [(str(r[0]), float(r[1])) for r in rows]
        # SQLite FTS5 — ONE query including the UNINDEXED object_type so
        # type filtering never becomes an N+1 per-candidate query. NOTE:
        # ORDER BY is ONLY bm25(...) — adding a secondary column disables
        # FTS5's top-N heap optimization and forces a full sort of every
        # match (measured: 10k-row common-term query ~60 ms vs ~5 ms with
        # the heap). Ties are broken deterministically below.
        q = _sqlite_match(text_query)
        if not q:
            return []
        rows = self._session.execute(
            text(
                f"SELECT object_id, object_type, "
                f"bm25({FTS_TABLE}, 0.0, 0.0, 0.0, 5.0, 3.0, 1.0, 1.0) AS r "
                f"FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH :q "
                f"ORDER BY r ASC LIMIT :lim"
            ),
            {"q": q, "lim": max(limit * 4, 200)},
        ).all()
        results: list[tuple[str, float]] = []
        for oid, otype, rank in rows:
            if exclude_types and otype in exclude_types:
                continue
            results.append((str(oid), float(rank)))
            if len(results) >= limit:
                break
        # Deterministic tie-break by object_id (rank asc, id asc).
        results.sort(key=lambda item: (item[1], item[0]))
        return results[:limit]


__all__ = ["FTS_TABLE", "SQLFTSRepository", "ensure_fts_schema", "fts_tokens"]
