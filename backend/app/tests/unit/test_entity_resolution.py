"""Entity Resolution Tests (Revision #15).

Tests deterministic cross-document entity matching with explicit
false-positive verification.
"""

from __future__ import annotations

import pytest

from app.application.services.entity_resolution import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    MatchResult,
    match_entities,
)

# =============================================================================
# Test Data
# =============================================================================

PAPER_FIELDS = {
    "publication_title": "Deep Learning for Microplastic Detection in River Systems",
    "authors": "A. Kumar, B. Singh, C. Patel",
    "journal_name": "Environmental Science and Technology",
    "publication_year": "2025",
    "doi": "10.1021/acs.est.2025.0042",
}

ACCEPTANCE_FIELDS = {
    "publication_title": "Deep Learning for Microplastic Detection in River Systems",
    "authors": "A. Kumar, B. Singh, C. Patel",
    "journal_name": "Environmental Science and Technology",
    "manuscript_id": "EST-2025-4567",
}

DIFFERENT_PAPER_FIELDS = {
    "publication_title": "Quantum Computing Applications in Cryptography",
    "authors": "X. Zhang, Y. Li",
    "journal_name": "Nature Physics",
    "publication_year": "2024",
    "doi": "10.1038/s41567-024-0001",
}

SIMILAR_TITLE_FIELDS = {
    "publication_title": "Deep Learning for Microplastic Detection in Rivers",
    "authors": "A. Kumar, B. Singh",
    "journal_name": "Environmental Science and Technology",
    "publication_year": "2025",
}


# =============================================================================
# A. Exact same title + authors → HIGH
# =============================================================================

class TestExactMatch:
    """Exact title + author match should be HIGH confidence."""

    def test_same_title_authors_journal(self):
        """Same title, authors, journal → HIGH confidence."""
        result = match_entities(PAPER_FIELDS, ACCEPTANCE_FIELDS, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD
        assert result.outcome == "high"

    def test_same_title_different_format(self):
        """Same title with minor formatting differences → HIGH."""
        fields2 = dict(PAPER_FIELDS)
        fields2["publication_title"] = "Deep Learning for Microplastic Detection in River Systems."
        result = match_entities(PAPER_FIELDS, fields2, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD


# =============================================================================
# B. Same DOI → HIGH
# =============================================================================

class TestDOIMatch:
    """DOI exact match should be HIGH confidence."""

    def test_same_doi(self):
        """Same DOI → HIGH confidence."""
        result = match_entities(PAPER_FIELDS, PAPER_FIELDS, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD
        assert result.outcome == "high"

    def test_doi_with_prefix(self):
        """DOI with https://doi.org/ prefix matches."""
        fields2 = dict(PAPER_FIELDS)
        fields2["doi"] = "https://doi.org/10.1021/acs.est.2025.0042"
        result = match_entities(PAPER_FIELDS, fields2, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD


# =============================================================================
# C. Same manuscript ID → HIGH
# =============================================================================

class TestManuscriptIDMatch:
    """Manuscript ID match should be HIGH confidence."""

    def test_same_manuscript_id(self):
        """Same manuscript ID → HIGH confidence."""
        fields1 = {"manuscript_id": "EST-2025-4567", "publication_title": "Test Paper"}
        fields2 = {"manuscript_id": "EST-2025-4567", "publication_title": "Test Paper"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD


# =============================================================================
# D. Minor title differences → MEDIUM-HIGH
# =============================================================================

class TestTitleVariations:
    """Minor title differences should still match."""

    def test_punctuation_differences(self):
        """Minor punctuation differences → still matches."""
        fields1 = {"publication_title": "Deep Learning: A Review"}
        fields2 = {"publication_title": "Deep Learning - A Review"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.confidence >= MEDIUM_THRESHOLD

    def test_capitalization_differences(self):
        """Capitalization differences → still matches."""
        fields1 = {"publication_title": "DEEP LEARNING FOR MICROPLASTICS"}
        fields2 = {"publication_title": "deep learning for microplastics"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.confidence >= MEDIUM_THRESHOLD


# =============================================================================
# E. Different papers → LOW (false positive check)
# =============================================================================

class TestFalsePositivePrevention:
    """CRITICAL: Different papers must NOT match."""

    def test_completely_different_papers(self):
        """Completely different papers with different DOIs → CONFLICT."""
        result = match_entities(PAPER_FIELDS, DIFFERENT_PAPER_FIELDS, "doc:1", "doc:2")
        # Different DOIs is a conflict
        assert result.outcome == "conflict"

    def test_different_dois_conflict(self):
        """Different DOIs → CONFLICT."""
        fields1 = {"doi": "10.1021/acs.est.2025.0042", "publication_title": "Paper A"}
        fields2 = {"doi": "10.1038/s41567-024-0001", "publication_title": "Paper B"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "conflict"

    def test_different_manuscript_ids_conflict(self):
        """Different manuscript IDs → CONFLICT."""
        fields1 = {"manuscript_id": "EST-2025-4567"}
        fields2 = {"manuscript_id": "NC-2025-9999"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "conflict"

    def test_same_title_different_authors_low(self):
        """Same title but different authors → lower confidence."""
        fields1 = {"publication_title": "Machine Learning Review", "authors": "A. Kumar"}
        fields2 = {"publication_title": "Machine Learning Review", "authors": "X. Zhang"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # Title matches but authors don't — medium confidence
        assert result.confidence < HIGH_THRESHOLD


# =============================================================================
# F. Missing fields → safe handling
# =============================================================================

class TestMissingFields:
    """Missing fields should not cause false matches."""

    def test_no_fields_no_match(self):
        """Empty fields → LOW confidence."""
        result = match_entities({}, {}, "doc:1", "doc:2")
        assert result.confidence == 0.0
        assert result.outcome == "low"

    def test_one_doi_one_missing(self):
        """One DOI, one missing → no signal, no false match."""
        fields1 = {"doi": "10.1021/acs.est.2025.0042"}
        fields2 = {"publication_title": "Some Paper"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "low"


# =============================================================================
# G. Author overlap
# =============================================================================

class TestAuthorMatching:
    """Author overlap detection."""

    def test_exact_author_match(self):
        """Exact author list → high overlap."""
        fields1 = {"authors": "A. Kumar, B. Singh", "publication_title": "Test"}
        fields2 = {"authors": "A. Kumar, B. Singh", "publication_title": "Test"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # Should have author signal with high overlap
        author_signals = [s for s in result.signals if s.signal_type == "authors"]
        assert len(author_signals) > 0
        assert author_signals[0].confidence >= 0.9

    def test_partial_author_overlap(self):
        """Partial author overlap → partial score."""
        fields1 = {"authors": "A. Kumar, B. Singh, C. Patel", "publication_title": "Test"}
        fields2 = {"authors": "A. Kumar, X. Zhang", "publication_title": "Test"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        author_signals = [s for s in result.signals if s.signal_type == "authors"]
        assert len(author_signals) > 0
        assert 0 < author_signals[0].confidence < 1.0


# =============================================================================
# H. Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge cases in entity matching."""

    def test_none_values_handled(self):
        """None values should not cause errors."""
        fields1 = {"publication_title": None, "doi": None}
        fields2 = {"publication_title": "Test", "doi": "10.1234/test"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result is not None

    def test_empty_strings_handled(self):
        """Empty strings should not cause false matches."""
        fields1 = {"publication_title": "", "doi": ""}
        fields2 = {"publication_title": "", "doi": ""}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.confidence == 0.0
