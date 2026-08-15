"""AUTO_SUGGESTED precision gates (V3 M6, ADR-053; resolves audit A10).

M6 gate: a predicate may be AUTO_SUGGESTED only when its *measured* field-level
precision meets its risk class threshold (high-risk >= 0.95, low-risk >= 0.85).
Below gate — or before the predicate has ever been measured — suggestion is
**disabled** and its extractions stay PROPOSED until a human confirms them.
This is the mechanical guard that keeps machine output out of authoritative
truth (A10 / ADR-006): suggestion is a review shortcut, never an approval.

Measurement is performed by the M6 evaluation harness (golden documents), which
records per-predicate precision here. Default is "not measured → disabled",
which is fail-safe.
"""

from __future__ import annotations

from app.application.knowledge.predicate_catalogue import (
    RISK_HIGH,
    get_predicate,
)

#: Field-level precision gates (blueprint §B6 / M6).
PRECISION_GATE_HIGH = 0.95
PRECISION_GATE_LOW = 0.85
#: Classification accuracy gate (blueprint §B6 / M6).
CLASSIFICATION_ACCURACY_GATE = 0.90
#: Minimum fact_confidence for a correctly-extracted claim to be suggested.
AUTO_SUGGEST_CONFIDENCE = 0.90


def precision_threshold(risk_class: str) -> float:
    """The precision gate for a risk class (high/low)."""
    return PRECISION_GATE_HIGH if risk_class == RISK_HIGH else PRECISION_GATE_LOW


class SuggestionPolicy:
    """Gate keeper for AUTO_SUGGESTED. Fail-safe: unmeasured -> disabled."""

    def __init__(self, measured_precision: dict[str, float] | None = None) -> None:
        self._measured: dict[str, float] = dict(measured_precision or {})

    def record_precision(self, predicate_id: str, precision: float) -> None:
        """Record a measured field precision for a predicate (0.0..1.0)."""
        self._measured[predicate_id] = float(precision)

    def measured_precision(self, predicate_id: str) -> float | None:
        return self._measured.get(predicate_id)

    def allows_auto_suggest(self, predicate_id: str) -> bool:
        """Whether a predicate's extractions may be AUTO_SUGGESTED.

        False when the predicate is unknown, has never been measured, or its
        measured precision is below its risk-class gate.
        """
        spec = get_predicate(predicate_id)
        if spec is None:
            return False
        precision = self._measured.get(predicate_id)
        if precision is None:
            return False
        return precision >= precision_threshold(spec.risk_class)


__all__ = [
    "AUTO_SUGGEST_CONFIDENCE",
    "CLASSIFICATION_ACCURACY_GATE",
    "PRECISION_GATE_HIGH",
    "PRECISION_GATE_LOW",
    "SuggestionPolicy",
    "precision_threshold",
]
