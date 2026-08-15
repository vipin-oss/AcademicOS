"""Unit tests for the Document use cases (no framework deps required).

Mirrors ``test_object_crud_use_cases.py``: an in-memory ``ObjectRepository``
plus a fake ``FileStorage`` exercise the full slice without any database,
filesystem, or HTTP.
"""
from __future__ import annotations

from app.application.commands.create_document import CreateDocumentCommand
from app.application.commands.delete_document import DeleteDocumentCommand
from app.application.commands.update_document import UpdateDocumentCommand
from app.application.dtos.document import CreateDocumentInput, UpdateDocumentInput
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_document import GetDocumentQuery
from app.application.queries.list_documents import ListDocumentsQuery
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
from app.application.use_cases.documents.get_document import GetDocumentUseCase
from app.application.use_cases.documents.list_documents import ListDocumentsUseCase
from app.application.use_cases.documents.update_document import UpdateDocumentUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
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


class InMemoryFileStorage(FileStorage):
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self._blobs[key] = content

    def read(self, key: str) -> bytes:
        return self._blobs[key]

    def exists(self, key: str) -> bool:
        return key in self._blobs

    def delete(self, key: str) -> None:
        self._blobs.pop(key, None)


def _course(repo: InMemoryObjectRepository) -> UniversalObject:
    course = UniversalObject.create(ObjectType.COURSE, "Intro to CS", created_by="faculty:1")
    course.pop_domain_events()
    repo.save(course)
    return course


def _upload(
    repo: InMemoryObjectRepository,
    storage: InMemoryFileStorage,
    *,
    title: str = "CS101 Syllabus",
    object_id: ObjectId | None = None,
    tags: tuple[str, ...] = ("syllabus",),
) -> object:
    return CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title=title,
                document_type="pdf",
                uploaded_by="faculty:1",
                file_name="syllabus.pdf",
                file_size=11,
                mime_type="application/pdf",
                content=b"%PDF-sample",
                object_id=object_id,
                description="Course syllabus",
                tags=tags,
            )
        )
    )


def test_upload_document_stores_file_and_projects_fields():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = _upload(repo, storage)

    assert out.id.startswith("obj:document:")
    assert out.title == "CS101 Syllabus"
    assert out.status == "draft"
    assert out.document_type == "pdf"
    assert out.description == "Course syllabus"
    assert out.tags == ["syllabus"]
    assert out.file_name == "syllabus.pdf"
    assert out.file_size == 11
    assert out.mime_type == "application/pdf"
    assert out.uploaded_by == "faculty:1"
    assert "ObjectCreated" in out.events
    # Blob stored under the key recorded in metadata.
    assert out.file_path is not None
    assert storage.read(out.file_path) == b"%PDF-sample"


def test_upload_document_linked_to_object_denormalises_title():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    course = _course(repo)
    out = _upload(repo, storage, object_id=course.id)

    assert out.object_id == str(course.id)
    assert out.object_title == "Intro to CS"
    assert out.object_type == "course"
    assert "RelationshipAdded" in out.events


def test_upload_document_with_missing_object_is_rejected():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    ghost = ObjectId.generate(ObjectType.COURSE)
    try:
        _upload(repo, storage, object_id=ghost)
        assert False
    except ValidationError:
        pass


def test_upload_document_rejects_bad_type_and_empty_title():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    for field, value in (("document_type", "bogus"), ("title", "  "), ("uploaded_by", "")):
        payload = {
            "title": "Doc",
            "document_type": "pdf",
            "uploaded_by": "faculty:1",
            "file_name": "a.pdf",
            "file_size": 1,
            "mime_type": "application/pdf",
            "content": b"x",
        }
        payload[field] = value
        try:
            CreateDocumentUseCase(repo, storage).execute(
                CreateDocumentCommand(input=CreateDocumentInput(**payload))
            )
            assert False, f"expected ValidationError for {field}={value!r}"
        except ValidationError:
            pass


def test_get_document_and_not_found():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = _upload(repo, storage)

    got = GetDocumentUseCase(repo).execute(GetDocumentQuery(object_id=ObjectId(out.id)))
    assert got.title == "CS101 Syllabus"

    try:
        GetDocumentUseCase(repo).execute(
            GetDocumentQuery(object_id=ObjectId.generate(ObjectType.DOCUMENT))
        )
        assert False
    except ObjectNotFoundError:
        pass


