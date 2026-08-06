"""Unit tests for the Citation Builder (Sprint-6 M3 Phase 3).

Deterministic numbering, deduplication, stable identifiers, preserved
ordering and evidence-card rendering — all from retrieval facts only.
"""
from __future__ import annotations

from app.application.assistant.citations import CitationBuilder
from app.application.dtos.assistant import RetrievedItem


def _item(object_id: str, title: str, sources=("search",), version=1, score=0.1,
          object_type="document") -> RetrievedItem:
    return RetrievedItem(
        object_id=object_id, object_type=object_type, title=title,
        version=version, sources=sources, score=score,
    )


def test_deterministic_numbering_in_retrieval_order():
    items = (
        _item("obj:document:B", "Beta"),
        _item("obj:document:A", "Alpha"),
        _item("obj:document:C", "Gamma"),
    )
    citations = CitationBuilder().build(items)
    assert [(c.number, c.object_id) for c in citations] == [
        (1, "obj:document:B"),
        (2, "obj:document:A"),
        (3, "obj:document:C"),
    ]


def test_duplicates_are_removed_keeping_first():
    items = (
        _item("obj:document:A", "Alpha v1", version=1),
        _item("obj:document:A", "Alpha v2", version=2),
        _item("obj:document:B", "Beta"),
    )
    citations = CitationBuilder().build(items)
    assert [c.object_id for c in citations] == ["obj:document:A", "obj:document:B"]
    assert citations[0].version == 1  # first occurrence kept
    assert citations[1].number == 2  # renumbered contiguously


def test_stable_ids_across_runs():
    items = (
        _item("obj:document:A", "Alpha"),
        _item("obj:document:B", "Beta"),
    )
    builder = CitationBuilder()
    assert builder.build(items) == builder.build(items)
    assert [c.object_id for c in builder.build(items)] == [
        "obj:document:A",
        "obj:document:B",
    ]


def test_citation_carries_only_retrieval_facts():
    item = _item("obj:document:A", "Alpha", sources=("search", "graph"), version=3, score=0.5)
    citation = CitationBuilder().build([item])[0]
    assert citation.object_id == item.object_id
    assert citation.object_type == item.object_type
    assert citation.title == item.title
    assert citation.sources == item.sources
    assert citation.version == item.version
    assert citation.score == item.score
    assert citation.number == 1


def test_empty_retrieval_yields_no_citations():
    assert CitationBuilder().build([]) == ()


def test_evidence_cards_reuse_shared_hrefs():
    citations = CitationBuilder().build(
        (_item("obj:document:A", "Alpha"), _item("obj:course:C", "Course", object_type="course"))
    )
    cards = CitationBuilder().evidence_cards(citations)
    assert len(cards) == 2
    assert cards[0].object_id == "obj:document:A"
    assert cards[0].href == "/documents/obj:document:A"
    assert cards[1].href == "/teaching/classes/obj:course:C"
    assert cards[0].subtitle == "document"


def test_cards_keep_citation_order():
    citations = CitationBuilder().build(
        (_item("obj:document:B", "Beta"), _item("obj:document:A", "Alpha"))
    )
    cards = CitationBuilder().evidence_cards(citations)
    assert [c.object_id for c in cards] == ["obj:document:B", "obj:document:A"]
