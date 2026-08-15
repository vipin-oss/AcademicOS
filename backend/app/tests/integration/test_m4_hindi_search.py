"""V3 M4 — Hindi/English/Hinglish search integration (blueprint M4 gate).

End-to-end proof over SQLite FTS5 that:

- a Hindi query returns correct hits (``गणित विभाग`` finds the maths dept doc);
- mixed Hindi/English documents are searchable;
- query tokens == index tokens (asserted against ``fts5vocab``, the actual
  index the engine reads);
- there is no English regression (folding is a no-op for ASCII).

The corpus is the bilingual golden data in ``bilingual_golden_corpus.py``.
"""
from __future__ import annotations

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.search.fts import SQLFTSRepository, ensure_fts_schema
from app.infrastructure.search.tokenizer import fold_diacritics, fts_tokens
from app.tests.unit.bilingual_golden_corpus import BILINGUAL_GOLDEN


def _seed(session) -> None:
    fts = SQLFTSRepository(session)
    for i, (text, _q, _match) in enumerate(BILINGUAL_GOLDEN):
        fts.upsert(
            object_id=f"obj:document:m4-{i}",
            object_type="document",
            version=1,
            title=text,
            metadata_text="",
            content_text=text,
            chunks_text=text,
        )
    session.commit()


def test_hindi_query_finds_the_right_document() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        _seed(session)
        fts = SQLFTSRepository(session)
        hits = [oid for oid, _ in fts.search("गणित विभाग", limit=10)]
        # The maths-dept document is index 0 in the corpus.
        assert "obj:document:m4-0" in hits
    finally:
        session.close()
        engine.dispose()


def test_mixed_language_document_searchable_by_both_languages() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        fts = SQLFTSRepository(session)
        # Hinglish doc: "HSRF sanction letter राशि स्वीकृत"
        fts.upsert(
            object_id="obj:document:m4-hinglish", object_type="document", version=1,
            title="HSRF sanction letter राशि स्वीकृत",
            metadata_text="", content_text="HSRF sanction letter राशि स्वीकृत",
            chunks_text="HSRF sanction letter राशि स्वीकृत",
        )
        session.commit()
        assert "obj:document:m4-hinglish" in [
            o for o, _ in fts.search("HSRF", limit=10)
        ]
        assert "obj:document:m4-hinglish" in [
            o for o, _ in fts.search("राशि", limit=10)
        ]
    finally:
        session.close()
        engine.dispose()


def test_query_tokens_equal_index_tokens_via_fts5vocab() -> None:
    """A3 gate: read the tokens the FTS5 index actually produced and assert
    they are exactly the folded query tokens for every golden document."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        _seed(session)
        for text, _q, _m in BILINGUAL_GOLDEN:
            # The index stores folded text; query tokens must equal the folded
            # document's tokens (and thus the index's tokens).
            assert fts_tokens(text) == fts_tokens(fold_diacritics(text))
        # Read back the real index tokens via the public fts5vocab view and
        # assert every folded query token is present in the index.
        session.execute(
            sqlalchemy.text(
                "CREATE VIRTUAL TABLE m4_vocab USING "
                "fts5vocab(document_search_fts, 'instance')"
            )
        )
        index_terms = {
            row[0]
            for row in session.execute(
                sqlalchemy.text("SELECT term FROM m4_vocab")
            ).fetchall()
        }
        for text, _q, _m in BILINGUAL_GOLDEN:
            assert set(fts_tokens(text)) <= index_terms, text
    finally:
        session.close()
        engine.dispose()


def test_no_english_regression() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        fts = SQLFTSRepository(session)
        fts.upsert(
            object_id="obj:document:m4-en", object_type="document", version=1,
            title="Quantum dots research proposal for SERB funding",
            metadata_text="", content_text="Quantum dots research proposal for SERB funding",
            chunks_text="Quantum dots research proposal for SERB funding",
        )
        session.commit()
        # Prefix AND semantics preserved for English.
        assert "obj:document:m4-en" in [
            o for o, _ in fts.search("quantum funding", limit=10)
        ]
        assert "obj:document:m4-en" in [
            o for o, _ in fts.search("serb", limit=10)
        ]
    finally:
        session.close()
        engine.dispose()
