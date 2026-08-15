"""L1 polymorphic span model tests (ADR-024 / ADR-003)."""

from __future__ import annotations

from app.domain.value_objects.span import Span, SpanKind


def test_page_span_roundtrip():
    span = Span(kind=SpanKind.PAGE, source_id="obj:document:1", page=2)
    data = span.to_region_dict()
    assert data["kind"] == "page"
    assert data["page"] == 2
    rebuilt = Span.from_region_dict(data)
    assert rebuilt == span
    assert span.region_label == "page 2"


def test_bbox_span_roundtrip():
    span = Span(
        kind=SpanKind.BBOX,
        source_id="obj:document:1",
        bbox=(10.0, 20.0, 100.0, 200.0),
    )
    data = span.to_region_dict()
    assert list(data["bbox"]) == [10.0, 20.0, 100.0, 200.0]
    rebuilt = Span.from_region_dict(data)
    assert rebuilt.bbox == (10.0, 20.0, 100.0, 200.0)


def test_table_cell_span():
    span = Span(
        kind=SpanKind.TABLE_CELL,
        source_id="obj:document:1",
        table_id="t1",
        row_idx=0,
        col_idx=1,
    )
    assert span.region_label == "table t1 cell 0:1"
    data = span.to_region_dict()
    assert data["row_idx"] == 0 and data["col_idx"] == 1


def test_equation_and_slide_kinds():
    eq = Span(kind=SpanKind.EQUATION, source_id="obj:document:1", block_id="b1")
    assert eq.kind is SpanKind.EQUATION
    slide = Span(kind=SpanKind.SLIDE, source_id="obj:document:1", slide=4)
    assert slide.region_label == "slide 4"


def test_not_page_universal():
    # a spreadsheet cell and an image region are first-class, not pages
    assert SpanKind.SPREADSHEET_CELL.value == "spreadsheet_cell"
    assert SpanKind.IMAGE_REGION.value == "image_region"
    assert SpanKind.DIAGRAM.value == "diagram"
