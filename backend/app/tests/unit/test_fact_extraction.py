"""L3 deterministic fact-extraction rule tests (ADR-034)."""

from __future__ import annotations

from app.application.services.fact_extraction import (
    candidate_from_field,
    candidate_from_sheet_cells,
    candidate_from_table,
)


def test_table_header_amount_maps_to_sanctioned_amount():
    rows = [["Amount", "Details"], ["1000", "grant"], ["2000", "letter"]]
    cands = candidate_from_table(rows)
    assert len(cands) == 2
    assert all(c.predicate_id == "sanctioned_amount" for c in cands)
    assert cands[0].raw_value == "1000"


def test_table_pi_maps_to_principal_investigator():
    rows = [["PI", "Project"], ["Dr. Nair", "Quantum"]]
    cands = candidate_from_table(rows)
    assert len(cands) == 1
    assert cands[0].predicate_id == "principal_investigator"
    assert cands[0].raw_value == "Dr. Nair"


def test_unknown_label_no_candidate():
    rows = [["Random", "Value"], ["a", "b"]]
    assert candidate_from_table(rows) == []


def test_field_mapping():
    cand = candidate_from_field("issue_date", "2026-08-13")
    assert cand is not None and cand.predicate_id == "issue_date"
    assert candidate_from_field("unknown_field", "x") is None


def test_sheet_cells_label_value_pair():
    cells = [{"text": "Amount"}, {"text": "5000"}, {"text": "Name"}, {"text": "Dr X"}]
    cands = candidate_from_sheet_cells(cells)
    assert any(c.predicate_id == "sanctioned_amount" and c.raw_value == "5000" for c in cands)
