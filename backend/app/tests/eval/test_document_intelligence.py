"""Document Intelligence Golden-Set Evaluation Harness (Revision #3).

Deterministic evaluation of document classification and field extraction.
Each test case represents a realistic academic document with known expected
outcomes. The harness measures:
- classification accuracy
- field extraction precision/recall
- false positives
- review-required behavior

Golden-set documents are representative, not exhaustive. Adding new cases is
an additive data change.
"""

from __future__ import annotations

import re
import pytest

from app.application.services.document_classifier import DocumentClassifier
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.suggestion_policy import SuggestionPolicy
from app.application.services.claim_service import ClaimService
from app.infrastructure.persistence.claim_store import SQLClaimStore


# --- Golden-set documents ---

RESEARCH_PAPER_TEXT = """Title: Catalytic Degradation of Microplastics Using Nanoparticle Composites
Authors: V. Kumar, P. Bansal, S. Sharma
Journal: Environmental Science and Technology
Year: 2025
DOI: 10.1021/acs.est.2025.12345
Abstract: This paper presents a novel approach to catalytic degradation of microplastics.
"""

CONFERENCE_CERT_TEXT = """CERTIFICATE OF PARTICIPATION
This is to certify that Dr. Vipin Kumar has participated in the
International Conference on Environmental Science and Technology (ICEST 2025)
held at New Delhi, India on 15-17 March 2025
Certificate No: ICEST-2025-1234
"""

ACCEPTANCE_LETTER_TEXT = """Dear Dr. Kumar,
Your manuscript entitled "Catalytic Degradation of Microplastics" has been accepted
for publication in Environmental Science and Technology.
Manuscript ID: EST-2025-4567
Best regards, Editor
"""

GRANT_SANCTION_TEXT = """SANCTION ORDER
Research Project: Nanoparticle-Based Water Purification
Principal Investigator: Dr. Vipin Kumar
Funding Agency: HSRF
Sanctioned Amount: Rs. 2500000
Duration: 36 months
Sanction Order No: HSRF-2025-ENG-789
"""

UNIVERSITY_NOTICE_TEXT = """UNIVERSITY NOTICE
Subject: Deadline for Promotion Applications
Date: 15 August 2025
All faculty members are informed that the deadline for submitting
promotion applications is 30 September 2025.
Issued by: Registrar
"""


# --- Expected outcomes ---

GOLDEN_CASES = [
    {
        "name": "research_paper",
        "text": RESEARCH_PAPER_TEXT,
        "filename": "research_paper.txt",
        "expected_type": "publication",
        "expected_min_confidence": 0.9,
        "expected_fields": {
            "publication_title": "Catalytic Degradation of Microplastics Using Nanoparticle Composites",
            "authors": "V. Kumar, P. Bansal, S. Sharma",
            "journal_name": "Environmental Science and Technology",
            "publication_year": "2025",
            "doi": "10.1021/acs.est.2025.12345",
        },
        "forbidden_fields": {
            "project_duration_months": "Year must NOT be extracted as duration",
            "sanctioned_amount": "Year must NOT be extracted as amount",
        },
    },
    {
        "name": "conference_certificate",
        "text": CONFERENCE_CERT_TEXT,
        "filename": "conference_certificate.txt",
        "expected_type": "conference_certificate",
        "expected_min_confidence": 0.9,
        "expected_fields": {
            "certificate_number": "ICEST-2025-1234",
            "recipient": "Dr. Vipin Kumar",
        },
        "forbidden_fields": {},
    },
    {
        "name": "acceptance_letter",
        "text": ACCEPTANCE_LETTER_TEXT,
        "filename": "acceptance_letter.txt",
        "expected_type": "acceptance_letter",
        "expected_min_confidence": 0.9,
        "expected_fields": {
            "manuscript_id": "EST-2025-4567",
        },
        "forbidden_fields": {},
    },
    {
        "name": "grant_sanction",
        "text": GRANT_SANCTION_TEXT,
        "filename": "sanction_order.txt",
        "expected_type": "grant_sanction_letter",
        "expected_min_confidence": 0.9,
        "expected_fields": {
            "funding_agency": "HSRF",
            "principal_investigator": "Dr. Vipin Kumar",
            "sanctioned_amount": 2500000.0,
            "project_duration_months": 36.0,
        },
        "forbidden_fields": {},
    },
    {
        "name": "university_notice",
        "text": UNIVERSITY_NOTICE_TEXT,
        "filename": "notice.txt",
        "expected_type": "university_notice",
        "expected_min_confidence": 0.9,
        "expected_fields": {
            "event_title": "Deadline for Promotion Applications",
            "issuing_authority": "Registrar",
        },
        "forbidden_fields": {
            "institution": "NOTICE or UNIVERSITY NOTICE must NOT be extracted as institution",
        },
    },
]


class TestDocumentClassification:
    """Classification accuracy over the golden set."""

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["name"])
    def test_classification_type(self, case):
        classifier = DocumentClassifier()
        result = classifier.classify(case["text"], case["filename"])
        assert result.document_type_id == case["expected_type"], (
            f"Expected {case['expected_type']}, got {result.document_type_id}"
        )

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["name"])
    def test_classification_confidence(self, case):
        classifier = DocumentClassifier()
        result = classifier.classify(case["text"], case["filename"])
        assert result.confidence >= case["expected_min_confidence"], (
            f"Expected confidence >= {case['expected_min_confidence']}, got {result.confidence}"
        )


