"""P1 tests: bounded chunk evidence assembly.

Covers the chunk stage of the AI runtime path:
- ranking (query-term chunk first, token-overlap next, then index order);
- explicit bounds (max chunks per doc, max chars per doc);
- adjacent-chunk expansion (successor joins when budget allows);
- duplicate removal + final document order;
- determinism (identical input -> identical selection);
- provenance (chunk index + char span in the rendered header);
- empty term / no chunks -> [] (caller falls back to whole text).
"""
from __future__ import annotations

from app.application.ports.document_chunk_store import DocumentChunkStore
from app.application.services.evidence_assembly import (
    render_chunk_evidence,
    select_chunks,
)


class _FakeChunkStore(DocumentChunkStore):
    def __init__(self, chunks):
        self._chunks = chunks

    def replace(self, *, document_id, version, source_item_id, chunks):
        raise NotImplementedError

    def delete_by_document(self, document_id):
        raise NotImplementedError

    def delete_all(self):
        raise NotImplementedError

    def count(self, document_id):
        return len(self._chunks)

    def by_document(self, document_id):
        return list(self._chunks)


def _chunk(index, text, start=None):
    start = start if start is not None else index * 200
    return {
        "document_id": "obj:document:d",
        "chunk_index": index,
        "content": text,
        "char_start": start,
        "char_end": start + len(text),
        "token_count": len(text.split()),
        "content_hash": f"h{index}",
        "version": 1,
        "source_item_id": None,
    }


def _corpus():
    return [
        _chunk(0, "The certificate was issued after the conference ended."),
        _chunk(1, "In Honor International Conference of Srinivasa Ramanujan's Birthday."),
        _chunk(2, "Organized by Chaudhary Bansi Lal University (CBLU), Bhiwani."),
        _chunk(3, "Held on 19 and 20 January 2024 at the university auditorium."),
        _chunk(4, "This certificate is issued for academic record purposes."),
    ]


class TestChunkSelection:
    def test_term_chunk_ranked_first(self):
        store = _FakeChunkStore(_corpus())
        # With a single-chunk budget, ONLY the term-containing chunk is
        # selected (ranking decides selection; final order is document order).
        chunks = select_chunks(store, "obj:document:d", "Ramanujan", max_chunks=1)
        assert [c["chunk_index"] for c in chunks] == [1]

    def test_term_chunk_selected_within_budget(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "Ramanujan", max_chunks=2)
        assert 1 in [c["chunk_index"] for c in chunks]

    def test_bounded_chunks_per_document(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "conference", max_chunks=2)
        assert len(chunks) <= 2

    def test_bounded_total_chars(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "conference", max_chars=500)
        assert sum(len(c["content"]) for c in chunks) <= 500

    def test_adjacent_expansion(self):
        store = _FakeChunkStore(_corpus())
        # term in chunk 1 -> chunk 2 (successor) joins when budget allows;
        # chunk 0 (no match) must NOT be selected ahead of the successor.
        chunks = select_chunks(store, "obj:document:d", "Ramanujan",
                               max_chunks=2, max_chars=2000)
        indexes = [c["chunk_index"] for c in chunks]
        assert indexes == [1, 2]

    def test_document_order_after_ranking(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "conference",
                               max_chunks=3, max_chars=2000)
        indexes = [c["chunk_index"] for c in chunks]
        assert indexes == sorted(indexes)  # final order = document order

    def test_no_duplicates(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "conference")
        indexes = [c["chunk_index"] for c in chunks]
        assert len(indexes) == len(set(indexes))

    def test_determinism(self):
        store = _FakeChunkStore(_corpus())
        a = select_chunks(store, "obj:document:d", "conference")
        b = select_chunks(store, "obj:document:d", "conference")
        assert a == b

    def test_empty_term_returns_empty(self):
        store = _FakeChunkStore(_corpus())
        assert select_chunks(store, "obj:document:d", "") == []

    def test_no_chunks_returns_empty(self):
        store = _FakeChunkStore([])
        assert select_chunks(store, "obj:document:d", "conference") == []


class TestRender:
    def test_provenance_spans(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "Ramanujan",
                               max_chunks=2, max_chars=2000)
        text, prov = render_chunk_evidence("Cblu Jan, 2024.pdf", chunks)
        assert "chunks " in prov
        assert "chars " in prov
        assert text == "\n\n".join(c["content"] for c in chunks)

    def test_empty_render(self):
        assert render_chunk_evidence("x", []) == ("", "")

    def test_span_values_match_content(self):
        store = _FakeChunkStore(_corpus())
        chunks = select_chunks(store, "obj:document:d", "conference", max_chunks=3)
        for c in chunks:
            assert c["content"] == _corpus()[c["chunk_index"]]["content"]
