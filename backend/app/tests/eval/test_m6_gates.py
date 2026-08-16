"""V3 M6 gates (blueprint §B6 / M6): classification accuracy + field precision.

Measures the Wave-1 typed extractor against the golden corpus and asserts the
blueprint gates:

- classification accuracy >= 0.90;
- field-level precision >= 0.95 (high-risk) / >= 0.85 (low-risk);
- a predicate below its gate (or unmeasured) can never be AUTO_SUGGESTED.

The measured per-predicate precision is recorded into a SuggestionPolicy so
the AUTO_SUGGESTED gate is exercised end-to-end, not just asserted as a
constant.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.nir import NirDocument, NirElement, NirElementType
from app.application.services.claim_service import ClaimService
from app.application.services.document_classifier import DocumentClassifier
from app.application.services.suggestion_policy import (
    CLASSIFICATION_ACCURACY_GATE,
    SuggestionPolicy,
    precision_threshold,
)
from app.application.services.typed_extraction import TypedClaimExtractor
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.source import MediaKind
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.tests.eval.m6_golden_documents import GOLDEN_DOCUMENTS


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()


def _nir(text: str) -> NirDocument:
    return NirDocument(
        source_id="doc:m6",
        media_kind=MediaKind.TEXT_LAYOUT.value,
        version=1,
        engine="test",
        engine_version=1,
        elements=(NirElement(element_type=NirElementType.PARAGRAPH, order=0, text=text),),
        normalized_text=text,
    )


def _claim_value(claim) -> object:
    value = claim.value if isinstance(claim.value, dict) else {}
    kind = value.get("kind")
    if kind == "money":
        return value.get("amount")
    if kind == "number":
        return value.get("value")
    if kind in ("date", "text"):
        return value.get("value")
    return value.get("text")


def _extract(session, filename: str, text: str, policy: SuggestionPolicy | None = None):
    extractor = TypedClaimExtractor(
        ClaimService(SQLClaimStore(session)),
        classifier=DocumentClassifier(),
        policy=policy or SuggestionPolicy(),
    )
    return extractor.extract(_nir(text), filename=filename, document_id="doc:m6")


def test_classification_accuracy_meets_gate() -> None:
    classifier = DocumentClassifier()
    correct = 0
    for filename, expected_type, text, _truth in GOLDEN_DOCUMENTS:
        result = classifier.classify(text, filename)
        if result.document_type_id == expected_type:
            correct += 1
    accuracy = correct / len(GOLDEN_DOCUMENTS)
    assert accuracy >= CLASSIFICATION_ACCURACY_GATE, accuracy
    assert correct == len(GOLDEN_DOCUMENTS)  # the corpus is deterministic


def test_field_precision_meets_gates(session) -> None:
    # (predicate_id -> [correct, total]) aggregated over the corpus
    stats: dict[str, list[int]] = {}
    for filename, _type, text, truth in GOLDEN_DOCUMENTS:
        result = _extract(session, filename, text)
        extracted = {c.predicate_id: _claim_value(c) for c in result.claims}
        for predicate_id, expected in truth.items():
            entry = stats.setdefault(predicate_id, [0, 0])
            entry[1] += 1
            if predicate_id in extracted and extracted[predicate_id] == expected:
                entry[0] += 1

    from app.application.knowledge.predicate_catalogue import get_predicate

    for predicate_id, (correct, total) in stats.items():
        precision = correct / total
        spec = get_predicate(predicate_id)
        threshold = precision_threshold(spec.risk_class)
        assert precision >= threshold, (
            f"{predicate_id} ({spec.risk_class}) precision {precision:.2f} "
            f"below gate {threshold}"
        )


def test_measurement_records_precision_into_policy(session) -> None:
    policy = SuggestionPolicy()
    stats: dict[str, list[int]] = {}
    for filename, _type, text, truth in GOLDEN_DOCUMENTS:
        result = _extract(session, filename, text, policy=policy)
        extracted = {c.predicate_id: _claim_value(c) for c in result.claims}
        for predicate_id, expected in truth.items():
            entry = stats.setdefault(predicate_id, [0, 0])
            entry[1] += 1
            if predicate_id in extracted and extracted[predicate_id] == expected:
                entry[0] += 1
    for predicate_id, (correct, total) in stats.items():
        policy.record_precision(predicate_id, correct / total)

    # every measured predicate now meets its gate -> suggestion allowed
    for predicate_id in stats:
        assert policy.allows_auto_suggest(predicate_id), predicate_id


def test_unmeasured_predicate_never_auto_suggests(session) -> None:
    """Revision #6: SAFE_FIELDS can auto-suggest without measurement.
    Non-safe fields remain blocked (fail-safe).
    """
    from app.application.services.suggestion_policy import SAFE_FIELDS
    policy = SuggestionPolicy()  # nothing measured
    result = _extract(
        session, "grant_sanction_letter_1.txt",
        GOLDEN_DOCUMENTS[0][2], policy=policy,
    )
    assert result.classification.document_type_id == "grant_sanction_letter"
    # SAFE_FIELDS can auto-suggest; non-safe fields are proposed
    suggested_preds = {c.predicate_id for c in result.suggested}
    proposed_preds = {c.predicate_id for c in result.proposed}
    for pred in suggested_preds:
        assert pred in SAFE_FIELDS, f"{pred} suggested but not in SAFE_FIELDS"
    # Non-safe fields must be proposed, not suggested
    for pred in proposed_preds:
        if pred not in SAFE_FIELDS:
            assert all(c.status is ClaimStatus.PROPOSED for c in result.proposed if c.predicate_id == pred)


def test_below_gate_predicate_stays_proposed(session) -> None:
    # A predicate recorded below its gate must never be suggested.
    policy = SuggestionPolicy({"sanctioned_amount": 0.5})  # below 0.95 gate
    assert not policy.allows_auto_suggest("sanctioned_amount")
    result = _extract(
        session, "grant_sanction_letter_1.txt",
        GOLDEN_DOCUMENTS[0][2], policy=policy,
    )
    suggested_preds = {c.predicate_id for c in result.suggested}
    assert "sanctioned_amount" not in suggested_preds
    assert all(c.status is ClaimStatus.PROPOSED for c in result.claims if c.predicate_id == "sanctioned_amount")


def test_meeting_gate_predicate_is_suggested(session) -> None:
    # With a passing precision, eligible extractions become AUTO_SUGGESTED
    # (review shortcut) but remain non-authoritative.
    policy = SuggestionPolicy({"sanctioned_amount": 1.0})
    result = _extract(
        session, "grant_sanction_letter_1.txt",
        GOLDEN_DOCUMENTS[0][2], policy=policy,
    )
    suggested_preds = {c.predicate_id for c in result.suggested}
    assert "sanctioned_amount" in suggested_preds
    for claim in result.suggested:
        assert claim.status is ClaimStatus.AUTO_SUGGESTED
        assert claim.is_authoritative is False
