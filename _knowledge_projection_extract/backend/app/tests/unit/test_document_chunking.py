"""Unit tests: deterministic document chunking (P0 knowledge projection).

Covers the ONE algorithm from the red-team audit:
- normalization (deterministic; CRLF/CR->LF, newline runs->paragraph break,
  whitespace runs->single space, edge trimming);
- boundary priority (paragraph -> sentence -> whitespace -> hard split);
- overlap (sentence-aligned; no overlap for chunks <= overlap length);
- absolute character spans with NO gaps and NO mid-word splits;
- determinism (two executions byte-identical);
- golden fixture (exact span list for a fixed long document);
- short / empty / degenerate inputs.
"""
from __future__ import annotations

from app.application.services.document_chunking import (
    Chunk,
    chunk_text,
    content_hash,
    normalize_content,
)

# ---------------------------------------------------------------------------
# Fixtures (stable literals)
# ---------------------------------------------------------------------------

SHORT = (
    "CERTIFICATE OF PARTICIPATION\n\n"
    "This is to certify that Dr Anil Kumar has participated in the In Honor "
    "International Conference of Srinivasa Ramanujan's Birthday organized by "
    "Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and 20 January "
    "2024 at the university auditorium.\n"
)

# A deterministic long document (> max_chars) built from fixed templates.
_PARAS = []
_TEMPLATES = [
    "The National Conference on Emerging Trends in Higher Education was organized by Chaudhary Bansi Lal University (CBLU), Bhiwani, during the third week of January. The inaugural session was addressed by the Vice Chancellor who spoke about the role of digital pedagogy in modern universities. More than two hundred fifty participants registered for the conference from across the country.",
    "The technical sessions covered research ethics, outcome based education, artificial intelligence in classrooms, and the transformation of examination systems. Each session was followed by an open discussion moderated by senior faculty members. Selected papers from the conference were published in the conference proceedings with an ISBN number.",
    "The valedictory session distributed certificates of participation to all delegates and awards for the best paper presentations. The organizing committee expressed gratitude to the sponsors and the university administration for their continued support. Participants provided feedback through a structured questionnaire administered on the final day.",
    "A cultural evening featuring classical music and folk dances was arranged for the delegates on the second day of the conference. The event concluded with a high tea and informal networking session among academicians from different institutions.",
]
for _block in range(6):
    for _idx, _t in enumerate(_TEMPLATES):
        _PARAS.append(f"Paragraph {_block * 4 + _idx + 1}: {_t}")
LONG = "\n\n".join(_PARAS)

#: Golden spans for ``chunk_text(LONG, max_chars=1000, overlap=120)`` —
#: captured from the verified algorithm output; any change to the algorithm
#: must be reflected here intentionally (and the invariants must still hold).
GOLDEN_SPANS = [
    (0, 760), (657, 1382), (1265, 2142), (2039, 2764), (2647, 3525),
    (3422, 4149), (4032, 4911), (4808, 5535), (5418, 6297), (6194, 6921),
    (6804, 7683), (7580, 8047), (7949, 8047), (8047, 8305),
]


class TestNormalize:
    def test_crlf_and_cr_normalized(self):
        assert normalize_content("a\r\nb\rc") == "a\nb\nc"

    def test_newline_runs_become_paragraph_break(self):
        assert normalize_content("a\n\n\n\nb") == "a\n\nb"

    def test_whitespace_runs_collapse(self):
        assert normalize_content("a   b\t\tc") == "a b c"

    def test_edge_whitespace_trimmed(self):
        assert normalize_content("  hello  ") == "hello"
        assert normalize_content("a \n b") == "a\nb"

    def test_empty(self):
        assert normalize_content("") == ""
        assert normalize_content("   \n  ") == ""


class TestContentHash:
    def test_hash_is_sha256_of_normalized_text(self):
        import hashlib
        expected = hashlib.sha256(normalize_content("A   B").encode()).hexdigest()
        assert content_hash("A   B") == expected

    def test_equal_after_normalization(self):
        assert content_hash("CBLU  conference") == content_hash("CBLU conference")

    def test_differs_for_different_text(self):
        assert content_hash("one") != content_hash("two")


class TestChunkingBasics:
    def test_empty_text_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        chunks = chunk_text(SHORT)
        assert len(chunks) == 1
        assert chunks[0].start == 0
        assert chunks[0].end == len(normalize_content(SHORT))
        assert chunks[0].content == normalize_content(SHORT)

    def test_overlap_must_be_smaller_than_max_chars(self):
        import pytest

        with pytest.raises(ValueError):
            chunk_text(SHORT, max_chars=100, overlap=100)


class TestGoldenFixture:
    def test_golden_spans(self):
        chunks = chunk_text(LONG)
        assert [(c.start, c.end) for c in chunks] == GOLDEN_SPANS

    def test_golden_content_equals_span_slices(self):
        t = normalize_content(LONG)
        chunks = chunk_text(LONG)
        for c in chunks:
            assert c.content == t[c.start:c.end]

    def test_no_gaps_no_midword_no_overlap_excess(self):
        t = normalize_content(LONG)
        chunks = chunk_text(LONG)
        for i, c in enumerate(chunks):
            assert c.end > c.start
            assert c.start >= 0 and c.end <= len(t)
            if i == 0:
                continue
            prev = chunks[i - 1]
            assert c.start <= prev.end, f"gap before chunk {i}"
            if c.start < prev.end:
                assert prev.end - c.start <= 120, f"overlap > 120 at {i}"
            if c.start > 0 and t[c.start - 1] not in " \n.!?":
                raise AssertionError(f"mid-word split at chunk {i} ({t[c.start-1]!r})")
            # chunk starts are clean (no leading whitespace) except the first
            if c.start > 0 and c.content and c.content[0] in " \n":
                raise AssertionError(f"chunk {i} starts with whitespace")

    def test_determinism_byte_identical(self):
        a = chunk_text(LONG)
        b = chunk_text(LONG)
        assert a == b
        assert [c.content for c in a] == [c.content for c in b]

    def test_boundary_priority_paragraph_first(self):
        # A paragraph break well inside the range must be chosen over a
        # later sentence boundary.
        text = "X" * 50 + "\n\n" + "Y" * 500 + ". " + "Z" * 200 + "."
        chunks = chunk_text(text, max_chars=200, overlap=40)
        first = chunks[0]
        assert first.content == text[:52]  # 50 X's + paragraph break
