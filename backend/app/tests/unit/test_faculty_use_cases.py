"""Unit tests for the Faculty use cases (no framework deps required).

Mirrors ``test_research_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import json

import pytest

from app.application.commands.attach_faculty_photo import AttachFacultyPhotoCommand
from app.application.commands.create_faculty import CreateFacultyCommand
from app.application.commands.delete_faculty import DeleteFacultyCommand
from app.application.commands.update_faculty import UpdateFacultyCommand
from app.application.dtos.faculty import (
    CreateFacultyInput,
    UpdateFacultyInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_faculty import GetFacultyQuery
from app.application.queries.list_faculty import ListFacultyQuery
from app.application.use_cases.faculty.attach_faculty_photo import (
    AttachFacultyPhotoUseCase,
)
from app.application.use_cases.faculty.create_faculty import CreateFacultyUseCase
from app.application.use_cases.faculty.delete_faculty import DeleteFacultyUseCase
from app.application.use_cases.faculty.get_faculty import GetFacultyUseCase
from app.application.use_cases.faculty.helpers import weekly_hours_of
from app.application.use_cases.faculty.list_faculty import ListFacultyUseCase
from app.application.use_cases.faculty.update_faculty import UpdateFacultyUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.storage.local import LocalFileStorage


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
        return [] if obj is None else obj.related_ids(kind)
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


    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


# ---------------------------------------------------------------------------
# Fabrication helpers (mirror the other suites' style)
# ---------------------------------------------------------------------------
def _input(**overrides) -> CreateFacultyInput:
    data = {
        "name": "Dr. Asha Nair",
        "employee_id": "EMP-1001",
        "created_by": "faculty:1",
        "status": ObjectStatus.ACTIVE,
        "faculty_code": "PHY-A-07",
        "designation": "Associate Professor",
        "department": "Physics",
        "school": "School of Physical Sciences",
        "joining_date": "2015-07-01",
        "employment_type": "regular",
        "email": "asha.nair@univ.edu",
        "mobile": "+91-98xxxxxxx1",
        "office": "B-204, Science Block",
        "qualification": "Ph.D. (Physics), IIT Delhi",
        "specialization": "Condensed Matter Physics",
        "research_interests": ["perovskites", "quantum dots"],
        "biography": "Works on thin-film photovoltaics.",
        "orcid": "0000-0002-1825-0097",
        "scopus_id": "55512345600",
        "google_scholar": "abcXYZ123",
        "researchgate": "Asha-Nair-42",
        "website": "https://univ.edu/faculty/asha-nair",
        "notes": "PhD coordinator.",
        "tags": ["senate", "nano-facility"],
        "degrees": [{"degree": "Ph.D.", "institution": "IIT Delhi", "year": "2012"}],
        "experience": [
            {"role": "Assistant Professor", "organization": "Univ", "from": "2015", "to": "2021"}
        ],
        "awards": [{"title": "Young Scientist Award", "year": "2019", "by": "INSA"}],
        "memberships": [{"body": "Indian Physics Association"}],
        "certifications": [{"title": "Nano-fabrication", "issuer": "INI", "year": "2020"}],
        "admin_positions": [{"position": "PhD Coordinator", "unit": "Physics", "from": "2023"}],
    }
    data.update(overrides)
    return CreateFacultyInput(**data)


def _create(repo, **overrides) -> object:
    return CreateFacultyUseCase(repo).execute(CreateFacultyCommand(input=_input(**overrides)))


def _target(repo, object_type, title, **meta):
    entries = [
        MetadataEntry(key, value if isinstance(value, str) else json.dumps(value),
                      MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        for key, value in meta.items()
    ]
    obj = UniversalObject.create(
        object_type, title, created_by="faculty:1",
        metadata=Metadata(entries=tuple(entries)),
    )
    obj.pop_domain_events()
    repo.save(obj)
    return obj


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_create_returns_the_full_enriched_record():
    repo = InMemoryObjectRepository()
    committee = _target(repo, ObjectType.COMMITTEE, "IQAC")
    out = _create(repo, committees=[str(committee.id)])

    assert out.name == "Dr. Asha Nair"
    assert out.status == "active"
    assert out.employee_id == "EMP-1001"
    assert out.faculty_code == "PHY-A-07"
    assert out.research_interests == ["perovskites", "quantum dots"]
    assert out.tags == ["senate", "nano-facility"]
    assert out.degrees == [{"degree": "Ph.D.", "institution": "IIT Delhi", "year": "2012"}]
    assert out.awards[0]["title"] == "Young Scientist Award"
    assert out.admin_positions[0]["position"] == "PhD Coordinator"
    assert [link["id"] for link in out.links["committees"]] == [str(committee.id)]
    assert out.links["committees"][0]["kind"] == "member_of"
    assert out.stats["committees"] == 0  # stats are computed by GetFaculty, not create


def test_create_rejects_duplicate_employee_id_case_insensitively():
    repo = InMemoryObjectRepository()
    _create(repo)
    with pytest.raises(ObjectAlreadyExistsError):
        _create(repo, employee_id="emp-1001")


def test_create_rejects_duplicate_faculty_code_but_allows_missing():
    repo = InMemoryObjectRepository()
    _create(repo)
    with pytest.raises(ObjectAlreadyExistsError):
        _create(repo, employee_id="EMP-1002", faculty_code="phy-a-07")
    # Two faculty without a code never collide.
    _create(repo, employee_id="EMP-1002", faculty_code=None)
    _create(repo, employee_id="EMP-1003", faculty_code=None)


def test_create_validates_required_and_typed_fields():
    repo = InMemoryObjectRepository()
    with pytest.raises(ValidationError):
        _create(repo, employee_id="")
    with pytest.raises(ValidationError):
        _create(repo, name="  ")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-2001", employment_type="freelance")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-2002", email="not-an-email")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-2003", orcid="123")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-2004", website="ftp://x")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-2005", joining_date="01-07-2015")


def test_create_validates_section_entries():
    repo = InMemoryObjectRepository()
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-3001", degrees=[{}])
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-3002", awards=[{"title": "X", "year": "20a1"}])
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-3003",
                degrees=[{"degree": "PhD", "campus": "oops"}])


def test_create_rejects_non_committee_link_targets():
    repo = InMemoryObjectRepository()
    student = _target(repo, ObjectType.STUDENT, "Asha Verma")
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-4001", committees=[str(student.id)])
    with pytest.raises(ValidationError):
        _create(repo, employee_id="EMP-4002", committees=["obj:committee:DOESNOTEXIST"])


# ---------------------------------------------------------------------------
# Get — the derived lenses + dashboard stats (PART 3/4/5/6)
# ---------------------------------------------------------------------------
def test_get_missing_or_wrong_type_is_not_found():
    repo = InMemoryObjectRepository()
    with pytest.raises(ObjectNotFoundError):
        GetFacultyUseCase(repo).execute(GetFacultyQuery(ObjectId.parse("obj:faculty:ZZZ")))
    other = _target(repo, ObjectType.COMMITTEE, "NAAC Committee")
    with pytest.raises(ObjectNotFoundError):
        GetFacultyUseCase(repo).execute(GetFacultyQuery(other.id))


def _seed_related_graph(repo, out):
    """Projects / grant / students / class / publication around one faculty."""
    faculty = repo.get_by_id(ObjectId.parse(out.id))
    project_a = _target(repo, ObjectType.RESEARCH_PROJECT, "Perovskite Cells",
                        lifecycle_status="funded")
    project_b = _target(repo, ObjectType.RESEARCH_PROJECT, "Quantum Dots",
                        lifecycle_status="completed")
    faculty.add_relationship(project_a.id, RelationshipKind.LEADS, Provenance.ASSERTED,
                             actor="faculty:1")
    faculty.add_relationship(project_b.id, RelationshipKind.WORKS_IN, Provenance.ASSERTED,
                             actor="faculty:1")
    repo.save(faculty)
    faculty.pop_domain_events()
    grant = _target(repo, ObjectType.GRANT, "SERB Core Grant")
    grant.add_relationship(project_a.id, RelationshipKind.FUNDS, Provenance.ASSERTED,
                           actor="faculty:1")
    repo.save(grant)
    grant.pop_domain_events()
    scholar = _target(repo, ObjectType.STUDENT, "Ravi Kumar", student_type="phd")
    scholar.add_relationship(faculty.id, RelationshipKind.SUPERVISED_BY, Provenance.ASSERTED,
                             actor="faculty:1")
    repo.save(scholar)
    scholar.pop_domain_events()
    alum = _target(repo, ObjectType.STUDENT, "Meera Iyer", student_type="alumni")
    alum.add_relationship(faculty.id, RelationshipKind.ADVISED_BY,
                          Provenance.ASSERTED, actor="faculty:1")
    repo.save(alum)
    alum.pop_domain_events()
    cls = _target(repo, ObjectType.COURSE, "Quantum Mechanics (Sem 3)",
                  course_code="PHY-301", programme="BSc Physics", semester="3", credits="4",
                  weekly_schedule=json.dumps([
                      {"day": "mon", "start": "09:00", "end": "10:30"},
                      {"day": "thu", "start": "14:00", "end": "15:00"},
                      {"day": "fri"},
                  ]))
    cls.add_relationship(faculty.id, RelationshipKind.TAUGHT_BY, Provenance.ASSERTED,
                         actor="faculty:1")
    repo.save(cls)
    cls.pop_domain_events()
    publication = _target(repo, ObjectType.PUBLICATION, "Quantum dots in perovskites")
    publication.add_relationship(faculty.id, RelationshipKind.AUTHORED_BY, Provenance.ASSERTED,
                                 actor="faculty:1")
    repo.save(publication)
    publication.pop_domain_events()


def test_get_computes_research_supervision_teaching_and_stats():
    repo = InMemoryObjectRepository()
    out = _create(repo)
    _seed_related_graph(repo, out)
    got = GetFacultyUseCase(repo).execute(GetFacultyQuery(ObjectId.parse(out.id)))

    by_kind = {p["kind"]: p["title"] for p in got.research["projects"]}
    assert by_kind == {"leads": "Perovskite Cells", "works_in": "Quantum Dots"}
    assert [g["title"] for g in got.research["grants"]] == ["SERB Core Grant"]
    assert [s["title"] for s in got.supervision["current"]] == ["Ravi Kumar"]
    assert got.supervision["current"][0]["student_type"] == "phd"
    assert [s["title"] for s in got.supervision["completed"]] == ["Meera Iyer"]
    cls = got.teaching["classes"][0]
    assert cls["course_code"] == "PHY-301"
    assert cls["semester"] == 3 and cls["credits"] == 4
    # 1.5h + 1h + 1h (missing times default to one hour per slot).
    assert cls["weekly_hours"] == 3.5
    assert got.teaching["total_weekly_hours"] == 3.5
    assert got.stats == {
        "publications": 1,
        "active_projects": 1,  # only the FUNDED one is in-flight
        "grants": 1,
        "students_supervised": 1,
        "courses": 1,
        "committees": 0,
    }


def test_weekly_hours_parsing_edges():
    assert weekly_hours_of(None) == 0.0
    assert weekly_hours_of("[]") == 0.0
    assert weekly_hours_of("not json") == 0.0
    assert weekly_hours_of(json.dumps([{"day": "tue", "start": "9", "end": "x"}])) == 1.0
    assert weekly_hours_of(json.dumps([{"start": "09:00", "end": "10:00"},
                                       {"start": "10:00", "end": "11:30"}])) == 2.5


# ---------------------------------------------------------------------------
# Update (frozen merge contract)
# ---------------------------------------------------------------------------
def test_update_merge_semantics_replace_and_clear():
    repo = InMemoryObjectRepository()
    out = _create(repo)
    updated = UpdateFacultyUseCase(repo).execute(
        UpdateFacultyCommand(
            object_id=ObjectId.parse(out.id),
            input=UpdateFacultyInput(
                actor="faculty:2",
                designation="Professor",
                office="",  # frozen replace-contract: stored verbatim
                research_interests=["topological materials"],
            ),
        )
    )
    assert updated.designation == "Professor"
    assert updated.office == ""  # verbatim replace (update_agency precedent)
    assert updated.research_interests == ["topological materials"]
    assert updated.department == "Physics"  # untouched
    assert updated.degrees and updated.degrees[0]["degree"] == "Ph.D."  # untouched
    assert updated.version > 1


def test_update_sections_and_committees_replace():
    repo = InMemoryObjectRepository()
    committee_a = _target(repo, ObjectType.COMMITTEE, "IQAC")
    committee_b = _target(repo, ObjectType.COMMITTEE, "Library Committee")
    out = _create(repo, employee_id="EMP-5001", committees=[str(committee_a.id)])
    updated = UpdateFacultyUseCase(repo).execute(
        UpdateFacultyCommand(
            object_id=ObjectId.parse(out.id),
            input=UpdateFacultyInput(
                actor="faculty:2",
                degrees=[],  # clears the section
                awards=[{"title": "New Award", "year": "2024"}],
                committees=[str(committee_b.id)],
            ),
        )
    )
    assert updated.degrees == []
    assert [a["title"] for a in updated.awards] == ["New Award"]
    assert [link["title"] for link in updated.links["committees"]] == ["Library Committee"]
    # experience stayed untouched
    assert updated.experience and updated.experience[0]["role"] == "Assistant Professor"


def test_update_employee_id_change_reruns_duplicate_check():
    repo = InMemoryObjectRepository()
    first = _create(repo)
    second = _create(repo, employee_id="EMP-6002", faculty_code=None)
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateFacultyUseCase(repo).execute(
            UpdateFacultyCommand(
                object_id=ObjectId.parse(second.id),
                input=UpdateFacultyInput(actor="faculty:2", employee_id="emp-1001"),
            )
        )
    # Keeping one's own id is fine.
    kept = UpdateFacultyUseCase(repo).execute(
        UpdateFacultyCommand(
            object_id=ObjectId.parse(first.id),
            input=UpdateFacultyInput(actor="faculty:2", employee_id="EMP-1001"),
        )
    )
    assert kept.employee_id == "EMP-1001"


# ---------------------------------------------------------------------------
# Delete + photo
# ---------------------------------------------------------------------------
def test_delete_removes_the_record():
    repo = InMemoryObjectRepository()
    out = _create(repo)
    DeleteFacultyUseCase(repo).execute(DeleteFacultyCommand(object_id=ObjectId.parse(out.id)))
    with pytest.raises(ObjectNotFoundError):
        GetFacultyUseCase(repo).execute(GetFacultyQuery(ObjectId.parse(out.id)))
    with pytest.raises(ObjectNotFoundError):
        DeleteFacultyUseCase(repo).execute(DeleteFacultyCommand(object_id=ObjectId.parse(out.id)))


def test_attach_photo_records_facts_and_replaces(tmp_path):
    repo = InMemoryObjectRepository()
    storage = LocalFileStorage(str(tmp_path))
    out = _create(repo)
    use_case = AttachFacultyPhotoUseCase(repo, storage)
    with pytest.raises(ValidationError):
        use_case.execute(
            AttachFacultyPhotoCommand(
                object_id=ObjectId.parse(out.id), file_name="note.txt",
                content=b"hello", mime_type="text/plain",
            )
        )
    with pytest.raises(ValidationError):
        use_case.execute(
            AttachFacultyPhotoCommand(
                object_id=ObjectId.parse(out.id), file_name="x.png",
                content=b"", mime_type="image/png",
            )
        )
    attached = use_case.execute(
        AttachFacultyPhotoCommand(
            object_id=ObjectId.parse(out.id), file_name="asha.png",
            content=b"\x89PNG-fake-1", mime_type="image/png",
        )
    )
    assert attached.photo_file_name == "asha.png"
    assert attached.photo_file_size == len(b"\x89PNG-fake-1")
    old_key = attached.photo_file_path
    assert old_key and storage.exists(old_key)
    replaced = use_case.execute(
        AttachFacultyPhotoCommand(
            object_id=ObjectId.parse(out.id), file_name="asha-2.jpg",
            content=b"\xff\xd8-fake-2", mime_type="image/jpeg",
        )
    )
    assert replaced.photo_file_name == "asha-2.jpg"
    assert not storage.exists(old_key)  # the old blob is gone


# ---------------------------------------------------------------------------
# List — PART 7 search + filters
# ---------------------------------------------------------------------------
def test_list_search_and_filters():
    repo = InMemoryObjectRepository()
    _create(repo)  # Asha Nair, Physics, Associate Professor, regular
    _create(repo, name="Dr. Kabir Shah", employee_id="EMP-7002", designation="Professor",
            department="Mathematics", specialization="Algebra",
            research_interests=["number theory"], faculty_code=None)
    _create(repo, name="Dr. Meera Rao", employee_id="EMP-7003", employment_type="visiting",
            department=None, designation=None, specialization=None, email=None,
            status=ObjectStatus.DRAFT, faculty_code=None)

    all_rows = ListFacultyUseCase(repo).execute(ListFacultyQuery(page_size=10))
    assert all_rows.total_count == 3
    assert [r.name for r in all_rows.items] == sorted(
        ["Dr. Asha Nair", "Dr. Kabir Shah", "Dr. Meera Rao"], key=str.casefold)

    physics = ListFacultyUseCase(repo).execute(ListFacultyQuery(department="physics"))
    assert [r.name for r in physics.items] == ["Dr. Asha Nair"]
    assert ListFacultyUseCase(repo).execute(
        ListFacultyQuery(designation="PROFESSOR")).total_count == 1
    assert ListFacultyUseCase(repo).execute(
        ListFacultyQuery(employment_type="visiting")).total_count == 1
    assert ListFacultyUseCase(repo).execute(ListFacultyQuery(status="draft")).total_count == 1
    found = ListFacultyUseCase(repo).execute(ListFacultyQuery(q="quantum dots asha"))
    assert [r.name for r in found.items] == ["Dr. Asha Nair"]
    found = ListFacultyUseCase(repo).execute(ListFacultyQuery(q="NUMBER THEORY"))
    assert [r.name for r in found.items] == ["Dr. Kabir Shah"]
    found = ListFacultyUseCase(repo).execute(ListFacultyQuery(q="condensed"))
    assert found.total_count == 1
    assert ListFacultyUseCase(repo).execute(ListFacultyQuery(q="nobody")).total_count == 0
    paged = ListFacultyUseCase(repo).execute(ListFacultyQuery(page=2, page_size=2))
    assert paged.total_count == 3 and len(paged.items) == 1
