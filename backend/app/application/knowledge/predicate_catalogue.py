"""Data-only claim predicate catalogue (ADR-019).

Not a store. Not written by engines. Exists so L1 cannot invent a closed
enum of fact kinds. Unknown / unparseable values become ``raw`` plus the
source text — never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass


#: Value-schema kinds understood by this data catalogue (not a DB type).
SCHEMA_MONEY = "money"
SCHEMA_TEXT = "text"
SCHEMA_DATE = "date"
SCHEMA_RAW = "raw"


@dataclass(frozen=True)
class PredicateSpec:
    predicate_id: str
    version: int
    value_schema: str
    description: str


#: Seed entries from the Freeze Contract's examples. Additive only.
CATALOGUE: tuple[PredicateSpec, ...] = (
    PredicateSpec(
        "sanctioned_amount",
        1,
        SCHEMA_MONEY,
        "Amount sanctioned on a grant, letter, or order.",
    ),
    PredicateSpec(
        "principal_investigator",
        1,
        SCHEMA_TEXT,
        "Named principal investigator.",
    ),
    PredicateSpec(
        "issue_date",
        1,
        SCHEMA_DATE,
        "Issue or sanction date as written in the source.",
    ),
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
            return {
                "kind": SCHEMA_RAW,
                "text": source_text,
                "predicate_id": predicate_id,
                "reason": "unparseable",
            }
        return {"kind": SCHEMA_MONEY, "amount": parsed, "predicate_id": predicate_id}

    if spec.value_schema == SCHEMA_DATE:
        text = str(raw_value).strip() if raw_value is not None else ""
        if len(text) < 4:
            return {
                "kind": SCHEMA_RAW,
                "text": source_text,
                "predicate_id": predicate_id,
                "reason": "unparseable",
            }
        return {"kind": SCHEMA_DATE, "value": text, "predicate_id": predicate_id}

    if spec.value_schema == SCHEMA_TEXT:
        text = str(raw_value).strip() if raw_value is not None else ""
        if not text:
            return {
                "kind": SCHEMA_RAW,
                "text": source_text,
                "predicate_id": predicate_id,
                "reason": "unparseable",
            }
        return {"kind": SCHEMA_TEXT, "value": text, "predicate_id": predicate_id}

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
    try:
        return float(cleaned)
    except ValueError:
        return None
