"""Unit tests for the API<->Application mapper (no framework deps required)."""
from __future__ import annotations

from app.api.mappers.object_mapper import to_create_input, to_response
from app.application.dtos.object import CreateObjectOutput
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)


def test_to_create_input_basic():
    inp = to_create_input(object_type="course", title="Intro", created_by="faculty:1")
    assert inp.object_type == ObjectType.COURSE
    assert inp.title == "Intro"
    assert inp.created_by == "faculty:1"
    assert inp.status == ObjectStatus.DRAFT
    assert inp.metadata is None


def test_to_create_input_with_metadata():
    inp = to_create_input(
        object_type="publication",
        title="Paper",
        created_by="faculty:2",
        status="active",
        metadata=[{"key": "doi", "value": "10.x", "layer": 6, "source": "asserted"}],
    )
    assert inp.metadata is not None
    assert inp.metadata.get_value("doi") == "10.x"
    entry = inp.metadata.entries[0]
    assert entry.layer == MetadataLayer.L6_HUMAN_ASSERTED
    assert entry.source == Provenance.ASSERTED


def test_to_create_input_invalid_type_raises():
    try:
        to_create_input(object_type="not_a_type", title="x", created_by="f")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_to_response_maps_output():
    out = CreateObjectOutput(
        id="obj:course:123",
        object_type="course",
        title="Intro",
        status="draft",
        version=1,
        created_by="faculty:1",
        created_at="2024-01-01T00:00:00+00:00",
        metadata={"code": "CS101"},
        events=["ObjectCreated"],
    )
    d = to_response(out)
    assert d["id"] == "obj:course:123"
    assert d["metadata"] == {"code": "CS101"}
    assert d["events"] == ["ObjectCreated"]
