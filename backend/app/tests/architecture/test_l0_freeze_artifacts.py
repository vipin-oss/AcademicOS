"""L0 freeze artifacts must be present and say the right laws."""

from __future__ import annotations

from pathlib import Path

from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_freeze_contract_is_present():
    path = ARCH / "AcademicOS_Final_Audit_Freeze_Contract.md"
    text = path.read_text(encoding="utf-8")
    assert "ADR-019" in text
    assert "ADR-020" in text
    assert "ADR-021" in text
    assert "ADR-022" in text
    assert "1M" in text
    assert "PART 13" in text


def test_adr_020_is_present():
    text = (ARCH / "adr" / "ADR-020-planner-failure-semantics.md").read_text(
        encoding="utf-8"
    )
    assert "fast-path" in text
    assert "clarify" in text
    assert "refuse" in text
    assert "regex" in text.lower()


def test_adr019_states_registry_not_enum():
    text = (ARCH / "adr" / "ADR-019-extensible-claim-predicates.md").read_text(
        encoding="utf-8"
    )
    assert "predicate_id" in text
    assert "registry" in text.lower()
    assert "raw" in text
    assert "enum" in text.lower()


def test_adr021_states_supersede_not_merge():
    text = (ARCH / "adr" / "ADR-021-file-version-supersession.md").read_text(
        encoding="utf-8"
    )
    assert "supersede" in text.lower()
    assert "merge" in text.lower()
    assert "delete" in text.lower()


def test_adr022_states_openapi_required():
    text = (ARCH / "adr" / "ADR-022-api-contract-freeze.md").read_text(encoding="utf-8")
    assert "OpenAPI" in text


def test_adr020_states_failure_chain():
    text = (ARCH / "adr" / "ADR-020-planner-failure-semantics.md").read_text(
        encoding="utf-8"
    )
    assert "fast-path" in text
    assert "clarify" in text
    assert "refuse" in text


def test_levels_register_lists_l0_through_l15():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    for level in range(16):
        assert f"L{level}" in text


def test_capability_registry_is_exactly_the_frozen_18():
    expected = (
        "inventory",
        "lookup",
        "list",
        "search",
        "count",
        "filter",
        "summarize",
        "compare",
        "aggregate",
        "timeline",
        "document_qa",
        "relationship",
        "cross_domain",
        "absence",
        "temporal",
        "navigate",
        "clarify",
        "refuse",
    )
    assert FROZEN_CAPABILITY_IDS == expected


def test_open_decisions_remain_undecided():
    text = (ARCH / "OPEN_DECISIONS.md").read_text(encoding="utf-8")
    for qid in [f"Q{i}" for i in range(1, 11)]:
        assert qid in text
    # Each currently-open Q must still say "undecided" (Q5 resolved at L9 via
    # ADR-047; Q2 resolved at V3 M4 via ADR-052 — both by ADR, never by code).
    assert text.lower().count("undecided") >= 9


def test_scale_law_forbids_unmeasured_infra():
    text = (ARCH / "SCALE_LAW.md").read_text(encoding="utf-8")
    assert "1M" in text
    assert "Kafka" in text
    assert "Elasticsearch" in text
    assert "Temporal" in text
    assert "measured evidence" in text


def test_readme_points_at_freeze_path():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "docs/architecture/" in readme


def test_adr_register_preserves_repo_adr001():
    text = (ARCH / "adr" / "README.md").read_text(encoding="utf-8")
    assert "AI Core" in text
    numbering = (ARCH / "adr" / "NUMBERING.md").read_text(encoding="utf-8")
    assert "Do not rename" in numbering or "do not rename" in numbering.lower()
    assert "source identity" in numbering.lower()
