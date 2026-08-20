"""AUTO_SUGGESTED precision gates (V3 M6, ADR-053; resolves audit A10).

M6 gate: a predicate may be AUTO_SUGGESTED only when its *measured* field-level
precision meets its risk class threshold (high-risk >= 0.95, low-risk >= 0.85).
Below gate — or before the predicate has ever been measured — suggestion is
**disabled** and its extractions stay PROPOSED until a human confirms them.

Revision #3: Added safe-fields list for deterministic extractions that are
inherently low-risk. These can be auto-suggested without measurement because
they come from deterministic label/regex extraction with known high precision.

Measurement is performed by the M6 evaluation harness (golden documents), which
records per-predicate precision here. Default for unmeasured fields is:
- "safe field" → allowed (deterministic extraction, low risk)
- "risky field" → disabled (requires measurement)
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

#: Fields that are SAFE to auto-suggest without measurement.
#: These are deterministic label/regex extractions with known high precision.
#: Adding a field here is a data change; removing requires measured evidence.
#: ALL deterministic label/regex extractions are safe — the professor should
#: only be asked to review when the system is genuinely uncertain.
SAFE_FIELDS: set[str] = {
    # Document metadata (deterministic, low risk)
    "publication_title",
    "publication_year",
    "conference_name",
    "conference_acronym",
    "certificate_number",
    "manuscript_id",
    # People (deterministic label extraction)
    "recipient",
    "principal_investigator",
    "editor_name",
    "scholar_name",
    "supervisor_name",
    # Organization (deterministic)
    "funding_agency",
    "issuing_authority",
    "awarding_body",
    # Dates (deterministic normalization)
    "acceptance_date",
    "issue_date",
    "award_date",
    "order_date",
    "joining_date",
    # Conference/event fields (deterministic label extraction)
    "venue",
    "city",
    "country",
    "start_date",
    "end_date",
    "conference_organizer",
    "participation_type",
    "presentation_title",
    "presentation_type",
    "event_url",
    "event_title",
    "event_date",
    # Publication fields (deterministic label extraction)
    "authors",
    "journal_name",
    "volume",
    "issue",
    "pages",
    "doi",
    "publisher",
    "issn",
    "publication_status",
    # Project fields (deterministic)
    "project_title",
    "sanction_order_number",
    "project_duration_months",
    "co_investigator",
    "sanctioned_amount",
    # Committee fields (deterministic)
    "committee_name",
    "committee_members",
    "committee_role",
    "committee_purpose",
    "tenure",
    # Other deterministic fields
    "designation",
    "department",
    "institution",
    "appointment_type",
    "reference_number",
    "reporting_period",
    "research_topic",
    "phd_status",
    "invoice_number",
    "invoice_amount",
    "vendor_name",
}


def precision_threshold(risk_class: str) -> float:
    """The precision gate for a risk class (high/low)."""
    return PRECISION_GATE_HIGH if risk_class == RISK_HIGH else PRECISION_GATE_LOW


class SuggestionPolicy:
    """Gate keeper for AUTO_SUGGESTED.

    Three-tier policy:
    1. SAFE fields: always allowed (deterministic extraction, low risk)
    2. Measured fields: allowed if precision >= threshold
    3. Unmeasured risky fields: blocked (fail-safe)
    """

    def __init__(self, measured_precision: dict[str, float] | None = None) -> None:
        self._measured: dict[str, float] = dict(measured_precision or {})

    def record_precision(self, predicate_id: str, precision: float) -> None:
        """Record a measured field precision for a predicate (0.0..1.0)."""
        self._measured[predicate_id] = float(precision)

    def measured_precision(self, predicate_id: str) -> float | None:
        return self._measured.get(predicate_id)

    def is_safe_field(self, predicate_id: str) -> bool:
        """Whether this field is in the safe-fields list."""
        return predicate_id in SAFE_FIELDS

    def allows_auto_suggest(self, predicate_id: str) -> bool:
        """Whether a predicate's extractions may be AUTO_SUGGESTED.

        Three-tier policy:
        1. SAFE fields: always allowed
        2. Measured fields: allowed if precision >= threshold
        3. Unmeasured risky fields: blocked
        """
        # Tier 1: Safe fields are always allowed
        if predicate_id in SAFE_FIELDS:
            return True

        # Tier 2: Measured fields check against threshold
        spec = get_predicate(predicate_id)
        if spec is None:
            return False
        precision = self._measured.get(predicate_id)
        if precision is None:
            # Tier 3: Unmeasured risky fields are blocked
            return False
        return precision >= precision_threshold(spec.risk_class)


__all__ = [
    "AUTO_SUGGEST_CONFIDENCE",
    "CLASSIFICATION_ACCURACY_GATE",
    "PRECISION_GATE_HIGH",
    "PRECISION_GATE_LOW",
    "SAFE_FIELDS",
    "SuggestionPolicy",
    "precision_threshold",
]
