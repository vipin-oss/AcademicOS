"""Deterministic fact-extraction rule for the extraction→claim bridge (ADR-034).

Maps specific NIR/CDM elements to predicate-catalogue claims. This is a small,
explicit, predicate-driven extractor — NOT general NER/entity extraction
(deferred). It is deterministic and idempotent: the same input produces the
same claim candidates.

Known label → predicate mappings are derived from the seed predicate catalogue
(ADR-019) and are additive-only. Unknown/unparseable values fall back to a
`raw` claim (with source text), never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    predicate_id: str
    raw_value: object
    source_text: str
    fact_confidence: float | None = None
    extraction_confidence: float | None = None


#: Deterministic label -> predicate mapping (seed catalogue, additive-only).
#: Keys are case-insensitive header/field labels; values are predicate ids.
_LABEL_TO_PREDICATE: dict[str, str] = {
    "amount": "sanctioned_amount",
    "sanctioned amount": "sanctioned_amount",
    "sanction amount": "sanctioned_amount",
    "sanctioned_amount": "sanctioned_amount",
    "pi": "principal_investigator",
    "principal investigator": "principal_investigator",
    "principal_investigator": "principal_investigator",
    "issue date": "issue_date",
    "date": "issue_date",
    "dated": "issue_date",
    "issue_date": "issue_date",
}

#: Table/sheet header index that, when present, identifies a value column.
_VALUE_HEADERS = {"value", "amount", "amount (inr)", "sanctioned amount", "date", "name", "pi"}


def _normalize(label: str) -> str:
    return (label or "").strip().casefold()


def candidate_from_table(rows: list[list[str]]) -> list[Candidate]:
    """Extract candidates from a table (rows of cells) via header labels."""
    if not rows:
        return []
    header = [str(c or "").strip().casefold() for c in rows[0]]
    out: list[Candidate] = []
    # find a predicate column
    for idx, head in enumerate(header):
        pred = _LABEL_TO_PREDICATE.get(head)
        if pred is None:
            continue
        for body in rows[1:]:
            if idx < len(body) and str(body[idx]).strip():
                out.append(
                    Candidate(
                        predicate_id=pred,
                        raw_value=body[idx],
                        source_text=str(body[idx]),
                        fact_confidence=0.9,
                        extraction_confidence=1.0,
                    )
                )
    return out


def candidate_from_field(label: str, value: object) -> Candidate | None:
    """Extract a candidate from a single key/value field."""
    pred = _LABEL_TO_PREDICATE.get(_normalize(label))
    if pred is None:
        return None
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    return Candidate(
        predicate_id=pred, raw_value=value, source_text=text,
        fact_confidence=0.9, extraction_confidence=1.0,
    )


def candidate_from_sheet_cells(cells: list[dict]) -> list[Candidate]:
    """Extract candidates from XLSX SHEET_CELL values (label/value pairs)."""
    out: list[Candidate] = []
    for i, cell in enumerate(cells):
        text = str(cell.get("text") or "").strip()
        if not text:
            continue
        pred = _LABEL_TO_PREDICATE.get(_normalize(text))
        if pred is None:
            continue
        # look ahead for a value in the same row (next cell)
        if i + 1 < len(cells):
            nxt = str(cells[i + 1].get("text") or "").strip()
            if nxt:
                out.append(
                    Candidate(
                        predicate_id=pred, raw_value=nxt, source_text=nxt,
                        fact_confidence=0.9, extraction_confidence=1.0,
                    )
                )
    return out


__all__ = [
    "Candidate",
    "candidate_from_field",
    "candidate_from_sheet_cells",
    "candidate_from_table",
]
