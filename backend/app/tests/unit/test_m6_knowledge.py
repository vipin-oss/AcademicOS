"""V3 M6 knowledge-plane data tests (ADR-053): predicate catalogue Wave 1,
document types, extraction templates."""

from __future__ import annotations

from app.application.knowledge.document_types import DOCUMENT_TYPES, get_document_type
from app.application.knowledge.extraction_templates import (
    EXTRACTION_TEMPLATES,
    template_predicates,
)
from app.application.knowledge.predicate_catalogue import (
    CATALOGUE,
    RISK_HIGH,
    RISK_LOW,
    SCHEMA_MONEY,
    SCHEMA_NUMBER,
    SCHEMA_TEXT,
    get_predicate,
    normalize_predicate_value,
)


def test_catalogue_is_additive_and_versioned() -> None:
    ids = [spec.predicate_id for spec in CATALOGUE]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 28  # Wave 1 (was 3)
    assert all(spec.version >= 1 for spec in CATALOGUE)


def test_every_predicate_has_risk_class_and_schema() -> None:
    for spec in CATALOGUE:
        assert spec.risk_class in (RISK_HIGH, RISK_LOW), spec
        assert spec.value_schema in (SCHEMA_MONEY, SCHEMA_TEXT, "date", SCHEMA_NUMBER), spec


def test_seed_predicates_kept_with_high_risk() -> None:
    assert get_predicate("sanctioned_amount").risk_class == RISK_HIGH
    assert get_predicate("principal_investigator").risk_class == RISK_HIGH
    assert get_predicate("issue_date").risk_class == RISK_HIGH


def test_money_predicate_has_unit() -> None:
    assert get_predicate("sanctioned_amount").unit == "INR"


def test_number_schema_normalizes() -> None:
    result = normalize_predicate_value("project_duration_months", "36 months", "36 months")
    assert result["kind"] == SCHEMA_NUMBER
    assert result["value"] == 36.0


def test_money_parses_rs_prefix() -> None:
    result = normalize_predicate_value("sanctioned_amount", "Rs. 50,00,000", "Rs. 50,00,000")
    assert result["kind"] == SCHEMA_MONEY
    assert result["amount"] == 5000000.0


def test_document_types_are_data() -> None:
    assert {t.type_id for t in DOCUMENT_TYPES} == {"grant_sanction_letter", "office_order"}
    assert get_document_type("grant_sanction_letter") is not None
    assert get_document_type("unknown") is None


def test_templates_reference_only_known_predicates() -> None:
    known = {spec.predicate_id for spec in CATALOGUE}
    for template in EXTRACTION_TEMPLATES:
        assert template.document_type_id in {t.type_id for t in DOCUMENT_TYPES}
        assert set(template.predicate_ids) <= known, template.template_id


def test_template_predicates_returns_empty_for_unknown() -> None:
    assert template_predicates("grant_sanction_letter")
    assert template_predicates("no_such_type") == ()
