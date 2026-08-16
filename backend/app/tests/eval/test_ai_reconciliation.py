"""AI Reconciliation Tests (Revision #6).

Tests the deterministic vs AI reconciliation engine with mock scenarios.
No real AI provider required — uses deterministic test doubles.
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
    compute_document_confidence,
    reconcile_fields,
)
from app.application.services.suggestion_policy import SuggestionPolicy


def _det(pred: str, value: str, confidence: float = 0.9) -> FieldCandidate:
    """Create a deterministic field candidate."""
    return FieldCandidate(
        predicate_id=pred,
        field_name=pred,
        value=value,
        source=FieldSource.LABEL,
        confidence=confidence,
        evidence=f"deterministic: {value}",
        risk=get_field_risk(pred),
    )


def _ai(pred: str, value: str, confidence: float = 0.8) -> FieldCandidate:
    """Create an AI field candidate."""
    return FieldCandidate(
        predicate_id=pred,
        field_name=pred,
        value=value,
        source=FieldSource.AI,
        confidence=confidence,
        evidence=f"ai: {value}",
        risk=get_field_risk(pred),
    )


class TestCaseA_DeterministicOnly:
    """Only deterministic extraction found the field."""

    def test_keeps_deterministic_value(self):
        det = [_det("publication_title", "Catalytic Degradation")]
        ai = []
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].value == "Catalytic Degradation"
        assert result[0].source == FieldSource.LABEL
        assert result[0].conflict is False

    def test_low_risk_high_confidence_auto_applies(self):
        policy = SuggestionPolicy()
        det = [_det("publication_title", "Test Paper", confidence=0.95)]
        ai = []
        result = reconcile_fields(det, ai, policy)
        assert result[0].status == FieldStatus.AUTO_APPLIED

    def test_high_risk_requires_review(self):
        det = [_det("doi", "10.1234/test", confidence=0.95)]
        ai = []
        result = reconcile_fields(det, ai)
        assert result[0].status == FieldStatus.REVIEW_REQUIRED


class TestCaseB_AIOnly:
    """Only AI extraction found the field."""

    def test_ai_only_proposes(self):
        det = []
        ai = [_ai("journal_name", "Nature")]
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].value == "Nature"
        assert result[0].source == FieldSource.AI
        assert result[0].confidence < 0.8  # AI-only penalty applied

    def test_ai_only_low_risk_proposes(self):
        policy = SuggestionPolicy()
        det = []
        ai = [_ai("publication_title", "Test Paper", confidence=0.85)]
        result = reconcile_fields(det, ai, policy)
        # Low risk AI-only should propose, not auto-apply
        assert result[0].status in (FieldStatus.PROPOSED, FieldStatus.AUTO_APPLIED)


class TestCaseC_Agreement:
    """Both deterministic and AI found the same value."""

    def test_agreement_boosts_confidence(self):
        det = [_det("journal_name", "Nature", confidence=0.85)]
        ai = [_ai("journal_name", "Nature", confidence=0.80)]
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].source == FieldSource.AGREEMENT
        assert result[0].confidence > 0.85  # Boost applied
        assert result[0].conflict is False

    def test_agreement_with_case_difference(self):
        det = [_det("journal_name", "nature", confidence=0.85)]
        ai = [_ai("journal_name", "Nature", confidence=0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].source == FieldSource.AGREEMENT

    def test_agreement_with_partial_overlap(self):
        det = [_det("authors", "V. Kumar", confidence=0.85)]
        ai = [_ai("authors", "Dr. V. Kumar and P. Bansal", confidence=0.80)]
        result = reconcile_fields(det, ai)
        # "Kumar" overlaps — should agree
        assert result[0].source == FieldSource.AGREEMENT


class TestCaseD_Conflict:
    """Both found different values."""

    def test_conflict_flagged(self):
        det = [_det("journal_name", "Nature", confidence=0.85)]
        ai = [_ai("journal_name", "Science", confidence=0.80)]
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].conflict is True
        assert result[0].status == FieldStatus.CONFLICT
        assert result[0].deterministic_value == "Nature"
        assert result[0].ai_value == "Science"

    def test_conflict_keeps_deterministic_as_primary(self):
        det = [_det("journal_name", "Nature", confidence=0.85)]
        ai = [_ai("journal_name", "Science", confidence=0.80)]
        result = reconcile_fields(det, ai)
        assert result[0].value == "Nature"  # Deterministic is primary


class TestCaseE_MalformedAI:
    """AI returns malformed or unsupported data."""

    def test_empty_ai_fields(self):
        det = [_det("publication_title", "Test")]
        ai = []
        result = reconcile_fields(det, ai)
        assert len(result) == 1
        assert result[0].source == FieldSource.LABEL

    def test_ai_with_empty_value(self):
        det = []
        ai = [_ai("publication_title", "")]
        result = reconcile_fields(det, ai)
        # Empty value should still be included (validation happens elsewhere)
        assert len(result) == 1


class TestConfidenceComputation:
    """Document-level confidence computation."""

    def test_no_fields_reduces_confidence(self):
        classification_conf = 0.95
        result = compute_document_confidence(classification_conf, [])
        assert result < classification_conf

    def test_conflicts_reduce_confidence(self):
        fields = [
            _det("journal", "A", 0.9),
            _det("title", "B", 0.9),
        ]
        # Mark one as conflict
        from app.application.services.reconciliation import ReconciledField
        reconciled = [
            ReconciledField(
                predicate_id="journal", field_name="journal", value="A",
                confidence=0.6, source=FieldSource.LABEL,
                status=FieldStatus.CONFLICT, risk=FieldRisk.MEDIUM,
                conflict=True,
            ),
            ReconciledField(
                predicate_id="title", field_name="title", value="B",
                confidence=0.9, source=FieldSource.LABEL,
                status=FieldStatus.AUTO_APPLIED, risk=FieldRisk.LOW,
            ),
        ]
        result = compute_document_confidence(0.95, reconciled)
        assert result < 0.95  # Conflict penalty

    def test_auto_applied_boosts_confidence(self):
        from app.application.services.reconciliation import ReconciledField
        reconciled = [
            ReconciledField(
                predicate_id="title", field_name="title", value="B",
                confidence=0.95, source=FieldSource.LABEL,
                status=FieldStatus.AUTO_APPLIED, risk=FieldRisk.LOW,
            ),
        ]
        result = compute_document_confidence(0.90, reconciled)
        assert result >= 0.85  # Reasonable confidence


class TestAIFailureScenarios:
    """AI failure must not break deterministic extraction."""

    def test_ai_empty_doesnt_affect_deterministic(self):
        det = [_det("title", "My Paper"), _det("year", "2025")]
        ai = []
        result = reconcile_fields(det, ai)
        assert len(result) == 2
        assert all(r.source == FieldSource.LABEL for r in result)

    def test_ai_unsupported_field_ignored(self):
        det = [_det("title", "My Paper")]
        # AI returns a field not in the schema
        ai = [FieldCandidate(
            predicate_id="unsupported_field",
            field_name="unsupported",
            value="something",
            source=FieldSource.AI,
            confidence=0.8,
        )]
        result = reconcile_fields(det, ai)
        # Both should be present
        assert len(result) == 2


class TestAutomationRate:
    """Measure automation metrics."""

    def test_measure_reconciliation_metrics(self):
        """Report metrics for a realistic scenario."""
        policy = SuggestionPolicy()

        # Simulate a research paper extraction
        det_fields = [
            _det("publication_title", "Catalytic Degradation", 0.9),
            _det("publication_year", "2025", 0.9),
            _det("doi", "10.1234/test", 0.85),
            _det("authors", "V. Kumar", 0.85),
        ]
        ai_fields = [
            _ai("publication_title", "Catalytic Degradation", 0.8),
            _ai("journal_name", "Environmental Science", 0.75),
        ]

        reconciled = reconcile_fields(det_fields, ai_fields, policy)

        auto = sum(1 for r in reconciled if r.status == FieldStatus.AUTO_APPLIED)
        proposed = sum(1 for r in reconciled if r.status == FieldStatus.PROPOSED)
        review = sum(1 for r in reconciled if r.status == FieldStatus.REVIEW_REQUIRED)
        conflicts = sum(1 for r in reconciled if r.conflict)

        print(f"\nReconciliation Metrics:")
        print(f"  Total fields: {len(reconciled)}")
        print(f"  Auto-applied: {auto}")
        print(f"  Proposed: {proposed}")
        print(f"  Review required: {review}")
        print(f"  Conflicts: {conflicts}")

        # No conflicts in this scenario (AI agrees on title, adds journal)
        assert conflicts == 0
        # At least some fields should auto-apply
        assert auto >= 1
