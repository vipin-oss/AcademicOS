"""Unit tests for the Student use cases (no framework deps required).

Mirrors ``test_publication_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.create_student import CreateStudentCommand
from app.application.commands.delete_student import DeleteStudentCommand
from app.application.commands.update_student import UpdateStudentCommand
from app.application.dtos.student import CreateStudentInput, UpdateStudentInput
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_student import GetStudentQuery
from app.application.queries.list_students import ListStudentsQuery
from app.application.use_cases.students.create_student import CreateStudentUseCase
from app.application.use_cases.students.delete_student import DeleteStudentUseCase
from app.application.use_cases.students.get_student import GetStudentUseCase
from app.application.use_cases.students.import_students import (
    ImportStudentsCommand,
    ImportStudentsUseCase,
)
from app.application.use_cases.students.list_students import ListStudentsUseCase
from app.application.use_cases.students.update_student import UpdateStudentUseCase
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


def _target(repo, object_type, title):
    obj = UniversalObject.create(object_type, title, created_by="faculty:1")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def _input(**overrides) -> CreateStudentInput:
    data = {
        "name": "Asha Verma",
        "created_by": "faculty:1",
        "student_type": "ug",
        "roll_number": "BSc-101",
        "email": "asha@univ.edu",
        "programme": "BSc Mathematics with Data Science",
        "department": "Mathematics",
        "semester": 1,
        "section": "A",
        "batch": "2026-30",
        "admission_date": "2026-07-15",
    }
    data.update(overrides)
    return CreateStudentInput(**data)


@pytest.fixture()
def repo():
    return InMemoryObjectRepository()


def test_create_student_persists_registry_metadata(repo):
    out = CreateStudentUseCase(repo).execute(CreateStudentCommand(input=_input()))
    assert out.name == "Asha Verma"
    assert out.student_type == "ug"
    assert out.roll_number == "BSc-101"
    assert out.programme == "BSc Mathematics with Data Science"
    assert out.semester == 1
    assert out.status == "draft"
    assert "ObjectCreated" in out.events
    stored = repo.get_by_id(ObjectId.parse(out.id))
    assert stored is not None and stored.object_type is ObjectType.STUDENT


def test_create_student_requires_roll_or_enrollment_when_set_distinct(repo):
    CreateStudentUseCase(repo).execute(CreateStudentCommand(input=_input()))
    with pytest.raises(ObjectAlreadyExistsError):
        CreateStudentUseCase(repo).execute(
            CreateStudentCommand(input=_input(name="Clone", roll_number="bsc-101"))
        )


def test_create_student_duplicate_university_enrollment_conflicts(repo):
    CreateStudentUseCase(repo).execute(
        CreateStudentCommand(input=_input(university_enrollment="UNIV-1"))
    )
    with pytest.raises(ObjectAlreadyExistsError):
        CreateStudentUseCase(repo).execute(
            CreateStudentCommand(
                input=_input(roll_number="OTHER", university_enrollment="UNIV-1")
            )
        )


def test_create_student_validation_rejects_bad_type(repo):
    with pytest.raises(ValidationError):
        CreateStudentUseCase(repo).execute(
            CreateStudentCommand(input=_input(student_type="kindergarten"))
        )


def test_create_student_links_are_grouped_by_kind_and_target(repo):
    supervisor = _target(repo, ObjectType.FACULTY, "Dr. Rao")
    co_supervisor = _target(repo, ObjectType.FACULTY, "Dr. Iyer")
    project = _target(repo, ObjectType.RESEARCH_PROJECT, "Graph ML")
    out = CreateStudentUseCase(repo).execute(
        CreateStudentCommand(
            input=_input(
                name="PhD Scholar",
                student_type="phd",
                links={
                    "supervisors": (supervisor.id,),
                    "co_supervisors": (co_supervisor.id,),
                    "projects": (project.id,),
                },
            )
        )
    )
    assert [link["id"] for link in out.links["supervisors"]] == [str(supervisor.id)]
    assert [link["id"] for link in out.links["co_supervisors"]] == [str(co_supervisor.id)]
    assert [link["id"] for link in out.links["projects"]] == [str(project.id)]


def test_create_student_link_target_must_exist(repo):
    with pytest.raises(ValidationError):
        CreateStudentUseCase(repo).execute(
            CreateStudentCommand(
                input=_input(links={"supervisors": (ObjectId.generate(ObjectType.FACULTY),)})
            )
        )


def test_get_student_rejects_non_student(repo):
    course = _target(repo, ObjectType.COURSE, "Computer Fundamentals")
    with pytest.raises(ObjectNotFoundError):
        GetStudentUseCase(repo).execute(GetStudentQuery(object_id=course.id))


def test_list_students_filters_and_searches(repo):
    create = CreateStudentUseCase(repo)
    create.execute(CreateStudentCommand(input=_input(name="Asha Verma", roll_number="101")))
    create.execute(
        CreateStudentCommand(
            input=_input(
                name="Ravi Kumar", roll_number="102", student_type="pg", semester=3
            )
        )
    )
    create.execute(
        CreateStudentCommand(
            input=_input(name="Meena", roll_number="103", programme="PhD Physics",
                         student_type="phd")
        )
    )
    listing = ListStudentsUseCase(repo)

    assert listing.execute(ListStudentsQuery()).total_count == 3
    assert listing.execute(ListStudentsQuery(student_type="pg")).total_count == 1
    assert listing.execute(ListStudentsQuery(semester=3)).total_count == 1
    assert listing.execute(ListStudentsQuery(programme="PhD Physics")).total_count == 1
    assert listing.execute(ListStudentsQuery(q="ravi")).total_count == 1
    assert listing.execute(ListStudentsQuery(q="102")).total_count == 1
    # pagination
    page = listing.execute(ListStudentsQuery(page=2, page_size=2))
    assert page.total_count == 3 and len(page.items) == 1


def test_list_students_object_lens_returns_linked_students(repo):
    supervisor = _target(repo, ObjectType.FACULTY, "Dr. Rao")
    CreateStudentUseCase(repo).execute(
        CreateStudentCommand(
            input=_input(name="Scholar One", links={"supervisors": (supervisor.id,)})
        )
    )
    CreateStudentUseCase(repo).execute(
        CreateStudentCommand(input=_input(name="Other", roll_number="999"))
    )
    result = ListStudentsUseCase(repo).execute(ListStudentsQuery(object_id=supervisor.id))
    assert result.total_count == 1
    assert result.items[0].name == "Scholar One"


def test_update_student_partial_and_links_merge(repo):
    supervisor = _target(repo, ObjectType.FACULTY, "Dr. Rao")
    co_sup = _target(repo, ObjectType.FACULTY, "Dr. Iyer")
    new_sup = _target(repo, ObjectType.FACULTY, "Dr. Bose")
    out = CreateStudentUseCase(repo).execute(
        CreateStudentCommand(
            input=_input(
                links={"supervisors": (supervisor.id,), "co_supervisors": (co_sup.id,)}
            )
        )
    )
    updated = UpdateStudentUseCase(repo).execute(
        UpdateStudentCommand(
            object_id=ObjectId.parse(out.id),
            input=UpdateStudentInput(
                actor="faculty:1",
                semester=2,
                links={"supervisors": (new_sup.id,)},
            ),
        )
    )
    assert updated.semester == 2
    assert updated.roll_number == "BSc-101"  # untouched
    assert [link["id"] for link in updated.links["supervisors"]] == [str(new_sup.id)]
    assert [link["id"] for link in updated.links["co_supervisors"]] == [str(co_sup.id)]  # preserved


def test_update_student_identity_change_reruns_duplicate_check(repo):
    create = CreateStudentUseCase(repo)
    first = create.execute(CreateStudentCommand(input=_input(roll_number="ROLL-1")))
    create.execute(CreateStudentCommand(input=_input(name="Two", roll_number="ROLL-2")))
    updater = UpdateStudentUseCase(repo)
    with pytest.raises(ObjectAlreadyExistsError):
        updater.execute(
            UpdateStudentCommand(
                object_id=ObjectId.parse(first.id),
                input=UpdateStudentInput(actor="faculty:1", roll_number="roll-2"),
            )
        )


def test_delete_student(repo):
    out = CreateStudentUseCase(repo).execute(CreateStudentCommand(input=_input()))
    DeleteStudentUseCase(repo).execute(DeleteStudentCommand(object_id=ObjectId.parse(out.id)))
    assert repo.get_by_id(ObjectId.parse(out.id)) is None
    with pytest.raises(ObjectNotFoundError):
        DeleteStudentUseCase(repo).execute(
            DeleteStudentCommand(object_id=ObjectId.parse(out.id))
        )


def test_import_students_csv_creates_and_reports(repo):
    text = (
        "Roll No,Name,Email,Section,Programme,Semester\n"
        "101,Asha Verma,asha@univ.edu,A,BSc Mathematics,1\n"
        "102,Ravi Kumar,ravi@univ.edu,A,BSc Mathematics,1\n"
        "101,Duplicate Row,dup@univ.edu,A,BSc Mathematics,1\n"
        ",No Roll,no@univ.edu,A,BSc Mathematics,1\n"
        ",,\n"
    )
    result = ImportStudentsUseCase(repo).execute(
        ImportStudentsCommand(text=text, created_by="faculty:1")
    )
    assert len(result.created) == 2
    assert len(result.skipped_duplicates) == 1
    assert result.skipped_duplicates[0]["roll_number"] == "101"
    assert len(result.errors) == 1  # the row without a Roll No (the fully-empty row is skipped)

    listing = ListStudentsUseCase(repo).execute(ListStudentsQuery())
    assert listing.total_count == 2
    imported = {item.roll_number: item for item in listing.items}
    assert imported["101"].email == "asha@univ.edu"
    assert imported["101"].status == "active"  # CSV imports default to ACTIVE
    assert imported["102"].semester == 1


def test_import_students_rejects_empty_csv(repo):
    with pytest.raises(ValidationError):
        ImportStudentsUseCase(repo).execute(
            ImportStudentsCommand(text="", created_by="faculty:1")
        )
