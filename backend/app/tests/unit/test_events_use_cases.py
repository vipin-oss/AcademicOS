"""Unit tests for the Events & Academic Activities use cases (no framework deps).

Mirrors ``test_finance_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.create_event import CreateEventCommand
from app.application.commands.delete_event import DeleteEventCommand
from app.application.commands.update_event import UpdateEventCommand
from app.application.dtos.events import (
    CreateEventInput,
    UpdateEventInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_event import GetEventQuery
from app.application.queries.get_events_dashboard import GetEventsDashboardQuery
from app.application.queries.list_events import ListEventsQuery
from app.application.use_cases.events.create_event import CreateEventUseCase
from app.application.use_cases.events.delete_event import DeleteEventUseCase
from app.application.use_cases.events.get_event import GetEventUseCase
from app.application.use_cases.events.get_events_dashboard import (
    GetEventsDashboardUseCase,
)
from app.application.use_cases.events.list_events import ListEventsUseCase
from app.application.use_cases.events.update_event import UpdateEventUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
)


class InMemoryObjectRepository(ObjectRepository):
    # String-keyed store — accepts ObjectId and wire strings alike, exactly
    # like the production SQLAlchemy adapter (which stringifies ids).
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[str(entity.id)] = entity

    def get_by_id(self, id) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id) -> bool:
        return str(id) in self._store

    def delete(self, id) -> None:
        self._store.pop(str(id), None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id, kind=None) -> list:
        obj = self._store.get(str(object_id))
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
def _object(repo: InMemoryObjectRepository, kind: ObjectType, title: str) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=kind, title=title, created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
    )
    repo.save(obj)
    obj.pop_domain_events()
    return obj


def _event_input(title: str = "National Mathematics Day", **overrides) -> CreateEventInput:
    payload = {
        "title": title,
        "created_by": "faculty:1",
        "event_code": "EVT-2026-001",
        "event_type": "mathematics_day",
        "organizer": "Dept. of Mathematics",
        "venue": "Auditorium A",
        "mode": "offline",
        "start_date": "2026-12-22",
        "end_date": "2026-12-22",
        "department": "Mathematics",
        "school": "School of Sciences",
        "event_status": "planned",
        "priority": "high",
    }
    payload.update(overrides)
    return CreateEventInput(**payload)


def _create(repo, title: str = "National Mathematics Day", **overrides):
    return CreateEventUseCase(repo).execute(
        CreateEventCommand(input=_event_input(title, **overrides))
    )


# ---------------------------------------------------------------------------
# Create — happy paths, enrichment, edges
# ---------------------------------------------------------------------------
def test_create_event_minimal_uses_documented_defaults():
    repo = InMemoryObjectRepository()
    out = CreateEventUseCase(repo).execute(
        CreateEventCommand(input=CreateEventInput(title="Colloquium", created_by="faculty:1"))
    )
    assert out.id.startswith("obj:event:")
    assert out.event_type == "custom"
    assert out.event_status == "planned"
    assert out.registration == {
        "expected_participants": 0,
        "registered": 0,
        "present": 0,
        "certificates_issued": 0,
    }
    assert out.stats == {
        "participation": 0,
        "speakers": 0,
        "sessions": 0,
        "presentations": 0,
        "certificates": 0,
    }
    assert set(out.links) == {
        "faculty", "students", "projects", "grants", "committees", "publications"
    }
    assert any("ObjectCreated" in event for event in out.events)


def test_create_event_full_sections_links_and_enrichment():
    repo = InMemoryObjectRepository()
    faculty = _object(repo, ObjectType.FACULTY, "Dr. Meera Krishnan")
    student = _object(repo, ObjectType.STUDENT, "Asha Verma")
    project = _object(repo, ObjectType.RESEARCH_PROJECT, "Algebraic Graphs")
    grant = _object(repo, ObjectType.GRANT, "SERB Grant")
    committee = _object(repo, ObjectType.COMMITTEE, "IQAC")
    publication = _object(repo, ObjectType.PUBLICATION, "Ramsey Bounds")
    certificate = _object(repo, ObjectType.DOCUMENT, "Certificate.pdf")
    photo = _object(repo, ObjectType.DOCUMENT, "Speaker Photo.png")
    bio_doc = _object(repo, ObjectType.DOCUMENT, "Bio.pdf")

    out = _create(
        repo,
        participation=[
            {
                "role": "organizer",
                "contribution": "Led the organising team",
                "certificate_document_id": str(certificate.id),
                "remarks": "  ",
            }
        ],
        speakers=[
            {
                "name": "Prof. S. Raman",
                "affiliation": "IIT Delhi",
                "designation": "Professor",
                "email": "raman@iitd.example",
                "photo_document_id": str(photo.id),
                "document_ids": [str(bio_doc.id)],
            }
        ],
        schedule=[
            {
                "title": "Keynote",
                "start_time": "10:00",
                "end_time": "11:00",
                "venue": "Hall 1",
                "chairperson": "Dr. Meera Krishnan",
            }
        ],
        registration={"expected_participants": 200, "registered": "150"},
        presentations=[
            {"publication_id": str(publication.id), "relation": "presented_paper"}
        ],
        faculty=[str(faculty.id)],
        students=[str(student.id)],
        projects=[str(project.id)],
        grants=[str(grant.id)],
        committees=[str(committee.id)],
    )
    # Point the session at the freshly minted speaker row id (speaker row_ids
    # are server-minted; a session can only reference a real speaker row).
    assert out.speakers[0]["row_id"]
    speaker_row_id = out.speakers[0]["row_id"]
    out = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(
                actor="faculty:1",
                schedule=[
                    {
                        "title": "Keynote",
                        "start_time": "10:00",
                        "end_time": "11:00",
                        "speaker_id": speaker_row_id,
                        "venue": "Hall 1",
                        "chairperson": "Dr. Meera Krishnan",
                    }
                ],
            ),
        )
    )

    assert out.schedule[0]["speaker_name"] == "Prof. S. Raman"
    assert out.participation[0]["certificate"] == {
        "id": str(certificate.id), "title": "Certificate.pdf"
    }
    assert out.speakers[0]["photo"] == {"id": str(photo.id), "title": "Speaker Photo.png"}
    assert out.speakers[0]["supporting_documents"] == [
        {"id": str(bio_doc.id), "title": "Bio.pdf"}
    ]
    assert out.presentations[0]["publication_title"] == "Ramsey Bounds"
    assert out.registration["expected_participants"] == 200
    assert out.registration["registered"] == 150
    assert out.registration["present"] == 0
    assert out.stats == {
        "participation": 1, "speakers": 1, "sessions": 1,
        "presentations": 1, "certificates": 1,
    }
    # Edge groups (publications derived from the presentations rows).
    assert [link["id"] for link in out.links["faculty"]] == [str(faculty.id)]
    assert [link["id"] for link in out.links["students"]] == [str(student.id)]
    assert [link["id"] for link in out.links["projects"]] == [str(project.id)]
    assert [link["id"] for link in out.links["grants"]] == [str(grant.id)]
    assert [link["id"] for link in out.links["committees"]] == [str(committee.id)]
    assert [link["id"] for link in out.links["publications"]] == [str(publication.id)]


def test_create_event_speaker_reference_validated_at_create():
    repo = InMemoryObjectRepository()
    with pytest.raises(ValidationError, match="does not match any speaker"):
        _create(
            repo,
            speakers=[{"name": "Prof. S. Raman"}],
            schedule=[{"title": "Keynote", "speaker_id": "ghost-row"}],
        )


# ---------------------------------------------------------------------------
# Create — duplicates + validation guards
# ---------------------------------------------------------------------------
def test_event_duplicate_code_and_triple_conflict():
    repo = InMemoryObjectRepository()
    _create(repo)
    # Same event code -> 409.
    with pytest.raises(ObjectAlreadyExistsError):
        _create(repo, title="A Different Title")
    # Same (title, department, start_date) triple without a code -> 409.
    repo2 = InMemoryObjectRepository()
    _create(repo2, event_code=None)
    with pytest.raises(ObjectAlreadyExistsError):
        _create(repo2, event_code=None)


def test_create_event_validation_guards():
    repo = InMemoryObjectRepository()
    publication = _object(repo, ObjectType.PUBLICATION, "Ramsey Bounds")
    faculty = _object(repo, ObjectType.FACULTY, "Dr. Meera Krishnan")

    with pytest.raises(ValidationError, match="event_type"):
        _create(repo, title="T1", event_code=None, event_type="mega_fest")
    with pytest.raises(ValidationError, match="role"):
        _create(repo, title="T2", event_code=None, participation=[{"role": "boss"}])
    with pytest.raises(ValidationError, match="role"):
        _create(repo, title="T2b", event_code=None, participation=[{"contribution": "x"}])
    with pytest.raises(ValidationError, match="end_date"):
        _create(repo, title="T3", event_code=None, end_date="2026-12-21")
    with pytest.raises(ValidationError, match="start_time"):
        _create(repo, title="T4", event_code=None,
                schedule=[{"title": "S", "start_time": "25:00"}])
    with pytest.raises(ValidationError, match="end_time must not be before"):
        _create(repo, title="T5", event_code=None,
                schedule=[{"title": "S", "start_time": "11:00", "end_time": "10:00"}])
    with pytest.raises(ValidationError, match="duplicate publication"):
        _create(repo, title="T6", event_code=None, presentations=[
            {"publication_id": str(publication.id)},
            {"publication_id": str(publication.id)},
        ])
    with pytest.raises(ValidationError, match="relation"):
        _create(repo, title="T7", event_code=None, presentations=[
            {"publication_id": str(publication.id), "relation": "keynote"}
        ])
    with pytest.raises(ValidationError, match="publication object"):
        _create(repo, title="T8", event_code=None, presentations=[
            {"publication_id": str(faculty.id)}  # a faculty, not a publication
        ])
    with pytest.raises(ValidationError, match="non-negative integer"):
        _create(repo, title="T9", event_code=None, registration={"registered": -3})
    with pytest.raises(ValidationError, match="registration"):
        _create(repo, title="T10", event_code=None, registration={"attendees": 3})
    with pytest.raises(ValidationError, match="students expects"):
        _create(repo, title="T11", event_code=None, students=[str(faculty.id)])
    with pytest.raises(ValidationError, match="email"):
        _create(repo, title="T12", event_code=None, speakers=[{"name": "X", "email": "nope"}])


# ---------------------------------------------------------------------------
# Get / list
# ---------------------------------------------------------------------------
def test_get_event_not_found_and_wrong_type():
    repo = InMemoryObjectRepository()
    other = _object(repo, ObjectType.FACULTY, "Dr. Meera Krishnan")
    with pytest.raises(ObjectNotFoundError):
        GetEventUseCase(repo).execute(GetEventQuery(object_id="obj:event:NOPE"))
    with pytest.raises(ObjectNotFoundError):
        GetEventUseCase(repo).execute(GetEventQuery(object_id=str(other.id)))


def test_list_events_filters_and_pagination():
    repo = InMemoryObjectRepository()
    publication = _object(repo, ObjectType.PUBLICATION, "Ramsey Bounds")
    _create(repo, title="Algebra Colloquium", event_code="E-1",
            event_type="research_colloquium", department="Mathematics",
            organizer="Dept. of Mathematics", start_date="2026-01-15",
            participation=[{"role": "speaker"}],
            speakers=[{"name": "Prof. S. Raman"}],
            presentations=[{"publication_id": str(publication.id),
                            "relation": "presented_paper"}])
    _create(repo, title="Cloud Workshop", event_code="E-2",
            event_type="workshop", department="Computer Science",
            organizer="CSI Chapter", start_date="2025-11-05",
            event_status="completed",
            participation=[{"role": "participant"}])
    _create(repo, title="Yoga Outreach", event_code="E-3",
            event_type="outreach_activity", department="Sports",
            organizer="NSS Unit", start_date="2026-06-21",
            event_status="cancelled")

    use_case = ListEventsUseCase(repo)
    assert use_case.execute(ListEventsQuery()).total_count == 3
    by_type = use_case.execute(ListEventsQuery(event_type="workshop"))
    assert [item.title for item in by_type.items] == ["Cloud Workshop"]
    by_year = use_case.execute(ListEventsQuery(year="2026"))
    assert {item.title for item in by_year.items} == {"Algebra Colloquium", "Yoga Outreach"}
    by_role = use_case.execute(ListEventsQuery(role="participant"))
    assert [item.title for item in by_role.items] == ["Cloud Workshop"]
    by_dept = use_case.execute(ListEventsQuery(department="computer"))
    assert [item.title for item in by_dept.items] == ["Cloud Workshop"]
    by_organizer = use_case.execute(ListEventsQuery(organizer="nss"))
    assert [item.title for item in by_organizer.items] == ["Yoga Outreach"]
    by_status = use_case.execute(ListEventsQuery(status="cancelled"))
    assert [item.title for item in by_status.items] == ["Yoga Outreach"]
    by_search = use_case.execute(ListEventsQuery(q="raman"))  # speaker name haystack
    assert [item.title for item in by_search.items] == ["Algebra Colloquium"]
    page = use_case.execute(ListEventsQuery(page=2, page_size=2))
    assert page.total_count == 3 and len(page.items) == 1
    with pytest.raises(ValidationError, match="year"):
        use_case.execute(ListEventsQuery(year="26"))

    # List rows carry the same denormalised shape as the workspace payload.
    row = by_role.items[0]
    assert row.stats["participation"] == 1
    full = GetEventUseCase(repo).execute(GetEventQuery(object_id=row.id))
    assert full.participation == row.participation


# ---------------------------------------------------------------------------
# Update — merge contract / group-replace / duplicate re-scan
# ---------------------------------------------------------------------------
def test_update_event_merge_contract_and_group_replace():
    repo = InMemoryObjectRepository()
    faculty = _object(repo, ObjectType.FACULTY, "Dr. Meera Krishnan")
    project = _object(repo, ObjectType.RESEARCH_PROJECT, "Algebraic Graphs")
    out = _create(repo, faculty=[str(faculty.id)], priority="low")

    updated = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(
                actor="faculty:1",
                venue="Seminar Hall B",
                event_status="ongoing",
                registration={"present": 87},
                faculty=[],
                projects=[str(project.id)],
            ),
        )
    )
    # Replaced fields…
    assert updated.venue == "Seminar Hall B"
    assert updated.event_status == "ongoing"
    assert updated.priority == "low"  # untouched scalar preserved
    assert updated.registration == {
        "expected_participants": 0, "registered": 0, "present": 87, "certificates_issued": 0
    }
    # …and group-replaced links (faculty cleared, project added).
    assert updated.links["faculty"] == []
    assert [link["id"] for link in updated.links["projects"]] == [str(project.id)]
    # Untouched core fields preserved.
    assert updated.event_code == "EVT-2026-001"
    assert updated.organizer == "Dept. of Mathematics"


def test_update_event_presentations_group_replace_resyncs_publication_edges():
    repo = InMemoryObjectRepository()
    pub_a = _object(repo, ObjectType.PUBLICATION, "Paper A")
    pub_b = _object(repo, ObjectType.PUBLICATION, "Paper B")
    out = _create(
        repo,
        presentations=[{"publication_id": str(pub_a.id), "relation": "presented_paper"}],
    )
    assert [link["id"] for link in out.links["publications"]] == [str(pub_a.id)]

    updated = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(
                actor="faculty:1",
                presentations=[{"publication_id": str(pub_b.id), "relation": "best_paper_award"}],
            ),
        )
    )
    assert [link["id"] for link in updated.links["publications"]] == [str(pub_b.id)]
    assert updated.presentations[0]["relation"] == "best_paper_award"
    assert updated.presentations[0]["publication_title"] == "Paper B"

    cleared = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(actor="faculty:1", presentations=[]),
        )
    )
    assert cleared.links["publications"] == []


def test_update_event_re_runs_duplicate_scan_on_code_change():
    repo = InMemoryObjectRepository()
    first = _create(repo, title="First", event_code="E-A")
    _create(repo, title="Second", event_code="E-B")
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateEventUseCase(repo).execute(
            UpdateEventCommand(
                object_id=first.id,
                input=UpdateEventInput(actor="faculty:1", event_code="E-B"),
            )
        )


def test_schedule_speaker_rename_reflects_and_removal_dangles():
    repo = InMemoryObjectRepository()
    out = _create(repo, speakers=[{"name": "Prof. S. Raman"}])
    row_id = out.speakers[0]["row_id"]
    out = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(
                actor="faculty:1",
                schedule=[{"title": "Keynote", "speaker_id": row_id}],
            ),
        )
    )
    assert out.schedule[0]["speaker_name"] == "Prof. S. Raman"

    # Rename the speaker echoing the SAME row_id — the session follows.
    renamed = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(
                actor="faculty:1",
                speakers=[{"row_id": row_id, "name": "Prof. S. Raman (IITD)"}],
            ),
        )
    )
    assert renamed.schedule[0]["speaker_name"] == "Prof. S. Raman (IITD)"

    # Referencing a row that the payload speakers no longer contain -> 422.
    with pytest.raises(ValidationError, match="does not match any speaker"):
        UpdateEventUseCase(repo).execute(
            UpdateEventCommand(
                object_id=out.id,
                input=UpdateEventInput(
                    actor="faculty:1",
                    speakers=[{"name": "Someone Else"}],
                    schedule=[{"title": "Keynote", "speaker_id": row_id}],
                ),
            )
        )

    # Removing the speaker without touching the schedule dangles gracefully:
    # stored speaker_id simply stops decorating (the DeleteVendor precedent).
    cleared = UpdateEventUseCase(repo).execute(
        UpdateEventCommand(
            object_id=out.id,
            input=UpdateEventInput(actor="faculty:1", speakers=[]),
        )
    )
    assert cleared.speakers == []
    assert "speaker_name" not in cleared.schedule[0]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def test_delete_event_and_not_found_guards():
    repo = InMemoryObjectRepository()
    out = _create(repo)
    DeleteEventUseCase(repo).execute(DeleteEventCommand(object_id=out.id))
    assert repo.get_by_id(out.id) is None
    with pytest.raises(ObjectNotFoundError):
        DeleteEventUseCase(repo).execute(DeleteEventCommand(object_id=out.id))
    other = _object(repo, ObjectType.FACULTY, "Dr. Meera Krishnan")
    with pytest.raises(ObjectNotFoundError):
        DeleteEventUseCase(repo).execute(DeleteEventCommand(object_id=str(other.id)))


# ---------------------------------------------------------------------------
# PART 9 dashboard (computed read, exact counts)
# ---------------------------------------------------------------------------
def test_events_dashboard_counts_each_card_rule():
    repo = InMemoryObjectRepository()
    publication = _object(repo, ObjectType.PUBLICATION, "Ramsey Bounds")
    certificate = _object(repo, ObjectType.DOCUMENT, "Certificate.pdf")

    # Organized + upcoming + certificate + presentation.
    _create(
        repo, title="Conference A", event_code="E-1", event_type="conference",
        event_status="planned",
        participation=[{
            "role": "organizer",
            "certificate_document_id": str(certificate.id),
        }],
        presentations=[{"publication_id": str(publication.id),
                        "relation": "presented_paper"}],
    )
    # Attended + upcoming (participant role neither organizes nor speaks).
    _create(
        repo, title="Workshop B", event_code="E-2", event_type="workshop",
        event_status="ongoing", participation=[{"role": "attendee"}],
    )
    # Completed invited talk with a speaking role -> invited_talks card.
    _create(
        repo, title="Talk C", event_code="E-3", event_type="invited_talk",
        event_status="completed", participation=[{"role": "resource_person"}],
    )
    # Completed invited talk where I only judged -> NOT an invited talk card.
    _create(
        repo, title="Talk D", event_code="E-4", event_type="invited_talk",
        event_status="completed", participation=[{"role": "judge"}],
    )
    # Cancelled events are neither upcoming nor completed.
    _create(repo, title="Seminar E", event_code="E-5", event_status="cancelled")

    cards = GetEventsDashboardUseCase(repo).execute(GetEventsDashboardQuery())
    assert cards.upcoming_events == 2
    assert cards.completed_events == 2
    assert cards.events_organized == 1
    assert cards.events_attended == 1
    assert cards.certificates == 1
    assert cards.presentations == 1
    assert cards.invited_talks == 1
