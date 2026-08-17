"""Entity Resolution — Safe Matching Policy Tests (Revision #17).

CRITICAL: FALSE POSITIVE AUTO-LINK RATE = 0%

Policy rules:
1. Conflicting DOI/Manuscript ID → CONFLICT
2. Exact DOI → HIGH
3. Exact Manuscript ID → HIGH
4. Title + Authors + Journal → HIGH
5. Title + Authors → MEDIUM
6. Title + Journal → MEDIUM
7. Title only → LOW (NEVER auto-link)
8. Authors only → LOW (NEVER link)
9. Journal only → LOW (NEVER link)
10. Year only → LOW (NEVER link)
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
# Positive Cases
# =============================================================================

class TestPositiveMatches:
    """Cases where documents SHOULD match."""

    def test_exact_doi_match(self):
        """Same DOI → HIGH confidence."""
        f1 = {"doi": "10.1021/acs.est.2025.0042"}
        f2 = {"doi": "10.1021/acs.est.2025.0042"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "high"
        assert r.confidence >= HIGH_THRESHOLD

    def test_doi_with_prefix(self):
        """DOI with https://doi.org/ prefix → HIGH."""
        f1 = {"doi": "10.1021/acs.est.2025.0042"}
        f2 = {"doi": "https://doi.org/10.1021/acs.est.2025.0042"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "high"

    def test_manuscript_id_match(self):
        """Same manuscript ID → HIGH confidence."""
        f1 = {"manuscript_id": "EST-2025-4567"}
        f2 = {"manuscript_id": "EST-2025-4567"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "high"

    def test_title_authors_journal(self):
        """Title + Authors + Journal → HIGH."""
        f1 = {
            "publication_title": "Deep Learning for Microplastic Detection",
            "authors": "A. Kumar, B. Singh",
            "journal_name": "Environmental Science",
        }
        f2 = {
            "publication_title": "Deep Learning for Microplastic Detection",
            "authors": "A. Kumar, B. Singh",
            "journal_name": "Environmental Science",
        }
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "high"

    def test_title_authors(self):
        """Title + Authors → MEDIUM."""
        f1 = {
            "publication_title": "Deep Learning for Microplastics",
            "authors": "A. Kumar, B. Singh",
        }
        f2 = {
            "publication_title": "Deep Learning for Microplastics",
            "authors": "A. Kumar, B. Singh",
        }
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "medium"

    def test_title_journal(self):
        """Title + Journal → MEDIUM."""
        f1 = {
            "publication_title": "Novel Methods in Water Purification",
            "journal_name": "Nature Chemistry",
        }
        f2 = {
            "publication_title": "Novel Methods in Water Purification",
            "journal_name": "Nature Chemistry",
        }
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "medium"

    def test_acceptance_letter_matches_paper(self):
        """Acceptance letter + paper with same title/authors → MEDIUM+."""
        paper = {
            "publication_title": "Advanced Thermal Analysis",
            "authors": "V. Kumar, P. Bansal",
            "journal_name": "EST",
            "doi": "10.1021/acs.est.2025.0042",
        }
        accept = {
            "publication_title": "Advanced Thermal Analysis",
            "authors": "V. Kumar, P. Bansal",
            "journal_name": "EST",
            "manuscript_id": "EST-2025-4567",
        }
        r = match_entities(paper, accept, "d1", "d2")
        assert r.outcome in ("high", "medium")

    def test_minor_punctuation(self):
        """Minor punctuation differences → still matches."""
        f1 = {"publication_title": "Deep Learning: A Review", "authors": "A. Kumar"}
        f2 = {"publication_title": "Deep Learning - A Review", "authors": "A. Kumar"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome in ("high", "medium")

    def test_capitalization(self):
        """Capitalization differences → still matches."""
        f1 = {"publication_title": "DEEP LEARNING", "authors": "A. Kumar", "journal_name": "Nature"}
        f2 = {"publication_title": "deep learning", "authors": "a kumar", "journal_name": "nature"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome in ("high", "medium")


# =============================================================================
# Negative Cases (CRITICAL: 0% false positive rate)
# =============================================================================

class TestNegativeMatches:
    """Cases where documents should NOT match (HIGH)."""

    def test_title_only_not_high(self):
        """Title only → NEVER HIGH (insufficient evidence)."""
        f1 = {"publication_title": "Machine Learning Review"}
        f2 = {"publication_title": "Machine Learning Review"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD, "Title only should NOT be HIGH"

    def test_authors_only_not_high(self):
        """Authors only → NEVER HIGH."""
        f1 = {"authors": "A. Kumar, B. Singh"}
        f2 = {"authors": "A. Kumar, B. Singh"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_journal_only_not_high(self):
        """Journal only → NEVER HIGH."""
        f1 = {"journal_name": "Nature"}
        f2 = {"journal_name": "Nature"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_year_only_not_high(self):
        """Year only → NEVER HIGH."""
        f1 = {"publication_year": "2025"}
        f2 = {"publication_year": "2025"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_same_author_different_title(self):
        """Same author, different title → NOT HIGH."""
        f1 = {"publication_title": "Quantum Computing", "authors": "A. Kumar"}
        f2 = {"publication_title": "Organic Chemistry", "authors": "A. Kumar"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_same_journal_different_papers(self):
        """Same journal, different papers → NOT HIGH."""
        f1 = {"publication_title": "Paper A", "journal_name": "Nature"}
        f2 = {"publication_title": "Paper B", "journal_name": "Nature"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_different_authors_same_title(self):
        """Same title, different authors → NOT HIGH."""
        f1 = {"publication_title": "Machine Learning", "authors": "A. Kumar"}
        f2 = {"publication_title": "Machine Learning", "authors": "X. Zhang"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_generic_title_not_high(self):
        """Generic title → NOT HIGH even with some overlap."""
        f1 = {"publication_title": "Introduction"}
        f2 = {"publication_title": "Introduction"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.confidence < HIGH_THRESHOLD

    def test_empty_fields(self):
        """Empty fields → LOW."""
        r = match_entities({}, {}, "d1", "d2")
        assert r.outcome == "low"
        assert r.confidence == 0.0

    def test_no_overlap(self):
        """Completely different documents → LOW."""
        f1 = {"publication_title": "Quantum Computing", "authors": "X. Zhang", "doi": "10.1/abc"}
        f2 = {"publication_title": "Organic Chemistry", "authors": "M. Johnson", "doi": "10.2/xyz"}
        r = match_entities(f1, f2, "d1", "d2")
        # Different DOIs → CONFLICT
        assert r.outcome == "conflict"


# =============================================================================
# Conflict Cases
# =============================================================================

class TestConflicts:
    """Cases with conflicting evidence."""

    def test_different_dois(self):
        """Different DOIs → CONFLICT."""
        f1 = {"doi": "10.1021/acs.est.2025.0042"}
        f2 = {"doi": "10.1038/s41567-024-0001"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "conflict"

    def test_different_manuscript_ids(self):
        """Different manuscript IDs → CONFLICT."""
        f1 = {"manuscript_id": "EST-2025-4567"}
        f2 = {"manuscript_id": "NC-2025-9999"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "conflict"

    def test_same_title_conflicting_doi(self):
        """Same title but conflicting DOI → CONFLICT."""
        f1 = {"publication_title": "Test Paper", "doi": "10.1/abc"}
        f2 = {"publication_title": "Test Paper", "doi": "10.2/xyz"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "conflict"


# =============================================================================
# Normalization Tests
# =============================================================================

class TestNormalization:
    """Test text normalization for matching."""

    def test_doi_prefix_normalization(self):
        """DOI prefixes are normalized."""
        f1 = {"doi": "10.1021/acs.est.2025.0042"}
        f2 = {"doi": "https://doi.org/10.1021/acs.est.2025.0042"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome == "high"

    def test_author_prefix_normalization(self):
        """Dr/Prof prefixes are removed."""
        f1 = {"authors": "Dr. A. Kumar", "publication_title": "Test"}
        f2 = {"authors": "Prof. A. Kumar", "publication_title": "Test"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome in ("high", "medium")

    def test_title_case_insensitive(self):
        """Title matching is case-insensitive."""
        f1 = {"publication_title": "DEEP LEARNING", "authors": "A. Kumar"}
        f2 = {"publication_title": "deep learning", "authors": "a kumar"}
        r = match_entities(f1, f2, "d1", "d2")
        assert r.outcome in ("high", "medium")


# =============================================================================
# False Positive Rate Verification
# =============================================================================

class TestFalsePositiveRate:
    """CRITICAL: Verify 0% false positive auto-link rate."""

    def test_different_papers_never_auto_link(self):
        """15 pairs of different papers → 0% auto-link."""
        papers = [
            {"publication_title": "Deep Learning for Microplastics", "authors": "A. Kumar", "doi": "10.1/abc"},
            {"publication_title": "Quantum Computing", "authors": "X. Zhang", "doi": "10.2/def"},
            {"publication_title": "Organic Chemistry", "authors": "M. Johnson", "doi": "10.3/ghi"},
            {"publication_title": "Machine Learning Review", "authors": "S. Lee", "doi": "10.4/jkl"},
            {"publication_title": "Natural Language Processing", "authors": "R. Patel", "doi": "10.5/mno"},
        ]

        auto_links = 0
        for i in range(len(papers)):
            for j in range(i + 1, len(papers)):
                r = match_entities(papers[i], papers[j], f"d{i}", f"d{j}")
                if r.outcome == "high":
                    auto_links += 1

        assert auto_links == 0, f"False positive auto-links: {auto_links}"

    def test_title_only_never_auto_links(self):
        """Title-only matches → NEVER auto-link (0% false positive)."""
        titles = [
            "Introduction to Machine Learning",
            "A Survey of Deep Learning",
            "Review of Natural Language Processing",
            "Fundamentals of Computer Science",
            "Advanced Topics in AI",
        ]

        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                r = match_entities(
                    {"publication_title": titles[i]},
                    {"publication_title": titles[j]},
                    f"d{i}", f"d{j}"
                )
                assert r.outcome != "high", f"Title-only auto-link: {titles[i]} vs {titles[j]}"
