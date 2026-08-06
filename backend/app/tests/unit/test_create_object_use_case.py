"""Unit tests for the Create Universal Object vertical slice.

No infrastructure is used: a fake in-memory repository implements the abstract
``ObjectRepository`` port, proving the Application layer works against the port
alone. This is exactly what "depend only on app.domain" requires.
"""
from __future__ import annotations

import pytest

from app.application.commands.create_object import CreateObjectCommand
from app.application.dtos.object import CreateObjectInput, CreateObjectOutput
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_object import GetObjectQuery
from app.application.use_cases.create_object import CreateObjectUseCase
from app.application.use_cases.get_object import GetObjectUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    """Test double implementing the abstract port. No DB, no framework."""

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

    def find_related(
        self, object_id: ObjectId, kind=None
    ) -> list[ObjectId]:
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

    def find_by_metadata(
        self, key: str, value: str | None = None
    ) -> list[UniversalObject]:
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
            "id", "object_type", "title", "status", "version",
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
            elif effective_sort == "title":
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



def _input(**overrides) -> CreateObjectInput:
    data = dict(
        object_type=ObjectType.COURSE,
        title="Introduction to Machine Learning",
        created_by="faculty:1",
        status=ObjectStatus.DRAFT,
    )
    data.update(overrides)
    return CreateObjectInput(**data)


def test_create_object_happy_path():
    repo = InMemoryObjectRepository()
    out = CreateObjectUseCase(repo).execute(CreateObjectCommand(input=_input()))

    assert isinstance(out, CreateObjectOutput)
    assert out.object_type == "course"
    assert out.title == "Introduction to Machine Learning"
    assert out.status == "draft"
    assert out.version == 1
    assert "ObjectCreated" in out.events
    # Persisted via the repository interface
    assert repo.exists(ObjectId.parse(out.id))


def test_create_object_validation_error():
    repo = InMemoryObjectRepository()
    with pytest.raises(ValidationError):
        CreateObjectUseCase(repo).execute(
            CreateObjectCommand(input=_input(title="   "))
        )


def test_create_object_conflict_guard():
    repo = InMemoryObjectRepository()
    oid = ObjectId.generate(ObjectType.COURSE)
    CreateObjectUseCase(repo).execute(
        CreateObjectCommand(input=_input(object_id=oid))
    )
    with pytest.raises(ObjectAlreadyExistsError):
        CreateObjectUseCase(repo).execute(
            CreateObjectCommand(input=_input(object_id=oid))
        )


def test_create_object_metadata_roundtrip():
    repo = InMemoryObjectRepository()
    meta = Metadata(
        entries=(
            MetadataEntry(
                "doi", "10.1000/ml101", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
            ),
        )
    )
    out = CreateObjectUseCase(repo).execute(
        CreateObjectCommand(input=_input(metadata=meta))
    )
    got = GetObjectUseCase(repo).execute(
        GetObjectQuery(object_id=ObjectId.parse(out.id))
    )
    assert got.metadata.get("doi") == "10.1000/ml101"


def test_get_object_after_create():
    repo = InMemoryObjectRepository()
    out = CreateObjectUseCase(repo).execute(CreateObjectCommand(input=_input()))
    got = GetObjectUseCase(repo).execute(
        GetObjectQuery(object_id=ObjectId.parse(out.id))
    )
    assert got.id == out.id
    assert got.title == out.title


def test_get_object_not_found():
    repo = InMemoryObjectRepository()
    with pytest.raises(ObjectNotFoundError):
        GetObjectUseCase(repo).execute(
            GetObjectQuery(object_id=ObjectId.generate(ObjectType.COURSE))
        )
