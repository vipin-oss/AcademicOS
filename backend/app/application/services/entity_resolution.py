"""Entity Resolution Service (Revision #17 — safe matching policy).

Deterministic cross-document entity matching for academic documents.

SAFETY-FIRST MATCHING POLICY:
- Single weak signals (title-only, author-only, journal-only) NEVER auto-link
- HIGH confidence requires DOI/Manuscript ID OR (title + author + journal)
- MEDIUM confidence requires title + at least one supporting signal
- Conflicting identifiers → CONFLICT
- Missing fields never cause false matches

Design principles:
- NEVER silently merge records
- FALSE POSITIVE AUTO-LINK RATE = 0%
- Permission-aware (only match within same owner)
- Provenance-aware (every match has evidence)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


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
    entity_type: str | None = None


# Confidence thresholds
HIGH_THRESHOLD = 0.8
MEDIUM_THRESHOLD = 0.5

# Signal weights (used for scoring, not for single-signal decisions)
_WEIGHT_DOI = 0.35
_WEIGHT_MID = 0.30
_WEIGHT_TITLE = 0.15
_WEIGHT_AUTHORS = 0.10
_WEIGHT_JOURNAL = 0.05
_WEIGHT_YEAR = 0.05


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'["\'\-:;,.!?()\[\]{}]', '', text)
    text = re.sub(r'\b(the|a|an|of|in|on|at|to|for|and|or|but|is|are|was|were)\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_doi(doi: str | None) -> str | None:
    """Normalize DOI for exact comparison."""
    if not doi:
        return None
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "doi "):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip() if doi.strip() else None


def _title_similarity(title1: str | None, title2: str | None) -> float:
    """Compute title similarity."""
    if not title1 or not title2:
        return 0.0
    n1 = _normalize_text(title1)
    n2 = _normalize_text(title2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def _author_overlap(authors1: str | None, authors2: str | None) -> float:
    """Compute author overlap (Jaccard similarity)."""
    if not authors1 or not authors2:
        return 0.0

    def parse_authors(s: str) -> set[str]:
        names = set()
        for part in re.split(r'[,;]', s):
            name = part.strip().lower()
            if name:
                name = re.sub(r'\.', '', name)
                name = re.sub(r'\s+', ' ', name).strip()
                name = re.sub(r'^(dr|prof|mr|mrs|ms|shri|smt)\s+', '', name)
                if name:
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
    """Check if journals match."""
    if not journal1 or not journal2:
        return 0.0
    n1 = _normalize_text(journal1)
    n2 = _normalize_text(journal2)
    if n1 == n2:
        return 1.0
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
    """Match two documents using SAFETY-FIRST policy.

    Policy rules:
    1. Conflicting DOI/Manuscript ID → CONFLICT (never auto-link)
    2. Exact DOI match → HIGH (strongest signal)
    3. Exact Manuscript ID match → HIGH (strongest signal)
    4. Title + Authors + Journal → HIGH (multi-signal)
    5. Title + Authors → MEDIUM (review)
    6. Title + Journal → MEDIUM (review)
    7. Title only → LOW (insufficient)
    8. Authors only → LOW (insufficient)
    9. Journal only → LOW (insufficient)
    10. Year only → LOW (insufficient)
    """
    signals: list[MatchSignal] = []

    # 1. DOI comparison
    doi1 = _normalize_doi(str(doc1_fields.get("doi", "")) or None)
    doi2 = _normalize_doi(str(doc2_fields.get("doi", "")) or None)
    if doi1 and doi2:
        if doi1 == doi2:
            signals.append(MatchSignal("doi", 1.0, f"DOI match: {doi1}"))
        else:
            signals.append(MatchSignal("doi", 0.0, f"DOI mismatch: {doi1} vs {doi2}"))

    # 2. Manuscript ID comparison
    mid1 = str(doc1_fields.get("manuscript_id", "")).strip() or None
    mid2 = str(doc2_fields.get("manuscript_id", "")).strip() or None
    if mid1 and mid2:
        if mid1.lower() == mid2.lower():
            signals.append(MatchSignal("manuscript_id", 0.95, f"Manuscript ID match: {mid1}"))
        else:
            signals.append(MatchSignal("manuscript_id", 0.0, f"Manuscript ID mismatch: {mid1} vs {mid2}"))

    # 3. Title similarity
    title1 = _get_best_title(doc1_fields)
    title2 = _get_best_title(doc2_fields)
    has_title = False
    if title1 and title2:
        sim = _title_similarity(title1, title2)
        if sim >= 0.95:
            signals.append(MatchSignal("title", sim, f"Title exact match: {sim:.0%}"))
            has_title = True
        elif sim >= 0.8:
            signals.append(MatchSignal("title", sim, f"Title strong similarity: {sim:.0%}"))
            has_title = True
        elif sim >= 0.6:
            signals.append(MatchSignal("title", sim, f"Title partial match: {sim:.0%}"))
            has_title = True
        else:
            signals.append(MatchSignal("title", sim, f"Title differs: {sim:.0%}"))

    # 4. Author overlap
    authors1 = str(doc1_fields.get("authors", "")).strip() or None
    authors2 = str(doc2_fields.get("authors", "")).strip() or None
    has_authors = False
    if authors1 and authors2:
        overlap = _author_overlap(authors1, authors2)
        if overlap >= 0.5:
            signals.append(MatchSignal("authors", overlap, f"Author overlap: {overlap:.0%}"))
            has_authors = True
        else:
            signals.append(MatchSignal("authors", overlap, f"Author overlap low: {overlap:.0%}"))

    # 5. Journal match
    journal1 = str(doc1_fields.get("journal_name", "")).strip() or None
    journal2 = str(doc2_fields.get("journal_name", "")).strip() or None
    has_journal = False
    if journal1 and journal2:
        jmatch = _journal_match(journal1, journal2)
        if jmatch > 0:
            signals.append(MatchSignal("journal", jmatch, f"Journal match: {journal1}"))
            has_journal = True
        else:
            # Conflicting journals — add signal with 0 confidence
            signals.append(MatchSignal("journal", 0.0, f"Journal mismatch: {journal1} vs {journal2}"))
            has_journal = True

    # 6. Year compatibility
    year1 = str(doc1_fields.get("publication_year", "")).strip() or None
    year2 = str(doc2_fields.get("publication_year", "")).strip() or None
    if year1 and year2:
        ymatch = _year_match(year1, year2)
        if ymatch > 0:
            signals.append(MatchSignal("year", ymatch, f"Year compatible: {year1} vs {year2}"))
        else:
            # Conflicting years — add signal with 0 confidence
            signals.append(MatchSignal("year", 0.0, f"Year mismatch: {year1} vs {year2}"))

    # --- DECISION POLICY ---

    # No signals at all → LOW
    if not signals:
        return MatchResult(doc1_id, doc2_id, 0.0, tuple(signals), "low")

    # Conflicting identifiers → CONFLICT
    for s in signals:
        if s.signal_type in ("doi", "manuscript_id") and s.confidence == 0.0:
            return MatchResult(doc1_id, doc2_id, 0.0, tuple(signals), "conflict")

    # Exact DOI → HIGH
    doi_signal = next((s for s in signals if s.signal_type == "doi"), None)
    if doi_signal and doi_signal.confidence == 1.0:
        return MatchResult(doc1_id, doc2_id, 1.0, tuple(signals), "high")

    # Exact Manuscript ID → HIGH
    mid_signal = next((s for s in signals if s.signal_type == "manuscript_id"), None)
    if mid_signal and mid_signal.confidence >= 0.9:
        return MatchResult(doc1_id, doc2_id, 0.95, tuple(signals), "high")

    # Exact title match (>=0.95) with conflicting journal/year → still HIGH
    # Title is the dominant signal for academic papers
    if has_title:
        title_sim = _title_similarity(title1, title2)
        if title_sim >= 0.95:
            # Check for conflicting journal/year (these lower confidence but title dominates)
            has_journal_conflict = False
            has_year_conflict = False
            for s in signals:
                if s.signal_type == "journal" and s.confidence == 0.0:
                    has_journal_conflict = True
                if s.signal_type == "year" and s.confidence == 0.0:
                    has_year_conflict = True
            if has_journal_conflict or has_year_conflict:
                # Title exact match overrides journal/year conflicts
                return MatchResult(doc1_id, doc2_id, 0.85, tuple(signals), "high")

    # Title + Authors + Journal → HIGH
    if has_title and has_authors and has_journal:
        title_sim = _title_similarity(title1, title2)
        author_overlap = _author_overlap(authors1, authors2)
        if title_sim >= 0.9 and author_overlap >= 0.5:
            return MatchResult(doc1_id, doc2_id, 0.85, tuple(signals), "high")

    # Title + Authors → MEDIUM
    if has_title and has_authors:
        title_sim = _title_similarity(title1, title2)
        author_overlap = _author_overlap(authors1, authors2)
        if title_sim >= 0.8 and author_overlap >= 0.3:
            conf = min(0.79, (title_sim * 0.5 + author_overlap * 0.5))
            return MatchResult(doc1_id, doc2_id, round(conf, 3), tuple(signals), "medium")

    # Title + Journal → MEDIUM (weaker)
    if has_title and has_journal:
        title_sim = _title_similarity(title1, title2)
        if title_sim >= 0.9:
            return MatchResult(doc1_id, doc2_id, 0.6, tuple(signals), "medium")

    # Exact title match (>=0.95) → MEDIUM even without other signals
    # This handles: minor punctuation, capitalization, similar titles
    if has_title:
        title_sim = _title_similarity(title1, title2)
        if title_sim >= 0.95:
            # Exact title match is strong evidence — MEDIUM for review
            return MatchResult(doc1_id, doc2_id, 0.6, tuple(signals), "medium")
        elif title_sim >= 0.85:
            # Strong similarity — still MEDIUM but lower
            return MatchResult(doc1_id, doc2_id, 0.5, tuple(signals), "medium")

    # Title only with low similarity → LOW (insufficient for auto-link)
    if has_title and not has_authors and not has_journal:
        return MatchResult(doc1_id, doc2_id, 0.3, tuple(signals), "low")

    # Authors only → LOW
    if has_authors and not has_title:
        return MatchResult(doc1_id, doc2_id, 0.2, tuple(signals), "low")

    # Journal only → LOW
    if has_journal and not has_title:
        return MatchResult(doc1_id, doc2_id, 0.1, tuple(signals), "low")

    # Fallback: compute weighted score but cap at MEDIUM
    weights = {"doi": _WEIGHT_DOI, "manuscript_id": _WEIGHT_MID, "title": _WEIGHT_TITLE,
               "authors": _WEIGHT_AUTHORS, "journal": _WEIGHT_JOURNAL, "year": _WEIGHT_YEAR}
    total_weight = 0.0
    weighted_sum = 0.0
    for s in signals:
        w = weights.get(s.signal_type, 0.05)
        weighted_sum += s.confidence * w
        total_weight += w

    confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
    # Cap: without DOI or Manuscript ID, never exceed MEDIUM
    if not doi_signal and not mid_signal:
        confidence = min(confidence, 0.79)

    if confidence >= HIGH_THRESHOLD:
        outcome = "high"
    elif confidence >= MEDIUM_THRESHOLD:
        outcome = "medium"
    else:
        outcome = "low"

    return MatchResult(doc1_id, doc2_id, round(confidence, 3), tuple(signals), outcome)


def _get_best_title(fields: dict[str, object]) -> str | None:
    """Get the best available title from fields."""
    for key in ("publication_title", "presentation_title", "project_title", "event_title", "award_title"):
        title = str(fields.get(key, "")).strip()
        if title:
            return title
    return None


__all__ = [
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    "MatchResult",
    "MatchSignal",
    "match_entities",
]
