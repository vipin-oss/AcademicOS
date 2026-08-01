"""Unit tests for Update/Delete/List use cases (no framework deps required)."""
from __future__ import annotations

from app.application.commands.delete_object import DeleteObjectCommand
from app.application.commands.update_object import UpdateObjectCommand
from app.application.dtos.object import Metadata, UpdateObjectInput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.list_objects import ListObjectsQuery
from app.application.use_cases.delete_object import DeleteObjectUseCase
from app.application.use_cases.list_object import ListObjectsUseCase
from app.application.use_cases.update_object import UpdateObjectUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        obj = self._store.get(object_id)
        if obj is None:
            return []
        return obj.related_ids(kind)

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
        return out

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


def _course() -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.COURSE, "Intro to CS", created_by="faculty:1", status=ObjectStatus.ACTIVE
    )
    obj.set_metadata(
        MetadataEntry("code", "CS101", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        actor="faculty:1",
    )
    obj.pop_domain_events()
    return obj


def test_update_status_and_metadata():
    repo = InMemoryObjectRepository()
    obj = _course()
    repo.save(obj)

    out = UpdateObjectUseCase(repo).execute(
        UpdateObjectCommand(
            object_id=obj.id,
            input=UpdateObjectInput(
                updated_by="faculty:1",
                status=ObjectStatus.ARCHIVED,
                metadata=Metadata(
                    entries=(
                        MetadataEntry("note", "updated", MetadataLayer.L5_INFERRED, Provenance.INFERRED),
                    )
                ),
            ),
        )
    )
    assert out.status == "archived"
    assert out.metadata["note"] == "updated"
    assert out.metadata["code"] == "CS101"  # previous metadata preserved


def test_update_missing_object_raises():
    repo = InMemoryObjectRepository()
    try:
        UpdateObjectUseCase(repo).execute(
            UpdateObjectCommand(
                object_id=ObjectId.generate(ObjectType.COURSE),
                input=UpdateObjectInput(updated_by="faculty:1"),
            )
        )
        assert False
    except ObjectNotFoundError:
        pass


def test_delete_object():
    repo = InMemoryObjectRepository()
    obj = _course()
    repo.save(obj)
    assert repo.exists(obj.id)
    DeleteObjectUseCase(repo).execute(DeleteObjectCommand(object_id=obj.id))
    assert not repo.exists(obj.id)


def test_delete_missing_object_raises():
    repo = InMemoryObjectRepository()
    try:
        DeleteObjectUseCase(repo).execute(
            DeleteObjectCommand(object_id=ObjectId.generate(ObjectType.COURSE))
        )
        assert False
    except ObjectNotFoundError:
        pass


def test_list_pagination():
    repo = InMemoryObjectRepository()
    for i in range(5):
        o = UniversalObject.create(ObjectType.COURSE, f"Course {i}", created_by="faculty:1")
        o.pop_domain_events()
        repo.save(o)

    page1 = ListObjectsUseCase(repo).execute(ListObjectsQuery(page=1, page_size=2))
    assert page1.total_count == 5
    assert len(page1.items) == 2
    assert page1.page == 1
    assert page1.page_size == 2

    page3 = ListObjectsUseCase(repo).execute(ListObjectsQuery(page=3, page_size=2))
    assert len(page3.items) == 1  # 5 items -> pages: 2,2,1


def test_list_default_ordering_stable():
    repo = InMemoryObjectRepository()
    a = UniversalObject.create(ObjectType.COURSE, "A", created_by="f:1")
    b = UniversalObject.create(ObjectType.COURSE, "B", created_by="f:1")
    a.pop_domain_events()
    b.pop_domain_events()
    repo.save(b)
    repo.save(a)
    result = ListObjectsUseCase(repo).execute(ListObjectsQuery(page=1, page_size=10))
    # Default ordering is by id (ascending, deterministic).
    ids = [i.id for i in result.items]
    assert ids == sorted(ids)
