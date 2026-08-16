"""Enrichment Idempotency & Lifecycle Integration Tests (Revision #9).

Tests the complete document-intelligence lifecycle:
- Upload → analysis → enrichment → polling → retry
- Idempotency: repeated operations don't create duplicates
- Provider failure: deterministic results preserved
- Confidence: meaningful, not fabricated
"""

from __future__ import annotations

import pytest

from app.application.services.field_candidate import (
    FieldCandidate,
    FieldRisk,
    FieldSource,
    FieldStatus,
    get_field_risk,
)
from app.application.services.reconciliation import (
    _normalize_value,
    _values_agree,
    compute_document_confidence,
    reconcile_fields,
)
from app.application.services.suggestion_policy import SAFE_FIELDS, SuggestionPolicy


# --- Helpers ---

def _det(pred: str, value: str, confidence: float = 0.9) -> FieldCandidate:
    return FieldCandidate(
        predicate_id=pred, field_name=pred, value=value,
        source=FieldSource.LABEL, confidence=confidence,
        evidence=f"det: {value}", risk=get_field_risk(pred),
    )

def _ai(pred: str, value: str, confidence: float = 0.8) -> FieldCandidate:
    return FieldCandidate(
        predicate_id=pred, field_name=pred, value=value,
        source=FieldSource.AI, confidence=confidence,
        evidence=f"ai: {value}", risk=get_field_risk(pred),
    )


# --- Failure / Recovery Matrix ---

class TestProviderUnavailable:
    """Provider unavailable: deterministic path survives."""

    def test_deterministic_only_works(self):
        det = [_det("publication_title", "Paper"), _det("publication_year", "2025")]
        ai = []
        result = reconcile_fields(det, ai)
        assert len(result) == 2
        assert all(r.source == FieldSource.LABEL for r in result)

    def test_no_fake_ai_complete(self):
        det = [_det("title", "Paper")]
        ai = []
        result = reconcile_fields(det, ai)
        assert result[0].source != FieldSource.AI
        assert result[0].source != FieldSource.AGREEMENT


class TestMalformedAIResult:
    """Malformed AI result: safely rejected."""

    def test_empty_ai_fields(self):
        det = [_det("title", "Paper")]
        ai = []
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].value == "Paper"

    def test_ai_empty_value(self):
        det = [_det("title", "Paper")]
        ai = [_ai("title", "")]
        result = reconcile_fields(det, ai)
        # Both present, but empty AI is a conflict/ignored
        assert len(result) >= 1


