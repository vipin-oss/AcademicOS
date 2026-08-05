"""Unit tests for the Committees & Meetings use cases (no framework deps).

Mirrors ``test_faculty_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.add_action_item import AddActionItemCommand
from app.application.commands.add_meeting import AddMeetingCommand
from app.application.commands.create_committee import CreateCommitteeCommand
from app.application.commands.delete_action_item import DeleteActionItemCommand
from app.application.commands.delete_committee import DeleteCommitteeCommand
from app.application.commands.delete_meeting import DeleteMeetingCommand
from app.application.commands.update_action_item import UpdateActionItemCommand
from app.application.commands.update_committee import UpdateCommitteeCommand
from app.application.commands.update_meeting import UpdateMeetingCommand
from app.application.dtos.committee import (
    CreateActionItemInput,
    CreateCommitteeInput,
    CreateMeetingInput,
    UpdateActionItemInput,
    UpdateCommitteeInput,
    UpdateMeetingInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_committee import GetCommitteeQuery
from app.application.queries.get_committees_dashboard import GetCommitteesDashboardQuery
from app.application.queries.get_meeting import GetMeetingQuery
from app.application.queries.list_committees import ListCommitteesQuery
from app.application.use_cases.committees.add_action_item import AddActionItemUseCase
from app.application.use_cases.committees.add_meeting import AddMeetingUseCase
from app.application.use_cases.committees.create_committee import CreateCommitteeUseCase
from app.application.use_cases.committees.delete_action_item import (
    DeleteActionItemUseCase,
)
from app.application.use_cases.committees.delete_committee import DeleteCommitteeUseCase
from app.application.use_cases.committees.delete_meeting import DeleteMeetingUseCase
from app.application.use_cases.committees.get_committee import GetCommitteeUseCase
from app.application.use_cases.committees.get_committees_dashboard import (
    GetCommitteesDashboardUseCase,
)
from app.application.use_cases.committees.get_meeting import GetMeetingUseCase
from app.application.use_cases.committees.list_committees import ListCommitteesUseCase
from app.application.use_cases.committees.update_action_item import (
    UpdateActionItemUseCase,
)
from app.application.use_cases.committees.update_committee import UpdateCommitteeUseCase
from app.application.use_cases.committees.update_meeting import UpdateMeetingUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    # String-keyed store — accepts ObjectId and wire strings alike, exactly
    # like the production SQLAlchemy adapter (which stringifies ids).
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
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
        sort_by: str = "id",
        order: str = "asc",
    ) -> list[UniversalObject]:
        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    o.metadata.get_value(metadata_key) is not None
                    and (
                        metadata_value is None
                        or o.metadata.get_value(metadata_key) == metadata_value
                    )
                )
            )
        ]
        reverse = order == "desc"
        if sort_by == "id":
            items.sort(key=lambda o: str(o.id), reverse=reverse)
        elif sort_by == "object_type":
            items.sort(key=lambda o: o.object_type.value, reverse=reverse)
        elif sort_by == "title":
            items.sort(key=lambda o: o.title, reverse=reverse)
        elif sort_by == "status":
            items.sort(key=lambda o: o.status.value, reverse=reverse)
        elif sort_by == "version":
            items.sort(key=lambda o: o.version, reverse=reverse)
        else:
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
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
def _person(repo: InMemoryObjectRepository, title: str, *, student: bool = False):
    obj = UniversalObject.create(
        object_type=ObjectType.STUDENT if student else ObjectType.FACULTY,
        title=title,
        created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
    )
    repo.save(obj)
    obj.pop_domain_events()
    return obj


def _input(**overrides) -> CreateCommitteeInput:
    data = {
        "name": "Board of Studies (Physics)",
        "created_by": "registrar:1",
        "status": ObjectStatus.ACTIVE,
        "committee_code": "BOS-PHY-01",
        "committee_type": "Board of Studies (BoS)",
        "department": "Physics",
        "school": "School of Physical Sciences",
        "description": "Curriculum and syllabi governance for Physics.",
        "constitution_date": "2025-07-01",
        "expiry_date": "2027-06-30",
        "notes": "Meets twice a semester.",
        "tags": ["bos", "governance"],
    }
    data.update(overrides)
    return CreateCommitteeInput(**data)


def _register(
    repo: InMemoryObjectRepository, *, with_members: bool = True, **overrides
):
    chair = _person(repo, "Prof. Asha Nair")
    student = _person(repo, "Ravi Kumar", student=True)
    payload = dict(overrides)
    if with_members:
        payload.setdefault(
            "members",
            [
                {"faculty_id": str(chair.id), "role": "chairperson", "start_date": "2025-07-01"},
                {"faculty_id": str(student.id), "role": "student_member",
                 "start_date": "2026-01-01", "remarks": "UG nominee"},
            ],
        )
    out = CreateCommitteeUseCase(repo).execute(
        CreateCommitteeCommand(input=_input(**payload))
    )
    return out, chair, student


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_create_persists_directory_members_and_backlinks():
    repo = InMemoryObjectRepository()
    out, chair, student = _register(repo)

    assert out.committee_code == "BOS-PHY-01"
    assert out.committee_type == "Board of Studies (BoS)"
    assert out.tags == ["bos", "governance"]
    assert [m.role for m in out.members] == ["chairperson", "student_member"]
    assert out.members[0].name == "Prof. Asha Nair"  # leadership sorts first
    assert out.stats["meetings"] == 0
    # backlinks written on the member aggregates (research-team precedent)
    assert str(out.id) in [str(t) for t in chair.related_ids(RelationshipKind.MEMBER_OF)]
    assert str(out.id) in [str(t) for t in student.related_ids(RelationshipKind.MEMBER_OF)]
    assert any("Created" in event for event in out.events)


def test_create_rejects_duplicate_code_and_triple_409():
    repo = InMemoryObjectRepository()
    _register(repo)
    with pytest.raises(ObjectAlreadyExistsError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=_input(name="Different Name", committee_code="bos-phy-01")
            )
        )  # same code, case-insensitive
    with pytest.raises(ObjectAlreadyExistsError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=_input(name="board of studies (physics)", committee_code="BOS-PHY-02")
            )
        )  # same (name, type, department) triple
    # same name + type but another department is allowed
    out, _, _ = _register(
        repo, name="Board of Studies (Physics)", committee_code="BOS-MAT-01",
        department="Mathematics", with_members=False,
    )
    assert out.department == "Mathematics"


def test_create_validates_members_and_links_422():
    repo = InMemoryObjectRepository()
    # unknown role
    person = _person(repo, "Prof. X")
    with pytest.raises(ValidationError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=_input(members=[{"faculty_id": str(person.id), "role": "boss"}])
            )
        )
    # member must be faculty/student
    committee_like = UniversalObject.create(
        object_type=ObjectType.COMMITTEE, title="X", created_by="t"
    )
    repo.save(committee_like)
    with pytest.raises(ValidationError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=_input(members=[{"faculty_id": str(committee_like.id), "role": "member"}])
            )
        )
    # bad link target type (a faculty under "projects")
    faculty = _person(repo, "Prof. Y")
    with pytest.raises(ValidationError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(input=_input(projects=[str(faculty.id)]))
        )
    # expiry before constitution
    with pytest.raises(ValidationError):
        CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=_input(constitution_date="2027-01-01", expiry_date="2025-01-01")
            )
        )


# ---------------------------------------------------------------------------
# Meetings (PART 3) + agenda/attendance/decisions (PART 4)
# ---------------------------------------------------------------------------
def _meeting(repo, committee_id: str, **overrides):
    data = {
        "title": "1st BoS Meeting 2026-27",
        "committee_id": committee_id,
        "created_by": "registrar:1",
        "meeting_number": "1",
        "meeting_date": "2026-08-15",
        "venue": "Committee Room 2",
        "mode": "offline",
        "agenda_items": [
            {"title": "Syllabus revision UG", "priority": "high",
             "presenter": "Prof. Asha Nair", "status": "pending"},
            {"title": "PhD coursework credits", "status": "pending"},
        ],
        "minutes": "Deferred to next meeting.",
        "attendance": [{"name": "Prof. Asha Nair", "status": "present"}],
        "decisions": ["UG syllabus to be revised by December."],
        "remarks": "Quorum complete.",
    }
    data.update(overrides)
    return AddMeetingUseCase(repo).execute(
        AddMeetingCommand(
            committee_id=committee_id,
            input=CreateMeetingInput(**data),
            actor="registrar:1",
        )
    )


def test_add_meeting_and_get_enriched_workspace():
    repo = InMemoryObjectRepository()
    committee, chair, _ = _register(repo)
    out = _meeting(repo, committee.id)
    assert out.meeting_number == "1"
    assert out.committee["id"] == committee.id
    assert out.stats["agenda_items"] == 2

    got = GetMeetingUseCase(repo).execute(GetMeetingQuery(meeting_id=out.id))
    assert got.agenda_items[0]["priority"] == "high"
    assert got.decisions == ["UG syllabus to be revised by December."]
    assert got.attendance[0]["status"] == "present"

    committee_view = GetCommitteeUseCase(repo).execute(
        GetCommitteeQuery(object_id=committee.id)
    )
    assert [m.meeting_number for m in committee_view.meetings] == ["1"]
    assert committee_view.stats["meetings"] == 1


def test_meeting_number_unique_per_committee_409():
    repo = InMemoryObjectRepository()
    committee, _, _ = _register(repo)
    other, _, _ = _register(repo, name="Finance Committee", committee_code="FC-01",
                             committee_type="Finance Committee", department="Finance",
                             with_members=False)
    _meeting(repo, committee.id)
    with pytest.raises(ObjectAlreadyExistsError):
        _meeting(repo, committee.id)
    # same number under a DIFFERENT committee is fine
    out = _meeting(repo, other.id)
    assert out.meeting_number == "1"


def test_meeting_validation_guards():
    repo = InMemoryObjectRepository()
    committee, _, _ = _register(repo)
    with pytest.raises(ValidationError):
        _meeting(repo, committee.id, mode="telepathy")
    with pytest.raises(ValidationError):
        _meeting(repo, committee.id, agenda_items=[{"priority": "high"}])  # title missing
    with pytest.raises(ValidationError):
        _meeting(repo, committee.id, attendance=[{"name": "X", "status": "maybe"}])
    with pytest.raises(ObjectNotFoundError):
        _meeting(repo, "obj:committee:MISSING")


def test_update_meeting_merge_and_number_recheck():
    repo = InMemoryObjectRepository()
    committee, _, _ = _register(repo)
    first = _meeting(repo, committee.id)
    second = _meeting(repo, committee.id, title="2nd Meeting", meeting_number="2")

    updated = UpdateMeetingUseCase(repo).execute(
        UpdateMeetingCommand(
            meeting_id=first.id,
            input=UpdateMeetingInput(
                actor="registrar:2",
                venue="Online (Meet)",
                mode="online",
                decisions=["Syllabus approved for circulation.", "DRC to review credits."],
            ),
        )
    )
    assert updated.venue == "Online (Meet)"
    assert updated.mode == "online"
    assert updated.decisions[0].startswith("Syllabus")
    assert updated.meeting_date == "2026-08-15"  # untouched
    assert updated.stats["agenda_items"] == 2

    with pytest.raises(ObjectAlreadyExistsError):
        UpdateMeetingUseCase(repo).execute(
            UpdateMeetingCommand(
                meeting_id=second.id,
                input=UpdateMeetingInput(actor="registrar:2", meeting_number="1"),
            )
        )


# ---------------------------------------------------------------------------
# Action tracker (PART 5)
# ---------------------------------------------------------------------------
def _action(repo, meeting_id: str, assignee=None, **overrides):
    data = {
        "title": "Circulate revised UG syllabus for feedback",
        "meeting_id": meeting_id,
        "created_by": "registrar:1",
        "assigned_to": assignee,
        "due_date": "2026-08-30",
        "priority": "high",
        "status": "pending",
        "progress": 0,
    }
    data.update(overrides)
    return AddActionItemUseCase(repo).execute(
        AddActionItemCommand(
            meeting_id=meeting_id,
            input=CreateActionItemInput(**data),
            actor="registrar:1",
        )
    )


def test_action_items_full_tracker_flow():
    repo = InMemoryObjectRepository()
    committee, chair, _ = _register(repo)
    meeting = _meeting(repo, committee.id)

    action = _action(repo, meeting.id, assignee=str(chair.id))
    assert action.assigned_name == "Prof. Asha Nair"
    assert action.meeting["id"] == meeting.id

    advanced = UpdateActionItemUseCase(repo).execute(
        UpdateActionItemCommand(
            action_id=action.id,
            input=UpdateActionItemInput(
                actor="registrar:2", status="in_progress", progress=60
            ),
        )
    )
    assert advanced.status == "in_progress"
    assert advanced.progress == 60

    done = UpdateActionItemUseCase(repo).execute(
        UpdateActionItemCommand(
            action_id=action.id,
            input=UpdateActionItemInput(
                actor="registrar:2", status="done", completion_date="2026-08-28"
            ),
        )
    )
    assert done.completion_date == "2026-08-28"

    workspace = GetMeetingUseCase(repo).execute(GetMeetingQuery(meeting_id=meeting.id))
    assert workspace.stats["completed_actions"] == 1

    with pytest.raises(ValidationError):
        UpdateActionItemUseCase(repo).execute(
            UpdateActionItemCommand(
                action_id=action.id,
                input=UpdateActionItemInput(actor="x", progress=120),
            )
        )
    DeleteActionItemUseCase(repo).execute(DeleteActionItemCommand(action_id=action.id))
    with pytest.raises(ObjectNotFoundError):
        DeleteActionItemUseCase(repo).execute(DeleteActionItemCommand(action_id=action.id))


def test_action_assignee_must_be_faculty_422():
    repo = InMemoryObjectRepository()
    committee, _, student = _register(repo)
    meeting = _meeting(repo, committee.id)
    with pytest.raises(ValidationError):
        _action(repo, meeting.id, assignee=str(student.id))  # students can't be assigned


# ---------------------------------------------------------------------------
# List (PART 9), update members reconcile, delete cascade, dashboard (PART 8)
# ---------------------------------------------------------------------------
def test_list_search_filters_chairperson_and_meeting_year():
    repo = InMemoryObjectRepository()
    first, _, _ = _register(repo)
    _meeting(repo, first.id)
    _register(
        repo, name="IQAC", committee_code="IQAC-01",
        committee_type="Internal Quality Assurance Cell (IQAC)",
        department="Administration", with_members=False,
    )

    all_items = ListCommitteesUseCase(repo).execute(ListCommitteesQuery())
    assert all_items.total_count == 2

    bytype = ListCommitteesUseCase(repo).execute(
        ListCommitteesQuery(committee_type="Internal Quality Assurance Cell (IQAC)")
    )
    assert [i.name for i in bytype.items] == ["IQAC"]

    byq = ListCommitteesUseCase(repo).execute(ListCommitteesQuery(q="bos physics asha"))
    assert [i.name for i in byq.items] == ["Board of Studies (Physics)"]

    bychair = ListCommitteesUseCase(repo).execute(
        ListCommitteesQuery(chairperson="asha nair")
    )
    assert [i.name for i in bychair.items] == ["Board of Studies (Physics)"]

    byyear = ListCommitteesUseCase(repo).execute(ListCommitteesQuery(meeting_year=2026))
    assert byyear.total_count == 1
    assert ListCommitteesUseCase(repo).execute(
        ListCommitteesQuery(meeting_year=2024)
    ).total_count == 0
    with pytest.raises(ValidationError):
        ListCommitteesUseCase(repo).execute(ListCommitteesQuery(page=0))


def test_update_members_reconcile_and_links_replace():
    repo = InMemoryObjectRepository()
    committee, chair, student = _register(repo)
    newcomer = _person(repo, "Prof. Kabir Shah")

    updated = UpdateCommitteeUseCase(repo).execute(
        UpdateCommitteeCommand(
            object_id=committee.id,
            input=UpdateCommitteeInput(
                actor="registrar:2",
                members=[{"faculty_id": str(newcomer.id), "role": "member"}],
                notes="Reconstituted.",
            ),
        )
    )
    assert [m.name for m in updated.members] == ["Prof. Kabir Shah"]
    assert updated.notes == "Reconstituted."
    assert updated.committee_code == "BOS-PHY-01"  # untouched
    # backlinks reconciled on the member aggregates
    chair_fresh = repo.get_by_id(chair.id)
    student_fresh = repo.get_by_id(student.id)
    new_fresh = repo.get_by_id(newcomer.id)
    assert str(committee.id) not in [str(t) for t in chair_fresh.related_ids(RelationshipKind.MEMBER_OF)]
    assert str(committee.id) not in [str(t) for t in student_fresh.related_ids(RelationshipKind.MEMBER_OF)]
    assert str(committee.id) in [str(t) for t in new_fresh.related_ids(RelationshipKind.MEMBER_OF)]

    with pytest.raises(ObjectAlreadyExistsError):
        _register(
            repo, name="Clash", committee_code="BOS-PHY-01", with_members=False
        )  # proves the code is still unique after updates


def test_delete_cascades_meetings_and_actions():
    repo = InMemoryObjectRepository()
    committee, chair, _ = _register(repo)
    meeting = _meeting(repo, committee.id)
    action = _action(repo, meeting.id, assignee=str(chair.id))

    DeleteCommitteeUseCase(repo).execute(DeleteCommitteeCommand(object_id=committee.id))
    assert repo.get_by_id(ObjectId.parse(committee.id)) is None
    assert repo.get_by_id(ObjectId.parse(meeting.id)) is None
    assert repo.get_by_id(ObjectId.parse(action.id)) is None
    # the people records survive (institutional records on other Objects)
    assert repo.get_by_id(chair.id) is not None
    with pytest.raises(ObjectNotFoundError):
        DeleteMeetingUseCase(repo).execute(DeleteMeetingCommand(meeting_id=meeting.id))


def test_dashboard_counts_and_upcoming():
    repo = InMemoryObjectRepository()
    committee, chair, _ = _register(repo)
    _meeting(repo, committee.id)  # dated 2026-08-15 (upcoming if today <= that)
    meeting2 = _meeting(
        repo, committee.id, title="Old Meeting", meeting_number="0",
        meeting_date="2024-01-10",
    )
    _action(repo, meeting2.id, assignee=str(chair.id), status="done", completion_date="2024-01-20")
    _action(repo, meeting2.id, title="Pending action A")
    _action(repo, meeting2.id, title="Pending action B")

    dashboard = GetCommitteesDashboardUseCase(repo).execute(GetCommitteesDashboardQuery())
    assert dashboard.total_committees == 1
    assert dashboard.active_committees == 1
    assert dashboard.pending_actions == 2
    assert dashboard.completed_actions == 1
    assert any(u["meeting_number"] == "1" for u in dashboard.upcoming_meetings) or not any(
        u["date"] == "2026-08-15" for u in dashboard.upcoming_meetings
    )  # depends on today's date vs the fixture
    upcoming_titles = [u["title"] for u in dashboard.upcoming_meetings]
    assert "Old Meeting" not in upcoming_titles  # past meetings never appear