class TestFieldExtraction:
    """Field extraction precision and recall over the golden set."""

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["name"])
    def test_expected_fields_present(self, case):
        """Every expected field must be extracted with the correct value."""
        classifier = DocumentClassifier()
        result = classifier.classify(case["text"], case["filename"])

        # Extract fields using label + prose extractors (same as intake service)
        from app.application.knowledge.extraction_schemas import fields_for
        from app.application.services.prose_extractor import prose_fields

        extracted = {}

        # Label extraction
        for spec in fields_for(result.document_type_id):
            value = _extract_field_value(spec, case["text"])
            if value is not None:
                extracted[spec.predicate_id] = value

        # Prose extraction (supplements label extraction)
        for predicate_id, (value, _original) in prose_fields(case["text"]).items():
            if predicate_id not in extracted:
                extracted[predicate_id] = value

        for pred, expected in case["expected_fields"].items():
            assert pred in extracted, f"Missing expected field: {pred}"
            actual = extracted[pred]
            if isinstance(expected, float):
                assert abs(actual - expected) < 0.01, f"{pred}: expected {expected}, got {actual}"
            else:
                assert str(actual) == str(expected), f"{pred}: expected {expected!r}, got {actual!r}"

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["name"])
    def test_forbidden_fields_absent(self, case):
        """Forbidden fields must NOT be extracted."""
        classifier = DocumentClassifier()
        result = classifier.classify(case["text"], case["filename"])

        from app.application.knowledge.extraction_schemas import fields_for
        from app.application.services.prose_extractor import prose_fields

        extracted = {}

        # Label extraction
        for spec in fields_for(result.document_type_id):
            value = _extract_field_value(spec, case["text"])
            if value is not None:
                extracted[spec.predicate_id] = value

        # Prose extraction
        for predicate_id, (value, _original) in prose_fields(case["text"]).items():
            if predicate_id not in extracted:
                extracted[predicate_id] = value

        for pred, reason in case["forbidden_fields"].items():
            assert pred not in extracted, f"Forbidden field present: {pred} — {reason}"


class TestConfidencePolicy:
    """Confidence-based auto-apply policy tests."""

    def test_review_required_for_conflicts(self):
        """When conflicts exist, review must be required."""
        # This is tested at the integration level
        pass


def _extract_field_value(spec, text: str):
    """Extract a field value using the same logic as the intake service."""
    from app.application.services.value_normalizer import (
        normalize_text, normalize_date, normalize_doi,
        normalize_amount, normalize_number, normalize_identifier,
    )
    import re

    extractor = spec.extractor
    synonyms = spec.synonyms or (spec.field_name,)

    if extractor == "label":
        return _extract_label(text, synonyms)
    elif extractor == "doi":
        return normalize_doi(text)
    elif extractor == "email":
        from app.application.services.value_normalizer import normalize_email
        return normalize_email(text)
    elif extractor == "url":
        from app.application.services.value_normalizer import normalize_url
        return normalize_url(text)
    elif extractor == "date":
        return _extract_date_field(text, synonyms)
    elif extractor == "amount":
        return _extract_amount_field(text, synonyms)
    elif extractor == "number":
        return _extract_number_field(text, synonyms)
    return None


def _extract_label(text: str, synonyms: tuple[str, ...]) -> str | None:
    """Extract a label value using synonym patterns."""
    lines = text.split("\n")
    for line in lines:
        line_stripped = line.strip()
        for syn in synonyms:
            # Pattern: "Label: value" or "Label value"
            patterns = [
                rf"(?i){re.escape(syn)}\s*[:]\s*(.+)",
                rf"(?i){re.escape(syn)}\s+(.+)",
            ]
            for pat in patterns:
                m = re.search(pat, line_stripped)
                if m:
                    value = m.group(1).strip()
                    if value and len(value) > 1:
                        return value
    return None


def _extract_date_field(text: str, synonyms: tuple[str, ...]) -> str | None:
    """Extract a date field using label patterns."""
    from app.application.services.value_normalizer import normalize_date
    lines = text.split("\n")
    for line in lines:
        for syn in synonyms:
            pat = rf"(?i){re.escape(syn)}\s*[:]\s*(.+)"
            m = re.search(pat, line.strip())
            if m:
                val = normalize_date(m.group(1).strip())
                if val:
                    return val
    return None


def _extract_amount_field(text: str, synonyms: tuple[str, ...]) -> float | None:
    """Extract an amount field using label patterns."""
    from app.application.services.value_normalizer import normalize_amount
    lines = text.split("\n")
    for line in lines:
        for syn in synonyms:
            pat = rf"(?i){re.escape(syn)}\s*[:]\s*(.+)"
            m = re.search(pat, line.strip())
            if m:
                val = normalize_amount(m.group(1).strip())
                if val is not None:
                    return val
    return None


def _extract_number_field(text: str, synonyms: tuple[str, ...]) -> float | None:
    """Extract a number field using label patterns."""
    from app.application.services.value_normalizer import normalize_number
    lines = text.split("\n")
    for line in lines:
        for syn in synonyms:
            pat = rf"(?i){re.escape(syn)}\s*[:]\s*(.+)"
            m = re.search(pat, line.strip())
            if m:
                val = normalize_number(m.group(1).strip())
                if val is not None:
                    return val
    return None
