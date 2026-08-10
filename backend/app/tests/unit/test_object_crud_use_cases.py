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

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
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
    def find_inbound(
        self, object_id: ObjectId, kind=None
    ) -> list[ObjectId]:
        return [
            o.id
            for o in self._store.values()
            if any(r.target == object_id and (kind is None or r.kind == kind) for r in o.relationships)
        ]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        if page < 1:
            raise ValueError("page must be >= 1.")
        if page_size < 0:
            raise ValueError("page_size must be >= 0.")
        if sort_by is not None and sort_by not in (
            "id", "object_type", "title", "title_ci", "status", "version",
        ):
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
        if order not in ("asc", "desc"):
            raise ValueError(f"Unsupported order: {order!r}")

        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    (value := o.metadata.get_value(metadata_key)) is not None
                    and (metadata_value is None or value == metadata_value)
                )
            )
        ]
        effective_sort = sort_by if sort_by is not None else ("id" if page_size > 0 else None)
        if effective_sort is not None:
            reverse = order == "desc"
            if effective_sort == "id":
                items.sort(key=lambda o: str(o.id), reverse=reverse)
            elif effective_sort == "object_type":
                items.sort(key=lambda o: o.object_type.value, reverse=reverse)
            elif effective_sort in ("title", "title_ci"):
                items.sort(key=lambda o: o.title, reverse=reverse)
            elif effective_sort == "status":
                items.sort(key=lambda o: o.status.value, reverse=reverse)
            elif effective_sort == "version":
                items.sort(key=lambda o: o.version, reverse=reverse)
        if page_size > 0:
            start = (page - 1) * page_size
            items = items[start : start + page_size]
        return items

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        return len(
            self.find(
                object_type=object_type,
                status=status,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            )
        )


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
