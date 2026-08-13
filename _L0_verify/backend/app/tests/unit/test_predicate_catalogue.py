"""ADR-019 data catalogue: additive, unknown → raw, never dropped."""

from __future__ import annotations

from app.application.knowledge.predicate_catalogue import (
    CATALOGUE,
    normalize_predicate_value,
)


def test_seed_catalogue_has_versioned_ids():
    assert CATALOGUE
    ids = [spec.predicate_id for spec in CATALOGUE]
    assert len(ids) == len(set(ids))
    assert all(spec.version >= 1 for spec in CATALOGUE)
    assert all(spec.predicate_id and spec.value_schema for spec in CATALOGUE)


def test_unknown_predicate_is_kept_as_raw_with_source_text():
    result = normalize_predicate_value(
        "exam_date",
        "12 March 2026",
        source_text="The examination will be held on 12 March 2026.",
    )
    assert result["kind"] == "raw"
    assert result["predicate_id"] == "exam_date"
    assert "12 March 2026" in str(result["text"])


def test_unparseable_known_predicate_is_raw_not_dropped():
    result = normalize_predicate_value(
        "sanctioned_amount",
        "not-a-number",
        source_text="sanctioned amount as written: not-a-number",
    )
    assert result["kind"] == "raw"
    assert result["predicate_id"] == "sanctioned_amount"
    assert result["text"]


def test_parseable_money_is_not_raw():
    result = normalize_predicate_value(
        "sanctioned_amount",
        "10,00,000",
        source_text="sanctioned Rs 10,00,000",
    )
    assert result["kind"] == "money"
    assert result["amount"] == 1000000.0


def test_adding_a_predicate_does_not_change_a_schema_constant():
    """The catalogue is a tuple of specs — not a DB enum / schema version."""

    assert isinstance(CATALOGUE, tuple)
    # Shape of a catalogue entry is fixed; length may grow additively later.
    first = CATALOGUE[0]
    assert hasattr(first, "predicate_id")
    assert hasattr(first, "version")
    assert hasattr(first, "value_schema")
