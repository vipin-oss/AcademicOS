"""Reconciliation engine for deterministic vs AI extraction (Revision #5).

Compares field candidates from deterministic extraction and AI enrichment,
producing reconciled fields with meaningful confidence scores and safe
automation decisions.

Cases:
- Deterministic only → keep deterministic
- AI only → propose if safe field, otherwise review
- Both agree → agreement increases confidence
- Both disagree → conflict, requires review
- Neither → no field
"""

from __future__ import annotations

from app.application.services.field_candidate import (
    FieldCandidate,
    FieldRisk,
    FieldSource,
    FieldStatus,
    ReconciledField,
    get_field_risk,
)
from app.application.services.suggestion_policy import SuggestionPolicy


# Confidence adjustments
_AGREEMENT_BOOST = 0.05  # When deterministic and AI agree
_CONFLICT_PENALTY = 0.3  # When deterministic and AI disagree
_AI_ONLY_PENALTY = 0.1   # When only AI found it (less trusted)


def _normalize_value(value: str) -> str:
    """Normalize a value for comparison."""
    return " ".join(str(value).strip().lower().split())


def _values_agree(det_value: str, ai_value: str) -> bool:
    """Check if two values are substantially the same."""
    det_norm = _normalize_value(det_value)
    ai_norm = _normalize_value(ai_value)

    # Exact match
    if det_norm == ai_norm:
        return True

    # One contains the other (e.g., "Kumar" in "Dr. V. Kumar")
    if det_norm in ai_norm or ai_norm in det_norm:
        return True

    # Check if they share significant tokens
    det_tokens = set(det_norm.split())
    ai_tokens = set(ai_norm.split())
    if not det_tokens or not ai_tokens:
        return False

    overlap = det_tokens & ai_tokens
    # If > 50% of tokens overlap, consider them agreeing
    return len(overlap) / min(len(det_tokens), len(ai_tokens)) > 0.5


def reconcile_fields(
    deterministic_fields: list[FieldCandidate],
    ai_fields: list[FieldCandidate],
    policy: SuggestionPolicy | None = None,
) -> list[ReconciledField]:
    """Reconcile deterministic and AI field candidates.

    Returns reconciled fields with meaningful confidence and status.
    """
    if policy is None:
        policy = SuggestionPolicy()

    # Group by predicate_id
    det_by_pred: dict[str, FieldCandidate] = {}
    for f in deterministic_fields:
        det_by_pred[f.predicate_id] = f

    ai_by_pred: dict[str, FieldCandidate] = {}
    for f in ai_fields:
        ai_by_pred[f.predicate_id] = f

    # All predicates we know about
    all_preds = set(det_by_pred.keys()) | set(ai_by_pred.keys())

    reconciled: list[ReconciledField] = []

    for pred in all_preds:
        det = det_by_pred.get(pred)
        ai = ai_by_pred.get(pred)
        risk = get_field_risk(pred)

        if det and ai:
            # Both found something
            if _values_agree(det.value, ai.value):
                # CASE C: Agreement
                confidence = min(det.confidence + _AGREEMENT_BOOST, 0.99)
                source = FieldSource.AGREEMENT
                status = _decide_status(confidence, risk, policy, pred)
                reconciled.append(ReconciledField(
                    predicate_id=pred,
                    field_name=det.field_name,
                    value=det.value,  # Use deterministic value (more trusted)
                    confidence=confidence,
                    source=source,
                    status=status,
                    risk=risk,
                    evidence=det.evidence,
                    deterministic_value=det.value,
                    ai_value=ai.value,
                    conflict=False,
                ))
            else:
                # CASE D: Conflict
                confidence = max(det.confidence - _CONFLICT_PENALTY, 0.3)
                reconciled.append(ReconciledField(
                    predicate_id=pred,
                    field_name=det.field_name,
                    value=det.value,  # Keep deterministic as primary
                    confidence=confidence,
                    source=FieldSource.LABEL,  # Deterministic is primary
                    status=FieldStatus.CONFLICT,
                    risk=risk,
                    evidence=det.evidence,
                    deterministic_value=det.value,
                    ai_value=ai.value,
                    conflict=True,
                ))

        elif det:
            # CASE A: Only deterministic found it
            reconciled.append(ReconciledField(
                predicate_id=pred,
                field_name=det.field_name,
                value=det.value,
                confidence=det.confidence,
                source=det.source,
                status=_decide_status(det.confidence, risk, policy, pred),
                risk=risk,
                evidence=det.evidence,
                deterministic_value=det.value,
            ))

        elif ai:
            # CASE B: Only AI found it
            confidence = max(ai.confidence - _AI_ONLY_PENALTY, 0.3)
            status = _decide_status(confidence, risk, policy, pred)
            reconciled.append(ReconciledField(
                predicate_id=pred,
                field_name=ai.field_name,
                value=ai.value,
                confidence=confidence,
                source=FieldSource.AI,
                status=status,
                risk=risk,
                evidence=ai.evidence,
                ai_value=ai.value,
            ))

    return reconciled


def _decide_status(
    confidence: float,
    risk: FieldRisk,
    policy: SuggestionPolicy,
    predicate_id: str,
) -> FieldStatus:
    """Decide the status based on confidence, risk, and policy."""

    # Safe fields with high confidence → auto-apply
    if risk == FieldRisk.LOW and confidence >= 0.85:
        if policy.is_safe_field(predicate_id) or policy.allows_auto_suggest(predicate_id):
            return FieldStatus.AUTO_APPLIED

    # Medium risk with good confidence → propose
    if risk == FieldRisk.MEDIUM and confidence >= 0.75:
        return FieldStatus.PROPOSED

    # High risk always requires review
    if risk == FieldRisk.HIGH:
        return FieldStatus.REVIEW_REQUIRED

    # Low confidence → review
    if confidence < 0.70:
        return FieldStatus.REVIEW_REQUIRED

    # Default: propose
    return FieldStatus.PROPOSED


def compute_document_confidence(
    classification_confidence: float,
    reconciled_fields: list[ReconciledField],
) -> float:
    """Compute a meaningful document-level confidence score.

    Based on:
    - Classification confidence
    - Average field confidence
    - Number of conflicts
    - Number of auto-applied fields
    """
    if not reconciled_fields:
        return classification_confidence * 0.8  # Lower if no fields extracted

    field_confidences = [f.confidence for f in reconciled_fields]
    avg_field_confidence = sum(field_confidences) / len(field_confidences)

    conflicts = sum(1 for f in reconciled_fields if f.conflict)
    auto_applied = sum(1 for f in reconciled_fields if f.status == FieldStatus.AUTO_APPLIED)

    # Base: weighted average of classification and field confidence
    base = 0.4 * classification_confidence + 0.6 * avg_field_confidence

    # Penalty for conflicts
    conflict_penalty = conflicts * 0.05

    # Bonus for auto-applied fields (indicates high quality extraction)
    auto_bonus = min(auto_applied * 0.02, 0.1)

    return max(min(base - conflict_penalty + auto_bonus, 0.99), 0.3)


__all__ = [
    "compute_document_confidence",
    "reconcile_fields",
]
