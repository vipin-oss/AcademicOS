"""Unit tests for graph integrity validation (Sprint-2 M3)."""
from __future__ import annotations

import pytest

from app.application.exceptions import ValidationError
from app.application.services.graph_integrity import assert_edge_targets
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


class InMemoryRepo(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}
        self._inbound: dict[str, list[str]] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[str(entity.id)] = entity
        for rel in entity.relationships:
            self._inbound.setdefault(str(rel.target), []).append(str(entity.id))

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id: ObjectId) -> bool:
        return str(id) in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(str(id), None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        return []

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return []

    def find_inbound(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return [ObjectId(i) for i in self._inbound.get(str(object_id), [])]

    def find(self, *, object_type=None, status=None, metadata_key=None,
             metadata_value=None, page=1, page_size=0, sort_by=None, order="asc"):
        return self.list()

    def count(self, *, object_type=None, status=None, metadata_key=None,
              metadata_value=None) -> int:
        return len(self.list())


def _node(repo, name="X", object_type=ObjectType.COURSE):
    obj = UniversalObject.create(object_type, name, created_by="f:1")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def test_empty_edges_pass(repo=None):
    repo = repo or InMemoryRepo()
    source = _node(repo)
    assert_edge_targets(repo, [], source_id=source.id)  # no error


def test_missing_target_rejected():
    repo = InMemoryRepo()
    source = _node(repo)
    ghost = ObjectId.generate(ObjectType.COURSE)
    with pytest.raises(ValidationError, match="not found"):
        assert_edge_targets(repo, [(ghost, None)], source_id=source.id)


def test_wrong_type_rejected():
    repo = InMemoryRepo()
    source = _node(repo)
    faculty = _node(repo, "F", ObjectType.FACULTY)
    with pytest.raises(ValidationError, match="must be a course"):
        assert_edge_targets(repo, [(faculty.id, ObjectType.COURSE)], source_id=source.id)


def test_self_loop_rejected():
    repo = InMemoryRepo()
    source = _node(repo)
    with pytest.raises(ValidationError, match="source object itself"):
        assert_edge_targets(repo, [(source.id, None)], source_id=source.id)


def test_valid_edges_pass():
    repo = InMemoryRepo()
    source = _node(repo, "S")
    a = _node(repo, "A")
    b = _node(repo, "B", ObjectType.PUBLICATION)
    assert_edge_targets(
        repo,
        [(a.id, ObjectType.COURSE), (b.id, ObjectType.PUBLICATION)],
        source_id=source.id,
    )


def test_no_type_expectation_skips_type_check():
    repo = InMemoryRepo()
    source = _node(repo)
    any_type = _node(repo, "X", ObjectType.SETTINGS)
    assert_edge_targets(repo, [(any_type.id, None)], source_id=source.id)


def test_no_inbound_edges_allows_delete():
    repo = InMemoryRepo()
    obj = _node(repo)
    assert_edge_targets(repo, [], source_id=obj.id)
    from app.application.services.graph_integrity import assert_no_inbound_edges

    assert_no_inbound_edges(repo, obj.id)  # no error


def test_inbound_edges_block_delete():
    from app.application.services.graph_integrity import assert_no_inbound_edges
    from app.domain.value_objects.enums import Provenance, RelationshipKind

    repo = InMemoryRepo()
    a = _node(repo, "A")
    b = _node(repo, "B")
    a.add_relationship(b.id, RelationshipKind.PREREQUISITE_OF, Provenance.ASSERTED)
    repo.save(a)

    with pytest.raises(ValidationError, match="referenced"):
        assert_no_inbound_edges(repo, b.id)
