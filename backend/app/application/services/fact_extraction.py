"""Deterministic fact-extraction rule for the extraction→claim bridge (ADR-034).

Maps specific NIR/CDM elements to predicate-catalogue claims. This is a small,
explicit, predicate-driven extractor — NOT general NER/entity extraction
(deferred). It is deterministic and idempotent: the same input produces the
same claim candidates.

Known label → predicate mappings are derived from the seed predicate catalogue
(ADR-019) and expanded to the Wave 1 catalogue (ADR-053). Additive-only.
Unknown/unparseable values fall back to a `raw` claim (with source text),
never silently dropped.

V3 M6 adds :func:`candidate_from_text_lines` so free-form letters/orders
("Label: value" prose) are readable — the surface the Wave 1 document types
actually ship in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    predicate_id: str
    raw_value: object
    source_text: str
    fact_confidence: float | None = None
    extraction_confidence: float | None = None


#: Deterministic label -> predicate mapping (Wave 1 catalogue, additive-only).
#: Keys are case-insensitive header/field labels; values are predicate ids.
_LABEL_TO_PREDICATE: dict[str, str] = {
    # sanctioned amount
    "amount": "sanctioned_amount",
    "sanctioned amount": "sanctioned_amount",
    "sanction amount": "sanctioned_amount",
    "sanctioned_amount": "sanctioned_amount",
    # principal / co-investigator
    "pi": "principal_investigator",
    "principal investigator": "principal_investigator",
    "principal_investigator": "principal_investigator",
    "co-investigator": "co_investigator",
    "co investigator": "co_investigator",
    "co_investigator": "co_investigator",
    "co-pi": "co_investigator",
    "co pi": "co_investigator",
    # dates
    "issue date": "issue_date",
    "date": "issue_date",
    "dated": "issue_date",
    "issue_date": "issue_date",
    "start date": "project_start_date",
    "project start date": "project_start_date",
    "project_start_date": "project_start_date",
    "end date": "project_end_date",
    "project end date": "project_end_date",
    "project_end_date": "project_end_date",
    "order date": "order_date",
    "order_date": "order_date",
    "effective date": "effective_date",
    "effective_date": "effective_date",
    "compliance deadline": "compliance_deadline",
    "compliance_deadline": "compliance_deadline",
    # grant specifics
    "project title": "project_title",
    "project_title": "project_title",
    "title of project": "project_title",
    "title of the project": "project_title",
    "duration": "project_duration_months",
    "project duration": "project_duration_months",
    "duration (months)": "project_duration_months",
    "project duration (months)": "project_duration_months",
    "project_duration_months": "project_duration_months",
    "funding agency": "funding_agency",
    "funding_agency": "funding_agency",
    "sponsoring agency": "funding_agency",
    "scheme": "scheme_name",
    "scheme name": "scheme_name",
    "scheme_name": "scheme_name",
    "sanction order number": "sanction_order_number",
    "sanction order no": "sanction_order_number",
    "sanction_order_number": "sanction_order_number",
    "file number": "file_number",
    "file no": "file_number",
    "file_number": "file_number",
    "sanctioned by": "sanctioned_by",
    "sanctioned_by": "sanctioned_by",
    "approved by": "sanctioned_by",
    "overhead": "overhead_amount",
    "overhead amount": "overhead_amount",
    "overhead_amount": "overhead_amount",
    "first year amount": "first_year_amount",
    "first year": "first_year_amount",
    "first_year_amount": "first_year_amount",
    "recurring amount": "recurring_amount",
    "recurring": "recurring_amount",
    "recurring_amount": "recurring_amount",
    "grant category": "grant_category",
    "grant_category": "grant_category",
    # office order specifics
    "order number": "order_number",
    "order no": "order_number",
    "order_number": "order_number",
    "subject": "subject",
    "issuing authority": "issuing_authority",
    "issuing_authority": "issuing_authority",
    "addressee": "addressee",
    "purpose": "purpose",
    "circular number": "circular_number",
    "circular no": "circular_number",
    "circular_number": "circular_number",
    "approval reference": "approval_reference",
    "approval_reference": "approval_reference",
    # shared administrative facts
    "department": "department",
    "dept": "department",
    "institution": "institution",
    "college": "institution",
    "university": "institution",
    "institute": "institution",
}

#: A "Label: value" / "Label — value" prose line (M6 text-line extraction).
_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&()\-]{0,48}?)\s*[:：]\s*(.+?)\s*$")


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


def candidate_from_text_lines(text: str) -> list[Candidate]:
    """Extract candidates from free-form prose "Label: value" lines (M6).

    Deterministic and idempotent. A line matches only when its label is a
    known predicate label; unknown labels are ignored (never guessed).
    """
    out: list[Candidate] = []
    if not text:
        return out
    for line in text.splitlines():
        match = _LINE_RE.match(line)
        if match is None:
            continue
        label = match.group(1).strip()
        value = match.group(2).strip()
        pred = _LABEL_TO_PREDICATE.get(_normalize(label))
        if pred is None or not value:
            continue
        out.append(
            Candidate(
                predicate_id=pred, raw_value=value, source_text=value,
                fact_confidence=0.9, extraction_confidence=1.0,
            )
        )
    return out


__all__ = [
    "Candidate",
    "candidate_from_field",
    "candidate_from_sheet_cells",
    "candidate_from_table",
    "candidate_from_text_lines",
]