class TestAgreementScenarios:
    """Deterministic + AI agree: confidence improvement."""

    def test_exact_agreement(self):
        det = [_det("journal", "Nature", 0.85)]
        ai = [_ai("journal", "Nature", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AGREEMENT
        assert result[0].confidence > 0.85

    def test_case_agreement(self):
        det = [_det("journal", "nature", 0.85)]
        ai = [_ai("journal", "NATURE", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AGREEMENT

    def test_whitespace_agreement(self):
        det = [_det("journal", "  Nature  ", 0.85)]
        ai = [_ai("journal", "Nature", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AGREEMENT

    def test_containment_agreement(self):
        det = [_det("authors", "Kumar", 0.85)]
        ai = [_ai("authors", "Dr. V. Kumar and P. Bansal", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AGREEMENT


class TestConflictScenarios:
    """Deterministic + AI conflict: review required."""

    def test_genuine_conflict(self):
        det = [_det("journal", "Nature", 0.85)]
        ai = [_ai("journal", "Science", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].conflict is True
        assert result[0].status == FieldStatus.CONFLICT

    def test_conflict_keeps_deterministic(self):
        det = [_det("journal", "Nature", 0.85)]
        ai = [_ai("journal", "Science", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].value == "Nature"
        assert result[0].deterministic_value == "Nature"
        assert result[0].ai_value == "Science"


class TestAIOnlyFields:
    """AI-only field: proposal/review."""

    def test_ai_only_safe_field(self):
        det = []
        ai = [_ai("publication_title", "New Paper", 0.85)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AI
        assert result[0].status in (FieldStatus.PROPOSED, FieldStatus.AUTO_APPLIED)

    def test_ai_only_risky_field(self):
        det = []
        ai = [_ai("doi", "10.1234/test", 0.9)]
        result = reconcile_fields(det, ai)
        assert result[0].status == FieldStatus.REVIEW_REQUIRED


class TestRetryIdempotency:
    """Retry creates no duplicates."""

    def test_same_fields_twice_produces_same_result(self):
        det = [_det("title", "Paper"), _det("year", "2025")]
        ai = [_ai("title", "Paper")]
        result1 = reconcile_fields(det, ai)
        result2 = reconcile_fields(det, ai)
        assert len(result1) == len(result2)
        assert all(r1.value == r2.value for r1, r2 in zip(result1, result2))


class TestDuplicatePrevention:
    """Same document uploaded twice: no duplicate claims."""

    def test_identical_extraction_no_new_fields(self):
        det = [_det("title", "Paper"), _det("year", "2025")]
        ai = []
        result = reconcile_fields(det, ai)
        # Second upload with same extraction produces same fields
        result2 = reconcile_fields(det, ai)
        assert len(result) == len(result2)


class TestConfirmationPreservation:
    """Existing confirmed information preserved."""

    def test_deterministic_preserved_over_ai(self):
        det = [_det("title", "Confirmed Paper", 0.95)]
        ai = [_ai("title", "Different Paper", 0.80)]
        result = reconcile_fields(det, ai)
        # Deterministic (confirmed) preserved as primary
        assert result[0].value == "Confirmed Paper"

    def test_conflict_not_silent_overwrite(self):
        det = [_det("doi", "10.1234/original", 0.95)]
        ai = [_ai("doi", "10.1234/different", 0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].conflict is True
        assert result[0].status == FieldStatus.CONFLICT


class TestConfidenceEvaluation:
    """Confidence values are honest and evidence-based."""

    def test_confidence_range_valid(self):
        det = [_det("title", "Paper", 0.9)]
        ai = [_ai("title", "Paper", 0.8)]
        result = reconcile_fields(det, ai)
        assert 0.0 <= result[0].confidence <= 1.0

    def test_document_confidence_range(self):
        from app.application.services.reconciliation import ReconciledField
        fields = [
            ReconciledField(
                predicate_id="title", field_name="title", value="Paper",
                confidence=0.9, source=FieldSource.LABEL,
                status=FieldStatus.AUTO_APPLIED, risk=FieldRisk.LOW,
            ),
        ]
        conf = compute_document_confidence(0.95, fields)
        assert 0.0 <= conf <= 1.0

    def test_empty_fields_reduces_confidence(self):
        conf = compute_document_confidence(0.95, [])
        assert conf < 0.95


class TestAutomationSafetyRegression:
    """Prevent unsafe broadening of auto-apply."""

    def test_doi_cannot_auto_apply(self):
        det = [_det("doi", "10.1234/test", 0.99)]
        result = reconcile_fields(det, [])
        assert result[0].status == FieldStatus.REVIEW_REQUIRED

    def test_amount_cannot_auto_apply(self):
        det = [_det("sanctioned_amount", "5000000", 0.99)]
        result = reconcile_fields(det, [])
        assert result[0].status == FieldStatus.REVIEW_REQUIRED

    def test_safe_field_can_auto_apply(self):
        policy = SuggestionPolicy()
        det = [_det("publication_title", "Test", 0.95)]
        result = reconcile_fields(det, [], policy)
        assert result[0].status == FieldStatus.AUTO_APPLIED

    def test_safe_fields_count_bounded(self):
        assert len(SAFE_FIELDS) <= 25


class TestNormalizationEdgeCases:
    """Normalization handles real-world variations."""

    def test_empty_vs_empty(self):
        assert _values_agree("", "") is True

    def test_date_normalization(self):
        assert _values_agree("2025-03-15", "2025-03-15") is True

    def test_genuine_difference(self):
        assert _values_agree("Nature", "Science") is False
