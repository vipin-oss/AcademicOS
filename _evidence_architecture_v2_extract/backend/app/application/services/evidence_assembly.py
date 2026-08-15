"""Bounded chunk evidence assembly (P1).

The chunk stage of the AI runtime path:

    query → retrieval plan → document candidates (bounded, ACL-gated)
         → CHUNK SEARCH (this module) → ranked, bounded chunk evidence
         → evidence assembly → claim verification → answer

Rules (deterministic, explicit bounds):
- ``max_chunks`` per document (default 3);
- ``max_chars`` total per document (default 2,000 — the existing per-item
  evidence cap, so the prompt budget is unchanged);
- chunks containing the query term rank first, then token-overlap chunks,
  then by ``chunk_index`` (deterministic);
- ADJACENT-CHUNK EXPANSION: the chunk immediately after each chosen chunk
  is included when the budget allows (context continuity for the model) —
  never before it, never unbounded;
- duplicate removal by ``chunk_index``; final ordering by ``chunk_index``
  (document order) so the rendered evidence reads naturally;
- provenance: every selected chunk retains ``chunk_index``, ``char_start``,
  ``char_end``, ``content_hash``; the rendered header exposes the span.

Whole-document text remains the fallback when a document has no chunks
(short/unextracted documents, structured objects) — the caller decides.
"""
from __future__ import annotations

import re

from app.application.ports.document_chunk_store import DocumentChunkStore

#: Maximum number of chunks selected per document.
MAX_CHUNKS_PER_DOC = 3
#: Maximum total evidence characters per document (matches the existing
#: per-item source cap — the overall evidence budget stays bounded).
MAX_CHUNK_EVIDENCE_CHARS = 2000


def _tokens(term: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (term or "").lower())


def select_chunks(
    chunk_store: DocumentChunkStore,
    document_id: str,
    term: str,
    *,
    max_chunks: int = MAX_CHUNKS_PER_DOC,
    max_chars: int = MAX_CHUNK_EVIDENCE_CHARS,
) -> list[dict]:
    """Ranked, bounded chunk selection for one document and query term.

    Returns chunk rows (from the store's ``by_document`` shape) in document
    order. ``[]`` when the document has no chunks or the term is empty.
    """
    chunks = chunk_store.by_document(document_id)
    if not chunks or not term:
        return []
    tokens = _tokens(term)
    if not tokens:
        return []
    term_lower = term.lower()

    scored: list[tuple[int, int, dict]] = []
    for chunk in chunks:
        low = chunk["content"].lower()
        if term_lower in low:
            score = 2
        elif any(tok in low for tok in tokens):
            score = 1
        else:
            score = 0
        scored.append((score, chunk["chunk_index"], chunk))

    # Deterministic ranking: score desc, chunk_index asc.
    scored.sort(key=lambda item: (-item[0], item[1]))
    matches = [(score, idx, chunk) for score, idx, chunk in scored if score >= 1]
    if not matches:
        # No chunk overlaps the query term at all -> no chunk evidence
        # (the caller falls back to whole-document text).
        return []

    chosen: list[dict] = []
    used = 0
    for score, _idx, chunk in matches:
        if len(chosen) >= max_chunks:
            break
        if used + len(chunk["content"]) > max_chars:
            break
        chosen.append(chunk)
        used += len(chunk["content"])

    # Adjacent-chunk expansion: the successor of each chosen chunk joins
    # when the budget allows (continuity; never unbounded; never displaced
    # by a zero-score chunk).
    by_index = {chunk["chunk_index"]: chunk for chunk in chunks}
    for chunk in list(chosen):
        nxt = by_index.get(chunk["chunk_index"] + 1)
        if (
            nxt is not None
            and nxt not in chosen
            and len(chosen) < max_chunks
            and used + len(nxt["content"]) <= max_chars
        ):
            chosen.append(nxt)
            used += len(nxt["content"])

    chosen.sort(key=lambda chunk: chunk["chunk_index"])
    return chosen


def render_chunk_evidence(title: str, chunks: list[dict]) -> tuple[str, str]:
    """Render selected chunks into ``(text, provenance_note)``.

    ``provenance_note`` names the chunk range and character span so the
    citation/evidence layer can point at the exact supporting span.
    """
    if not chunks:
        return "", ""
    text = "\n\n".join(chunk["content"] for chunk in chunks)
    first, last = chunks[0], chunks[-1]
    provenance = (
        f"chunks {first['chunk_index']}–{last['chunk_index']}, "
        f"chars {first['char_start']}–{last['char_end']}"
    )
    return text, provenance


__all__ = [
    "MAX_CHUNKS_PER_DOC",
    "MAX_CHUNK_EVIDENCE_CHARS",
    "render_chunk_evidence",
    "select_chunks",
]