def test_get_document_hides_non_document_objects():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    course = _course(repo)
    try:
        GetDocumentUseCase(repo).execute(GetDocumentQuery(object_id=course.id))
        assert False
    except ObjectNotFoundError:
        pass


def test_list_documents_pagination_and_object_filter():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    course = _course(repo)
    for i in range(5):
        _upload(repo, storage, title=f"Doc {i}", object_id=course.id if i < 3 else None)

    page1 = ListDocumentsUseCase(repo).execute(ListDocumentsQuery(page=1, page_size=2))
    assert page1.total_count == 5
    assert len(page1.items) == 2

    linked = ListDocumentsUseCase(repo).execute(
        ListDocumentsQuery(page=1, page_size=100, object_id=course.id)
    )
    assert linked.total_count == 3
    assert all(item.object_id == str(course.id) for item in linked.items)

    # Non-document objects never appear in the listing.
    assert all(item.id.startswith("obj:document:") for item in page1.items)


def test_update_document_renames_and_changes_metadata():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = _upload(repo, storage)

    updated = UpdateDocumentUseCase(repo).execute(
        UpdateDocumentCommand(
            object_id=ObjectId(out.id),
            input=UpdateDocumentInput(
                actor="faculty:1",
                title="CS101 Syllabus v2",
                description="Updated",
                tags=("syllabus", "fall-2026"),
                status=ObjectStatus.ACTIVE,
            ),
        )
    )
    assert updated.title == "CS101 Syllabus v2"
    assert updated.status == "active"
    assert updated.description == "Updated"
    assert updated.tags == ["syllabus", "fall-2026"]
    assert updated.version > out.version
    assert updated.updated_at is not None
    assert "ObjectRenamed" in updated.events
    assert "ObjectStatusChanged" in updated.events


def test_update_document_link_unlink_round_trip():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    course = _course(repo)
    out = _upload(repo, storage)
    assert out.object_id is None

    # Absent field leaves the link untouched.
    untouched = UpdateDocumentUseCase(repo).execute(
        UpdateDocumentCommand(
            object_id=ObjectId(out.id), input=UpdateDocumentInput(actor="faculty:1")
        )
    )
    assert untouched.object_id is None

    linked = UpdateDocumentUseCase(repo).execute(
        UpdateDocumentCommand(
            object_id=ObjectId(out.id),
            input=UpdateDocumentInput(
                actor="faculty:1", object_id=course.id, object_id_provided=True
            ),
        )
    )
    assert linked.object_id == str(course.id)

    unlinked = UpdateDocumentUseCase(repo).execute(
        UpdateDocumentCommand(
            object_id=ObjectId(out.id),
            input=UpdateDocumentInput(actor="faculty:1", object_id=None, object_id_provided=True),
        )
    )
    assert unlinked.object_id is None


def test_update_document_obeys_lifecycle_rules():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = _upload(repo, storage)

    # draft -> superseded is an illegal transition, enforced by the domain.
    from app.domain.exceptions import InvalidStateTransitionError

    try:
        UpdateDocumentUseCase(repo).execute(
            UpdateDocumentCommand(
                object_id=ObjectId(out.id),
                input=UpdateDocumentInput(
                    actor="faculty:1", status=ObjectStatus.SUPERSEDED
                ),
            )
        )
        assert False
    except (ValidationError, InvalidStateTransitionError):
        pass


def test_update_missing_document_raises():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    try:
        UpdateDocumentUseCase(repo).execute(
            UpdateDocumentCommand(
                object_id=ObjectId.generate(ObjectType.DOCUMENT),
                input=UpdateDocumentInput(actor="faculty:1"),
            )
        )
        assert False
    except ObjectNotFoundError:
        pass


def test_delete_document_removes_aggregate_and_blob():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = _upload(repo, storage)
    assert out.file_path is not None and storage.exists(out.file_path)

    DeleteDocumentUseCase(repo, storage).execute(
        DeleteDocumentCommand(object_id=ObjectId(out.id))
    )
    assert not repo.exists(ObjectId(out.id))
    assert not storage.exists(out.file_path)


def test_delete_missing_document_raises():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    try:
        DeleteDocumentUseCase(repo, storage).execute(
            DeleteDocumentCommand(object_id=ObjectId.generate(ObjectType.DOCUMENT))
        )
        assert False
    except ObjectNotFoundError:
        pass
