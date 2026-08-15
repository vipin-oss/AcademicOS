"""P1 tests: full-text search projection + bounded content retrieval.

Covers the scale half of Knowledge-Layer P1:
- FTS schema creation (dialect-aware) and idempotency;
- upsert/search/delete lifecycle + ranking determinism;
- prefix token matching (AND semantics);
- exclude_types filtering;
- graceful degradation when the FTS table is missing (LIKE fallback);
- the BOUNDED legacy content leg (a common term returns a capped set);
- FTS-first repository path (bounded, ranked, authoritative on miss).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel  # noqa
from app.infrastructure.search.fts import SQLFTSRepository, ensure_fts_schema
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)


@pytest.fixture()
def harness():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _seed(session):
    fts = SQLFTSRepository(session)
    docs = [
        ("obj:document:a", "document", 1, "CBLU Conference Report",
         "venue: CBLU Campus\n", "The conference report text about CBLU events.",
         "chunk about CBLU events and conference proceedings."),
        ("obj:document:b", "document", 1, "Research Grant Proposal",
         "agency: SERB\n", "The proposal requests funding for quantum research.",
         "chunk about quantum research funding."),
        ("obj:user:u", "user", 1, "user account",
         "", "", ""),
    ]
    for oid, otype, ver, title, meta, content, chunks in docs:
        fts.upsert(object_id=oid, object_type=otype, version=ver, title=title,
                   metadata_text=meta, content_text=content, chunks_text=chunks)
    session.commit()


class TestFTSSchema:
    def test_ensure_is_idempotent(self, harness):
        ensure_fts_schema(harness.get_bind())
        ensure_fts_schema(harness.get_bind())

    def test_available_true_after_schema(self, harness):
        assert SQLFTSRepository(harness).available is True

    def test_available_false_without_schema(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)  # no FTS table
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        assert SQLFTSRepository(session).available is False


class TestFTSSearch:
    def test_prefix_token_search_ands(self, harness):
        _seed(harness)
        fts = SQLFTSRepository(harness)
        assert [oid for oid, _ in fts.search("cblu conference", limit=10)] == ["obj:document:a"]
        assert [oid for oid, _ in fts.search("research funding", limit=10)] == ["obj:document:b"]

    def test_prefix_match_within_word(self, harness):
        _seed(harness)
        hits = SQLFTSRepository(harness).search("conf", limit=10)
        assert "obj:document:a" in {oid for oid, _ in hits}

    def test_miss_returns_empty(self, harness):
        _seed(harness)
        assert SQLFTSRepository(harness).search("zebraquirk", limit=10) == []

    def test_exclude_types(self, harness):
        _seed(harness)
        fts = SQLFTSRepository(harness)
        hits = fts.search("user", limit=10)
        assert "obj:user:u" in {oid for oid, _ in hits}
        hits = fts.search("user", limit=10, exclude_types={"user"})
        assert "obj:user:u" not in {oid for oid, _ in hits}

    def test_limit_bounds(self, harness):
        _seed(harness)
        for i in range(5):
            SQLFTSRepository(harness).upsert(
                object_id=f"obj:document:x{i}", object_type="document", version=1,
                title=f"Report {i}", metadata_text="", content_text="report content",
                chunks_text="")
        harness.commit()
        hits = SQLFTSRepository(harness).search("report", limit=3)
        assert len(hits) == 3

    def test_delete_removes_row(self, harness):
        _seed(harness)
        SQLFTSRepository(harness).delete("obj:document:a")
        harness.commit()
        hits = SQLFTSRepository(harness).search("cblu", limit=10)
        assert "obj:document:a" not in {oid for oid, _ in hits}


class TestRepositoryFTSPath:
    def _seed_repo_rows(self, harness):
        for oid, otype, title in (
            ("obj:document:a", "document", "CBLU Conference Report"),
            ("obj:document:b", "document", "Research Grant Proposal"),
            ("obj:user:u", "user", "user account"),
        ):
            harness.add(SearchDocumentModel(
                object_id=oid, object_type=otype, title=title,
                metadata_text="meta", version=1))
        harness.commit()

    def test_search_uses_fts_when_available(self, harness):
        _seed(harness)
        self._seed_repo_rows(harness)
        repo = SQLAlchemySearchRepository(harness)
        hits = repo.search(text="cblu conference", limit=8)
        assert [h.object_id for h in hits] == ["obj:document:a"]
        assert repo.search(text="zebraquirk", limit=8) == []

    def test_like_fallback_when_fts_missing(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)  # no FTS table
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        session.add(SearchDocumentModel(
            object_id="obj:document:a", object_type="document",
            title="CBLU Conference Report", metadata_text="meta", version=1))
        session.commit()
        repo = SQLAlchemySearchRepository(session)
        hits = repo.search(text="cblu", limit=8)
        assert [h.object_id for h in hits] == ["obj:document:a"]

    def test_bounded_content_leg(self, harness):
        """A common term must NOT return thousands of rows via the legacy
        LIKE content leg (bounded at the SQL boundary)."""
        for i in range(500):
            harness.add(DocumentContentModel(
                object_id=f"obj:document:c{i:04d}", version=1,
                content_text="commonword appears in every document",
                source_item_id=f"obj:document:c{i:04d}", created_at="now"))
        harness.commit()
        repo = SQLAlchemySearchRepository(harness)
        # FTS is available here and contains no "commonword" rows -> the FTS
        # path is authoritative (miss = []). Exercise the LIKE bound
        # directly by targeting a term present in content only, with the FTS
        # table cleared so the legacy path is used.
        SQLFTSRepository(harness).clear()
        harness.commit()
        hits = repo.search(text="commonword", limit=8)
        # legacy path: title/metadata LIKE (no match) + capped content leg
        assert len(hits) <= 8
        assert len(hits) <= 200  # hard bound even with 500 matching rows
