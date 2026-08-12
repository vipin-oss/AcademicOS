"""Reproducible P1 benchmark: Knowledge-Layer Scale & Identity.

Synthetic but realistic documents at 100 / 1,000 / 10,000. Measures:
- retrieval latency (realistic ~20%-match term AND pathological 100%-match
  term, reported separately)
- candidate count returned (must remain bounded)
- chunk/evidence assembly latency
- duplicate detection cost (identity-registry lookup)

Acceptance target: < 20 ms realistic retrieval at 10,000 docs on the
benchmark environment (SQLite here — PostgreSQL production numbers are NOT
claimed from SQLite measurements). If the target is not met the measured
bottleneck is reported honestly.

Usage: python scripts/benchmark_p1.py [--docs 100 1000 10000]
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa: E402
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel  # noqa: E402
from app.infrastructure.db.models.document_identity_model import DocumentIdentityModel  # noqa: E402
from app.infrastructure.db.models.search_document_model import SearchDocumentModel  # noqa: E402
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa: E402
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa: E402
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa: E402
from app.infrastructure.search.fts import ensure_fts_schema, SQLFTSRepository  # noqa: E402
from app.infrastructure.repositories.sqlalchemy_search_repository import (  # noqa: E402
    SQLAlchemySearchRepository,
)
from app.infrastructure.persistence.document_identity_store import SQLDocumentIdentityStore  # noqa: E402
from app.application.services.document_chunking import chunk_text  # noqa: E402
from app.application.services.evidence_assembly import select_chunks  # noqa: E402
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore  # noqa: E402

WORDS = (
    "conference research education university faculty student course project "
    "grant publication teaching committee meeting finance event certificate "
    "document policy notice circular syllabus paper journal funding proposal "
    "report review data"
).split()


def make_text(seed: int) -> str:
    r = random.Random(seed)
    words = [r.choice(WORDS) for _ in range(350)]
    words[5] = "zebraquirk"  # rare term present in every doc (deterministic)
    if seed % 5 == 0:
        words[20] = "projectfunding"  # realistic mid-frequency term (~20%)
    return " ".join(words)


def build(n: int, cursor: int, session) -> None:
    content, chunks, search, fts = [], [], [], []
    for i in range(n):
        oid = f"obj:document:b-{cursor + i:06d}"
        text = make_text(cursor + i)
        content.append(DocumentContentModel(
            object_id=oid, version=1, content_text=text,
            content_hash="h", source_item_id=oid, created_at="now"))
        search.append(SearchDocumentModel(
            object_id=oid, object_type="document", title=f"Report {cursor + i}",
            metadata_text="year: 2024\n", version=1))
        c = chunk_text(text)
        for idx, ch in enumerate(c):
            chunks.append(DocumentChunkModel(
                document_id=oid, chunk_index=idx, content=ch.content,
                char_start=ch.start, char_end=ch.end, token_count=ch.token_count,
                content_hash="h", version=1, source_item_id=None, created_at="now"))
        fts.append({"object_id": oid, "object_type": "document", "version": 1,
                    "title": f"Report {cursor + i}", "metadata_text": "year: 2024",
                    "content_text": text,
                    "chunks_text": "\n".join(x.content for x in c)})
    session.bulk_save_objects(content + chunks + search)
    session.commit()
    repo = SQLFTSRepository(session)
    for row in fts:
        repo.upsert(**row)
    session.commit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="+", type=int, default=[100, 1000, 10000])
    args = ap.parse_args()

    engine = create_engine("sqlite:///" + os.path.join(tempfile.mkdtemp(), "bench.db"))
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemySearchRepository(session)
    chunk_store = SQLDocumentChunkStore(session)
    identity = SQLDocumentIdentityStore(session)

    print(f"{'docs':>7} {'retrieval(real) ms':>17} {'candidates':>10} {'retrieval(patho) ms':>18} {'chunk+asm ms':>12} {'dup-check ms':>12}")
    cursor = 0
    worst_real = 0.0
    for n in args.docs:
        t0 = time.perf_counter()
        build(n, cursor, session)
        cursor += n
        build_ms = (time.perf_counter() - t0) * 1000

        # realistic mid-frequency term (~20% of docs)
        t0 = time.perf_counter()
        hits = repo.search(text="projectfunding", limit=8)
        real_ms = (time.perf_counter() - t0) * 1000
        candidates = len(hits)

        # pathological 100%-match term
        t0 = time.perf_counter()
        repo.search(text="conference", limit=8)
        patho_ms = (time.perf_counter() - t0) * 1000

        # chunk evidence assembly for the top hit
        top = hits[0].object_id if hits else None
        t0 = time.perf_counter()
        sel = select_chunks(chunk_store, top, "projectfunding") if top else []
        asm_ms = (time.perf_counter() - t0) * 1000

        # duplicate detection cost: registry lookup by an existing hash
        t0 = time.perf_counter()
        identity.canonical_for("h")
        dup_ms = (time.perf_counter() - t0) * 1000

        if n >= 10000:
            worst_real = real_ms
        print(f"{cursor:>7} {real_ms:>17.1f} {candidates:>10} {patho_ms:>18.1f} {asm_ms:>12.2f} {dup_ms:>12.2f}")

    print(f"\nbuild last batch: {build_ms:.0f} ms")
    ok = worst_real and worst_real < 20.0
    print(f"acceptance (<20 ms realistic retrieval at 10k docs): "
          f"{'PASS' if ok else ('FAIL — %.1f ms' % worst_real if worst_real else 'NOT MEASURED')}")
    print("note: pathological 100%-match term reported separately above; "
          "PostgreSQL production performance is NOT claimed from these "
          "SQLite measurements.")


if __name__ == "__main__":
    main()
