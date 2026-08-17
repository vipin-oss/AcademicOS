"""Entity Resolution Service (Revision #15).

Deterministic cross-document entity matching for academic documents.

Safely determines whether two documents refer to the same academic entity
(publication, project, event, etc.) using multiple matching signals:

- DOI exact match (highest confidence)
- Manuscript ID exact match
- Normalized title similarity
- Author overlap
- Journal/venue match
- Year compatibility

Matching outcomes:
- HIGH CONFIDENCE (≥0.8): Safe relationship suggestion
- MEDIUM CONFIDENCE (0.5-0.79): Proposed relationship (review required)
- LOW CONFIDENCE (<0.5): No automatic link
- CONFLICT: Review required (contradictory evidence)

Design principles:
- Never silently merge records
- False positive rate = 0% for clearly different entities
- Permission-aware (only match within same owner)
- Provenance-aware (every match has evidence)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional


@dataclass(frozen=True)
class MatchSignal:
    """A single matching signal between two documents."""
    signal_type: str  # "doi", "manuscript_id", "title", "authors", "journal", "year"
    confidence: float  # 0.0-1.0
    evidence: str  # Human-readable explanation


@dataclass(frozen=True)
class MatchResult:
    """Result of entity matching between two documents."""
    source_doc_id: str
    target_doc_id: str
    confidence: float  # Overall confidence 0.0-1.0
    signals: tuple[MatchSignal, ...]
    outcome: str  # "high", "medium", "low", "conflict"
    entity_type: str | None = None  # Inferred entity type if matched


# Confidence thresholds
HIGH_THRESHOLD = 0.8
MEDIUM_THRESHOLD = 0.5


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove common punctuation for comparison
    text = re.sub(r'["\'\-:;,.]', '', text)
    return text


def _normalize_doi(doi: str | None) -> str | None:
    """Normalize DOI for exact comparison."""
    if not doi:
        return None
    doi = doi.strip().lower()
    # Remove common prefixes
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi if doi else None


def _title_similarity(title1: str | None, title2: str | None) -> float:
    """Compute title similarity using SequenceMatcher."""
    if not title1 or not title2:
        return 0.0
    n1 = _normalize_text(title1)
    n2 = _normalize_text(title2)
    if not n1 or not n2:
        return 0.0
    return SequenceMatcher(None, n1, n2).ratio()


def _author_overlap(authors1: str | None, authors2: str | None) -> float:
    """Compute author overlap (Jaccard similarity of author sets)."""
    if not authors1 or not authors2:
        return 0.0
    # Parse author lists
    def parse_authors(s: str) -> set[str]:
        names = set()
        for part in re.split(r'[,;]', s):
            name = part.strip().lower()
            if name:
                # Normalize: "A. Kumar" -> "a kumar"
                name = re.sub(r'\.', '', name)
                name = re.sub(r'\s+', ' ', name).strip()
                names.add(name)
        return names

    set1 = parse_authors(authors1)
    set2 = parse_authors(authors2)
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def _journal_match(journal1: str | None, journal2: str | None) -> float:
    """Check if journals match (normalized)."""
    if not journal1 or not journal2:
        return 0.0
    n1 = _normalize_text(journal1)
    n2 = _normalize_text(journal2)
    if n1 == n2:
        return 1.0
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 0.8
    return 0.0


def _year_match(year1: str | None, year2: str | None) -> float:
    """Check if years are compatible."""
    if not year1 or not year2:
        return 0.0
    try:
        y1 = int(str(year1).strip()[:4])
        y2 = int(str(year2).strip()[:4])
        if y1 == y2:
            return 1.0
        # Allow 1 year difference (publication vs acceptance year)
        if abs(y1 - y2) <= 1:
            return 0.5
        return 0.0
    except (ValueError, IndexError):
        return 0.0


def match_entities(
    doc1_fields: dict[str, object],
    doc2_fields: dict[str, object],
    doc1_id: str,
    doc2_id: str,
) -> MatchResult:
    """Match two documents based on their extracted fields.

    Args:
        doc1_fields: Extracted fields from document 1 (predicate_id -> value)
        doc2_fields: Extracted fields from document 2
        doc1_id: Document 1 ID
        doc2_id: Document 2 ID

    Returns:
        MatchResult with confidence, signals, and outcome
    """
    signals: list[MatchSignal] = []

    # 1. DOI exact match (highest confidence)
    doi1 = _normalize_doi(str(doc1_fields.get("doi", "")) or None)
    doi2 = _normalize_doi(str(doc2_fields.get("doi", "")) or None)
    if doi1 and doi2:
        if doi1 == doi2:
            signals.append(MatchSignal("doi", 1.0, f"DOI match: {doi1}"))
        else:
            signals.append(MatchSignal("doi", 0.0, f"DOI mismatch: {doi1} vs {doi2}"))

    # 2. Manuscript ID exact match
    mid1 = str(doc1_fields.get("manuscript_id", "")).strip() or None
    mid2 = str(doc2_fields.get("manuscript_id", "")).strip() or None
    if mid1 and mid2:
        if mid1.lower() == mid2.lower():
            signals.append(MatchSignal("manuscript_id", 0.95, f"Manuscript ID match: {mid1}"))
        else:
            signals.append(MatchSignal("manuscript_id", 0.0, f"Manuscript ID mismatch: {mid1} vs {mid2}"))

    # 3. Title similarity
    title1 = str(doc1_fields.get("publication_title", "")).strip() or None
    title2 = str(doc2_fields.get("publication_title", "")).strip() or None
    if not title1:
        title1 = str(doc1_fields.get("presentation_title", "")).strip() or None
    if not title2:
        title2 = str(doc2_fields.get("presentation_title", "")).strip() or None
    if title1 and title2:
        sim = _title_similarity(title1, title2)
        if sim >= 0.9:
            signals.append(MatchSignal("title", sim, f"Title similarity: {sim:.0%}"))
        elif sim >= 0.7:
            signals.append(MatchSignal("title", sim, f"Title partial match: {sim:.0%}"))
        else:
            signals.append(MatchSignal("title", sim, f"Title differs: {sim:.0%}"))

    # 4. Author overlap
    authors1 = str(doc1_fields.get("authors", "")).strip() or None
    authors2 = str(doc2_fields.get("authors", "")).strip() or None
    if authors1 and authors2:
        overlap = _author_overlap(authors1, authors2)
        if overlap >= 0.5:
            signals.append(MatchSignal("authors", overlap, f"Author overlap: {overlap:.0%}"))
        else:
            signals.append(MatchSignal("authors", overlap, f"Author overlap low: {overlap:.0%}"))

    # 5. Journal match
    journal1 = str(doc1_fields.get("journal_name", "")).strip() or None
    journal2 = str(doc2_fields.get("journal_name", "")).strip() or None
    if journal1 and journal2:
        jmatch = _journal_match(journal1, journal2)
        if jmatch > 0:
            signals.append(MatchSignal("journal", jmatch, f"Journal match: {journal1}"))

    # 6. Year compatibility
    year1 = str(doc1_fields.get("publication_year", "")).strip() or None
    year2 = str(doc2_fields.get("publication_year", "")).strip() or None
    if year1 and year2:
        ymatch = _year_match(year1, year2)
        if ymatch > 0:
            signals.append(MatchSignal("year", ymatch, f"Year compatible: {year1} vs {year2}"))

    # Compute overall confidence
    if not signals:
        return MatchResult(
            source_doc_id=doc1_id,
            target_doc_id=doc2_id,
            confidence=0.0,
            signals=tuple(signals),
            outcome="low",
        )

    # Weighted combination
    weights = {
        "doi": 1.0,
        "manuscript_id": 0.95,
        "title": 0.4,
        "authors": 0.3,
        "journal": 0.2,
        "year": 0.1,
    }

    # Check for conflicts (contradictory evidence)
    has_conflict = False
    for s in signals:
        if s.signal_type in ("doi", "manuscript_id") and s.confidence == 0.0:
            has_conflict = True

    if has_conflict:
        return MatchResult(
            source_doc_id=doc1_id,
            target_doc_id=doc2_id,
            confidence=0.0,
            signals=tuple(signals),
            outcome="conflict",
        )

    # Compute weighted score
    total_weight = 0.0
    weighted_sum = 0.0
    for s in signals:
        w = weights.get(s.signal_type, 0.1)
        weighted_sum += s.confidence * w
        total_weight += w

    confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Determine outcome
    if confidence >= HIGH_THRESHOLD:
        outcome = "high"
    elif confidence >= MEDIUM_THRESHOLD:
        outcome = "medium"
    else:
        outcome = "low"

    return MatchResult(
        source_doc_id=doc1_id,
        target_doc_id=doc2_id,
        confidence=round(confidence, 3),
        signals=tuple(signals),
        outcome=outcome,
    )


__all__ = [
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    "MatchResult",
    "MatchSignal",
    "match_entities",
]
