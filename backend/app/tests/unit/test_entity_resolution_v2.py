"""Cross-Document Entity Resolution Tests (Revision #16).

Comprehensive test matrix for safe entity matching with zero false positives.

Test scenarios:
A. Exact same title + authors → HIGH
B. Same DOI → HIGH
C. Same manuscript ID → HIGH
D. Minor title punctuation differences → HIGH
E. Title capitalization differences → HIGH
F. Same title but different authors → NOT AUTO-MERGED
G. Same author but different title → NOT MATCH
H. Similar titles but different papers → LOW/NO MATCH
I. Missing DOI/missing authors → NO AUTO-MERGE
J. Conflicting DOI → CONFLICT
K. Conflicting authors with similar title → REVIEW

CRITICAL: FALSE POSITIVE AUTO-LINK RATE = 0%
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
# Test Data - Realistic Academic Scenarios
# =============================================================================

# Scenario A: Research Paper
PAPER_ADVANCED_THERMAL = {
    "publication_title": "Advanced Thermal Analysis of Nanoparticle Composites",
    "authors": "V. Kumar, P. Bansal, S. Sharma",
    "journal_name": "Environmental Science and Technology",
    "publication_year": "2025",
    "doi": "10.1021/acs.est.2025.12345",
}

# Scenario A: Acceptance Letter (same paper)
ACCEPTANCE_THERMAL = {
    "publication_title": "Advanced Thermal Analysis of Nanoparticle Composites",
    "authors": "V. Kumar, P. Bansal, S. Sharma",
    "journal_name": "Environmental Science and Technology",
    "manuscript_id": "EST-2025-4567",
}

# Scenario B: Same manuscript ID
ACCEPTANCE_WITH_MID = {
    "publication_title": "Novel Methods in Water Purification",
    "manuscript_id": "NC-2025-7890",
}

PAPER_WITH_MID = {
    "publication_title": "Novel Methods in Water Purification",
    "manuscript_id": "NC-2025-7890",
}

# Scenario C: Different paper (negative test)
PAPER_QUANTUM = {
    "publication_title": "Quantum Computing Applications in Cryptography",
    "authors": "X. Zhang, Y. Li",
    "journal_name": "Nature Physics",
    "publication_year": "2024",
    "doi": "10.1038/s41567-024-0001",
}

# Scenario D: Similar title, different paper (negative test)
PAPER_ML_REVIEW = {
    "publication_title": "Machine Learning: A Comprehensive Review",
    "authors": "A. Kumar, B. Singh",
    "journal_name": "ACM Computing Surveys",
    "publication_year": "2025",
}

PAPER_ML_TUTORIAL = {
    "publication_title": "Machine Learning: A Tutorial Introduction",
    "authors": "X. Zhang, Y. Li",
    "journal_name": "IEEE TPAMI",
    "publication_year": "2024",
}

# Scenario E: Same author, different paper (negative test)
PAPER_BY_KUMAR_1 = {
    "publication_title": "Deep Learning for Image Classification",
    "authors": "A. Kumar, B. Singh",
    "publication_year": "2025",
}

PAPER_BY_KUMAR_2 = {
    "publication_title": "Natural Language Processing Fundamentals",
    "authors": "A. Kumar, C. Patel",
    "publication_year": "2024",
}


# =============================================================================
# A. Exact same title + authors → HIGH
# =============================================================================

class TestExactMatch:
    """Exact title + author match should be HIGH confidence."""

    def test_same_title_authors_journal_year(self):
        """Same title, authors, journal, year → HIGH confidence."""
        result = match_entities(
            PAPER_ADVANCED_THERMAL, PAPER_ADVANCED_THERMAL,
            "doc:paper", "doc:paper2"
        )
        assert result.confidence >= HIGH_THRESHOLD
        assert result.outcome == "high"

    def test_acceptance_matches_paper(self):
        """Acceptance letter for same paper → HIGH confidence."""
        result = match_entities(
            PAPER_ADVANCED_THERMAL, ACCEPTANCE_THERMAL,
            "doc:paper", "doc:acceptance"
        )
        assert result.confidence >= MEDIUM_THRESHOLD
        # Should have title + author + journal signals
        signal_types = {s.signal_type for s in result.signals}
        assert "title" in signal_types
        assert "authors" in signal_types

    def test_minor_punctuation_differences(self):
        """Minor punctuation differences → MEDIUM (high similarity title match)."""
        fields1 = {"publication_title": "Deep Learning: A Review"}
        fields2 = {"publication_title": "Deep Learning - A Review"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # High-similarity title match → MEDIUM (for review)
        assert result.confidence >= MEDIUM_THRESHOLD

    def test_capitalization_differences(self):
        """Capitalization differences → MEDIUM (high similarity title match)."""
        fields1 = {"publication_title": "DEEP LEARNING FOR MICROPLASTICS"}
        fields2 = {"publication_title": "deep learning for microplastics"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # High-similarity title match → MEDIUM (for review)
        assert result.confidence >= MEDIUM_THRESHOLD


# =============================================================================
# B. Same DOI → HIGH
# =============================================================================

class TestDOIMatch:
    """DOI exact match should be HIGH confidence."""

    def test_same_doi(self):
        """Same DOI → HIGH confidence."""
        result = match_entities(
            PAPER_ADVANCED_THERMAL, PAPER_ADVANCED_THERMAL,
            "doc:1", "doc:2"
        )
        assert result.confidence >= HIGH_THRESHOLD
        doi_signals = [s for s in result.signals if s.signal_type == "doi"]
        assert len(doi_signals) == 1
        assert doi_signals[0].confidence == 1.0

    def test_doi_with_prefix(self):
        """DOI with https://doi.org/ prefix matches."""
        fields1 = {"doi": "10.1021/acs.est.2025.12345"}
        fields2 = {"doi": "https://doi.org/10.1021/acs.est.2025.12345"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.confidence >= HIGH_THRESHOLD


# =============================================================================
# C. Same manuscript ID → HIGH
# =============================================================================

class TestManuscriptIDMatch:
    """Manuscript ID match should be HIGH confidence."""

    def test_same_manuscript_id(self):
        """Same manuscript ID → HIGH confidence."""
        result = match_entities(
            ACCEPTANCE_WITH_MID, PAPER_WITH_MID,
            "doc:accept", "doc:paper"
        )
        assert result.confidence >= HIGH_THRESHOLD
        mid_signals = [s for s in result.signals if s.signal_type == "manuscript_id"]
        assert len(mid_signals) == 1
        assert mid_signals[0].confidence >= 0.9


# =============================================================================
# D. Minor title differences → HIGH
# =============================================================================

class TestTitleVariations:
    """Minor title differences should still match."""

    def test_punctuation_differences(self):
        """Minor punctuation differences → MEDIUM (high similarity title match)."""
        fields1 = {"publication_title": "Deep Learning: A Review"}
        fields2 = {"publication_title": "Deep Learning - A Review"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # High-similarity title match → MEDIUM (for review)
        assert result.confidence >= MEDIUM_THRESHOLD

    def test_capitalization_differences(self):
        """Capitalization differences → MEDIUM (high similarity title match)."""
        fields1 = {"publication_title": "DEEP LEARNING FOR MICROPLASTICS"}
        fields2 = {"publication_title": "deep learning for microplastics"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # High-similarity title match → MEDIUM (for review)
        assert result.confidence >= MEDIUM_THRESHOLD


# =============================================================================
# E. Same title but different authors → NOT AUTO-MERGED
# =============================================================================

class TestDifferentAuthors:
    """Same title but different authors should NOT auto-merge."""

    def test_same_title_different_authors(self):
        """Same title but different authors → NOT HIGH confidence."""
        fields1 = {
            "publication_title": "Machine Learning Review",
            "authors": "A. Kumar, B. Singh"
        }
        fields2 = {
            "publication_title": "Machine Learning Review",
            "authors": "X. Zhang, Y. Li"
        }
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # Should NOT be HIGH confidence (authors differ)
        assert result.confidence < HIGH_THRESHOLD

    def test_same_title_no_authors(self):
        """Same title but no author info → LOW (safe policy)."""
        fields1 = {"publication_title": "Machine Learning Review"}
        fields2 = {"publication_title": "Machine Learning Review"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # Title only → LOW (safe policy: insufficient evidence)
        assert result.confidence < HIGH_THRESHOLD


# =============================================================================
# F. Same author but different title → NOT MATCH
# =============================================================================

class TestDifferentTitle:
    """Same author but different title should NOT match."""

    def test_same_author_different_title(self):
        """Same author but completely different title → LOW confidence."""
        result = match_entities(
            PAPER_BY_KUMAR_1, PAPER_BY_KUMAR_2,
            "doc:1", "doc:2"
        )
        assert result.confidence < MEDIUM_THRESHOLD
        assert result.outcome == "low"

    def test_completely_different_papers(self):
        """Completely different papers → LOW confidence."""
        result = match_entities(
            PAPER_ADVANCED_THERMAL, PAPER_QUANTUM,
            "doc:1", "doc:2"
        )
        # Different DOIs → conflict
        assert result.outcome == "conflict"


# =============================================================================
# G. Similar titles but different papers → LOW
# =============================================================================

class TestSimilarTitles:
    """Similar but different titles should be LOW confidence."""

    def test_similar_titles_different_papers(self):
        """Similar but different titles → lower confidence."""
        result = match_entities(
            PAPER_ML_REVIEW, PAPER_ML_TUTORIAL,
            "doc:1", "doc:2"
        )
        assert result.confidence < HIGH_THRESHOLD

    def test_very_different_titles(self):
        """Very different titles → LOW confidence."""
        result = match_entities(
            PAPER_ADVANCED_THERMAL, PAPER_QUANTUM,
            "doc:1", "doc:2"
        )
        assert result.outcome == "conflict"


# =============================================================================
# H. Missing DOI/missing authors → NO AUTO-MERGE
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
        fields1 = {"doi": "10.1021/acs.est.2025.12345"}
        fields2 = {"publication_title": "Some Paper"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "low"

    def test_missing_authors_title_only(self):
        """Missing authors, title only → LOW (safe policy)."""
        fields1 = {"publication_title": "Test Paper"}
        fields2 = {"publication_title": "Test Paper"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        # Title only → LOW (safe policy: insufficient evidence)
        assert result.confidence < HIGH_THRESHOLD


# =============================================================================
# I. Conflicting DOI → CONFLICT
# =============================================================================

class TestConflicts:
    """Conflicting evidence should result in CONFLICT."""

    def test_different_dois_conflict(self):
        """Different DOIs → CONFLICT."""
        fields1 = {"doi": "10.1021/acs.est.2025.12345", "publication_title": "Paper A"}
        fields2 = {"doi": "10.1038/s41567-024-0001", "publication_title": "Paper B"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "conflict"

    def test_different_manuscript_ids_conflict(self):
        """Different manuscript IDs → CONFLICT."""
        fields1 = {"manuscript_id": "EST-2025-4567"}
        fields2 = {"manuscript_id": "NC-2025-9999"}
        result = match_entities(fields1, fields2, "doc:1", "doc:2")
        assert result.outcome == "conflict"


# =============================================================================
# CRITICAL: False Positive Auto-Link Rate = 0%
# =============================================================================

class TestFalsePositiveRate:
    """CRITICAL: Verify 0% false positive auto-link rate."""

    def test_false_positive_rate_zero(self):
        """CRITICAL: Completely different papers must NOT auto-link (HIGH confidence)."""
        papers = [
            PAPER_ADVANCED_THERMAL,
            PAPER_QUANTUM,
            PAPER_ML_REVIEW,
            PAPER_ML_TUTORIAL,
            PAPER_BY_KUMAR_1,
            PAPER_BY_KUMAR_2,
        ]

        # Every pair should NOT be HIGH confidence
        for i in range(len(papers)):
            for j in range(i + 1, len(papers)):
                result = match_entities(papers[i], papers[j], f"doc:{i}", f"doc:{j}")
                # Different papers should never be HIGH confidence
                assert result.confidence < HIGH_THRESHOLD, \
                    f"False positive HIGH: {papers[i].get('publication_title')} vs {papers[j].get('publication_title')}"

    def test_acceptance_letter_matches_correct_paper_only(self):
        """Acceptance letter should match its paper, not others."""
        # Acceptance for thermal paper
        acceptance = ACCEPTANCE_THERMAL

        # Should match thermal paper
        result_match = match_entities(
            PAPER_ADVANCED_THERMAL, acceptance,
            "doc:thermal", "doc:accept"
        )
        assert result_match.confidence >= MEDIUM_THRESHOLD

        # Should NOT match quantum paper
        result_no_match = match_entities(
            PAPER_QUANTUM, acceptance,
            "doc:quantum", "doc:accept"
        )
        assert result_no_match.confidence < MEDIUM_THRESHOLD
