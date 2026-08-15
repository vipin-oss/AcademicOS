"""Deterministic document chunking service (P0 knowledge projection).

ONE algorithm, ONE output: two executions on identical normalized content
produce byte-identical chunk representations (deterministic rebuild).

Normalization (deterministic, no semantic cleanup):
- CRLF/CR -> LF
- runs of 3+ newlines -> exactly two (``\\n\\n`` paragraph break)
- runs of spaces/tabs -> a single space
- whitespace trimmed at the ends; spaces stripped around newlines

Boundary priority within ``[start, start + max_chars)``:
1. PARAGRAPH boundary (last ``\\n\\n``)   -> boundary after the ``\\n\\n``
2. SENTENCE boundary (last ``.!?`` followed by space/newline/end)
3. WHITESPACE boundary (last space)
4. HARD split at ``start + max_chars`` (no boundary exists in range)

Overlap (deterministic): the next chunk starts at ``end - overlap``, then
advances to the FIRST sentence boundary in the overlap tail of the previous
chunk (overlap never splits a sentence); when no sentence boundary exists
it uses a whitespace boundary at or before the candidate; otherwise the
candidate itself. Invariants guaranteed by construction:

- no gaps:  ``next_start <= end`` always (overlap allowed, gaps forbidden)
- progress: ``next_start > start`` for any chunk longer than ``overlap``
- spans:    ``start``/``end`` are absolute offsets into the normalized text
- word-split: never (sentence/whitespace boundaries only; the hard split
  is the documented fallback for pathological inputs)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

#: Default maximum chunk length (chars of normalized text).
DEFAULT_MAX_CHARS = 1000
#: Default overlap (chars) between adjacent chunks.
DEFAULT_OVERLAP = 120

_CRLF_RE = re.compile(r"\r\n?")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_SPACES_RE = re.compile(r"[ \t]+")
_EDGE_SPACE_RE = re.compile(r"[ \t]+\n|\n[ \t]+")
_SENTENCE_PUNCT = ".!?"
_WS = " \n"


def normalize_content(text: str) -> str:
    """Deterministic normalization used for chunking AND content hashing."""
    if not text:
        return ""
    t = _CRLF_RE.sub("\n", text)
    t = _MULTI_NL_RE.sub("\n\n", t)
    # Two passes: a substitution can consume the boundary marker, leaving
    # whitespace on the other side ("a \n b" -> "a\n b" after one pass).
    t = _EDGE_SPACE_RE.sub("\n", t)
    t = _EDGE_SPACE_RE.sub("\n", t)
    t = _SPACES_RE.sub(" ", t)
    return t.strip()


def content_hash(text: str) -> str:
    """SHA-256 of the NORMALIZED content (NOT the source-file bytes).

    This is the authority for content-change detection: identical normalized
    text -> identical hash -> no re-chunking/re-embedding. Source-file
    SHA-256 (intake ``KEY_SHA256``) is a separate, complementary fact.
    """
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Chunk:
    """One deterministic chunk: absolute character span in normalized text."""

    start: int
    end: int
    content: str

    @property
    def token_count(self) -> int:
        return len(self.content.split())


def _last_boundary_in(text: str, start: int, end: int, needle: str) -> int | None:
    """Position AFTER the last occurrence of ``needle`` in ``text[start:end]``.

    ``needle`` is a single character or a multi-char marker; the returned
    index is ``match.start() + len(needle)`` so slicing ``text[start:idx]``
    ends at the boundary.
    """
    idx = text.rfind(needle, start, end)
    if idx < 0:
        return None
    return idx + len(needle)


def _sentence_boundaries(text: str, start: int, end: int) -> list[int]:
    """Sentence-boundary positions (after ``.!?`` + space/newline/end)."""
    out: list[int] = []
    limit = min(end, len(text))
    for i in range(start, limit):
        ch = text[i]
        if ch in _SENTENCE_PUNCT:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt in ("", " ", "\n"):
                out.append(i + 1)
    return out


def _find_chunk_end(text: str, start: int, max_chars: int) -> int:
    """Longest legal boundary <= ``start + max_chars`` (priority order)."""
    hard = min(start + max_chars, len(text))
    if hard - start <= 0:
        return start
    # 1. paragraph
    idx = _last_boundary_in(text, start, hard, "\n\n")
    if idx is not None:
        return idx
    # 2. sentence
    sentences = _sentence_boundaries(text, start, hard)
    if sentences:
        return sentences[-1]
    # 3. whitespace
    idx = _last_boundary_in(text, start, hard, " ")
    if idx is not None:
        return idx
    # 4. hard split
    return hard


def _skip_ws(text: str, pos: int) -> int:
    """Advance past immediately-following whitespace (clean chunk starts)."""
    while pos < len(text) and text[pos] in _WS:
        pos += 1
    return pos


def _next_start(text: str, end: int, overlap: int, chunk_len: int) -> int:
    """Deterministic next-chunk start: overlap, sentence-aligned, no gaps.

    Chunks shorter than or equal to ``overlap`` get NO overlap (their next
    chunk starts exactly at ``end``) — overlapping a tiny chunk can make the
    sentence-aligned candidate fall back onto the current start and force a
    mid-word progress split.
    """
    if chunk_len <= overlap:
        return end
    candidate = end - overlap
    if candidate <= 0:
        return 0
    # Prefer the first sentence boundary inside the overlap tail.
    for pos in _sentence_boundaries(text, candidate, end):
        return _skip_ws(text, pos)
    # Whitespace boundary at or before the candidate.
    if text[candidate] in _WS:
        return _skip_ws(text, candidate)
    j = candidate
    while j > 0 and text[j - 1] not in _WS:
        j -= 1
    if j > 0:
        return _skip_ws(text, j)
    return candidate


def chunk_text(
    text: str, *, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[Chunk]:
    """Split normalized content into deterministic chunks.

    ``overlap`` must be < ``max_chars``. Short documents (< ``max_chars``)
    produce exactly one chunk. Empty input produces no chunks.
    """
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    t = normalize_content(text)
    if not t:
        return []
    if len(t) <= max_chars:
        return [Chunk(start=0, end=len(t), content=t)]

    chunks: list[Chunk] = []
    start = 0
    while start < len(t):
        end = _find_chunk_end(t, start, max_chars)
        if end <= start:
            end = min(start + 1, len(t))
        chunks.append(Chunk(start=start, end=end, content=t[start:end]))
        if end >= len(t):
            break
        nxt = _next_start(t, end, overlap, chunk_len=end - start)
        if nxt >= end:
            nxt = end  # no gap; no overlap in this degenerate case
        if nxt <= start:
            nxt = min(end, start + max(1, overlap // 2))
        start = nxt
    return chunks


def chunks_identical(a: list[Chunk], b: list[Chunk]) -> bool:
    """Structural equality used by rebuild-equivalence assertions."""
    if len(a) != len(b):
        return False
    return all(
        x.start == y.start and x.end == y.end and x.content == y.content
        for x, y in zip(a, b)
    )


__all__ = [
    "Chunk",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_OVERLAP",
    "chunk_text",
    "chunks_identical",
    "content_hash",
    "normalize_content",
]
