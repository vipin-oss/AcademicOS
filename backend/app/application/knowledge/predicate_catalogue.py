"""Data-only claim predicate catalogue (ADR-019, extended by ADR-053).

Not a store. Not written by engines. Exists so L1 cannot invent a closed
enum of fact kinds. Unknown / unparseable values become ``raw`` plus the
source text — never dropped.

V3 M6 (ADR-053) adds the **Wave 1** predicate set — grant/sanction-letter and
office-order facts — and gives every predicate a ``unit`` and a ``risk_class``
so the M6 precision gates (high-risk >= 0.95, low-risk >= 0.85) and the
AUTO_SUGGESTED policy can reason about extraction quality. Additive only: the
three seed predicates keep their ids, versions and schemas unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Value-schema kinds understood by this data catalogue (not a DB type).
SCHEMA_MONEY = "money"
SCHEMA_TEXT = "text"
SCHEMA_DATE = "date"
SCHEMA_NUMBER = "number"
SCHEMA_RAW = "raw"

#: Risk classes (ADR-053). High-risk predicates gate at >= 0.95 measured
#: precision; low-risk at >= 0.85. A predicate below its gate can never be
#: AUTO_SUGGESTED (its extractions stay PROPOSED until a human confirms).
RISK_HIGH = "high"
RISK_LOW = "low"


@dataclass(frozen=True)
class PredicateSpec:
    predicate_id: str
    version: int
    value_schema: str
    description: str
    unit: str | None = None
    risk_class: str = RISK_LOW


def _p(
    predicate_id: str,
    value_schema: str,
    description: str,
    *,
    version: int = 1,
    unit: str | None = None,
    risk_class: str = RISK_LOW,
) -> PredicateSpec:
    return PredicateSpec(
        predicate_id, version, value_schema, description, unit, risk_class
    )


#: Wave 1 catalogue (ADR-053). Additive only; ``predicate_id`` is the
#: registry key and must stay unique.
CATALOGUE: tuple[PredicateSpec, ...] = (
    # ---- grant / sanction letters --------------------------------------
    _p("sanctioned_amount", SCHEMA_MONEY, "Amount sanctioned on a grant, letter, or order.", unit="INR", risk_class=RISK_HIGH),
    _p("principal_investigator", SCHEMA_TEXT, "Named principal investigator.", risk_class=RISK_HIGH),
    _p("co_investigator", SCHEMA_TEXT, "Named co-investigator."),
    _p("project_title", SCHEMA_TEXT, "Title of the sanctioned project."),
    _p("project_duration_months", SCHEMA_NUMBER, "Project duration in months.", unit="months"),
    _p("project_start_date", SCHEMA_DATE, "Project start date.", risk_class=RISK_HIGH),
    _p("project_end_date", SCHEMA_DATE, "Project end date.", risk_class=RISK_HIGH),
    _p("funding_agency", SCHEMA_TEXT, "Funding / sponsoring agency.", risk_class=RISK_HIGH),
    _p("scheme_name", SCHEMA_TEXT, "Scheme / programme name."),
    _p("sanction_order_number", SCHEMA_TEXT, "Sanction order number.", risk_class=RISK_HIGH),
    _p("file_number", SCHEMA_TEXT, "Government / institutional file number.", risk_class=RISK_HIGH),
    _p("sanctioned_by", SCHEMA_TEXT, "Authority that sanctioned the grant."),
    _p("overhead_amount", SCHEMA_MONEY, "Overhead component amount.", unit="INR"),
    _p("first_year_amount", SCHEMA_MONEY, "First-year release amount.", unit="INR"),
    _p("recurring_amount", SCHEMA_MONEY, "Recurring (annual) release amount.", unit="INR"),
    _p("grant_category", SCHEMA_TEXT, "Grant category (e.g. major/minor research project)."),
    # ---- office orders --------------------------------------------------
    _p("order_number", SCHEMA_TEXT, "Office order number.", risk_class=RISK_HIGH),
    _p("order_date", SCHEMA_DATE, "Office order date.", risk_class=RISK_HIGH),
    _p("subject", SCHEMA_TEXT, "Order subject line."),
    _p("issuing_authority", SCHEMA_TEXT, "Authority issuing the order.", risk_class=RISK_HIGH),
    _p("addressee", SCHEMA_TEXT, "Addressee of the order."),
    _p("effective_date", SCHEMA_DATE, "Effective date of the order.", risk_class=RISK_HIGH),
    _p("compliance_deadline", SCHEMA_DATE, "Compliance deadline stated in the order."),
    _p("purpose", SCHEMA_TEXT, "Stated purpose of the order."),
    _p("circular_number", SCHEMA_TEXT, "Circular number."),
    _p("approval_reference", SCHEMA_TEXT, "Reference to the approving authority/decision."),
    # ---- shared administrative facts ------------------------------------
    _p("issue_date", SCHEMA_DATE, "Issue or sanction date as written in the source.", risk_class=RISK_HIGH),
    _p("department", SCHEMA_TEXT, "Department the fact belongs to."),
    _p("institution", SCHEMA_TEXT, "Institution the fact belongs to."),
)

_BY_ID: dict[str, PredicateSpec] = {spec.predicate_id: spec for spec in CATALOGUE}


def get_predicate(predicate_id: str) -> PredicateSpec | None:
    return _BY_ID.get(predicate_id)


def normalize_predicate_value(
    predicate_id: str,
    raw_value: object,
    source_text: str,
) -> dict[str, object]:
    """Validate ``raw_value`` against the catalogue.

    Unknown predicates and unparseable values return
    ``{"kind": "raw", "text": source_text, "predicate_id": ...}``.
    Nothing is dropped.
    """

    spec = _BY_ID.get(predicate_id)
    if spec is None:
        return {
            "kind": SCHEMA_RAW,
            "text": source_text,
            "predicate_id": predicate_id,
            "reason": "unknown_predicate",
        }

    if spec.value_schema == SCHEMA_MONEY:
        parsed = _parse_money(raw_value)
        if parsed is None:
            return _raw(predicate_id, source_text)
        return {"kind": SCHEMA_MONEY, "amount": parsed, "predicate_id": predicate_id}

    if spec.value_schema == SCHEMA_NUMBER:
        parsed = _parse_number(raw_value)
        if parsed is None:
            return _raw(predicate_id, source_text)
        return {"kind": SCHEMA_NUMBER, "value": parsed, "predicate_id": predicate_id}

    if spec.value_schema == SCHEMA_DATE:
        text = str(raw_value).strip() if raw_value is not None else ""
        if len(text) < 4:
            return _raw(predicate_id, source_text)
        return {"kind": SCHEMA_DATE, "value": text, "predicate_id": predicate_id}

    if spec.value_schema == SCHEMA_TEXT:
        text = str(raw_value).strip() if raw_value is not None else ""
        if not text:
            return _raw(predicate_id, source_text)
        return {"kind": SCHEMA_TEXT, "value": text, "predicate_id": predicate_id}

    return _raw(predicate_id, source_text)


def _raw(predicate_id: str, source_text: str) -> dict[str, object]:
    return {
        "kind": SCHEMA_RAW,
        "text": source_text,
        "predicate_id": predicate_id,
        "reason": "unparseable",
    }


def _parse_money(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace(",", "").replace("₹", "").replace("INR", "").strip()
    # Indian letters commonly prefix amounts with "Rs" / "Rs.".
    if cleaned.lower().startswith("rs"):
        cleaned = cleaned[2:].lstrip(". ").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_number(value: object) -> float | None:
    """Parse a plain number, tolerating a trailing unit word (e.g. ``36 months``)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace(",", "").strip()
    # take the leading numeric token; ignore a trailing unit
    for end in range(len(cleaned), 0, -1):
        candidate = cleaned[:end].strip()
        try:
            return float(candidate)
        except ValueError:
            continue
    return None


__all__ = [
    "CATALOGUE",
    "RISK_HIGH",
    "RISK_LOW",
    "SCHEMA_DATE",
    "SCHEMA_MONEY",
    "SCHEMA_NUMBER",
    "SCHEMA_RAW",
    "SCHEMA_TEXT",
    "PredicateSpec",
    "get_predicate",
    "normalize_predicate_value",
]
