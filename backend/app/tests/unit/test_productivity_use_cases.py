"""Unit tests for the Productivity Hub use cases (no framework deps).

Mirrors ``test_reports_use_cases.py``: an in-memory ``ObjectRepository``
fabricates a small cross-module world and the productivity use cases run
against it — verifying PART 1..8 behaviour is computed from the frozen
modules' data plus the user's own task/entry/notification objects.

All fixture dates are derived from the REAL today (via ``dt.timedelta``) so
the suite is deterministic on any day it runs.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app.application.commands.create_calendar_entry import CreateCalendarEntryCommand
from app.application.commands.create_notification import CreateNotificationCommand
from app.application.commands.create_task import CreateTaskCommand
from app.application.commands.delete_task import DeleteTaskCommand
from app.application.commands.update_calendar_entry import UpdateCalendarEntryCommand
from app.application.commands.update_notification import UpdateNotificationCommand
from app.application.commands.update_task import UpdateTaskCommand
from app.application.dtos.productivity import (
    CreateEntryInput,
    CreateNotificationInput,
    CreateTaskInput,
    UpdateEntryInput,
    UpdateNotificationInput,
    UpdateTaskInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_calendar_feed import GetCalendarFeedQuery
from app.application.queries.get_productivity_dashboard import GetProductivityDashboardQuery
from app.application.queries.get_reminders import GetRemindersQuery
from app.application.queries.get_task import GetTaskQuery
from app.application.queries.list_notifications import ListNotificationsQuery
from app.application.queries.list_tasks import ListTasksQuery
from app.application.queries.productivity_search import ProductivitySearchQuery
from app.application.use_cases.productivity.create_calendar_entry import (
    CreateCalendarEntryUseCase,
)
from app.application.use_cases.productivity.create_notification import (
    CreateNotificationUseCase,
)
from app.application.use_cases.productivity.create_task import CreateTaskUseCase
from app.application.use_cases.productivity.delete_task import DeleteTaskUseCase
from app.application.use_cases.productivity.get_calendar_feed import GetCalendarFeedUseCase
from app.application.use_cases.productivity.get_dashboard import (
    GetProductivityDashboardUseCase,
)
from app.application.use_cases.productivity.get_reminders import GetRemindersUseCase
from app.application.use_cases.productivity.get_task import GetTaskUseCase
from app.application.use_cases.productivity.list_notifications import (
    ListNotificationsUseCase,
)
from app.application.use_cases.productivity.list_tasks import ListTasksUseCase
from app.application.use_cases.productivity.productivity_search import (
    ProductivitySearchUseCase,
)
from app.application.use_cases.productivity.refresh_notifications import (
    RefreshNotificationsUseCase,
)
from app.application.use_cases.productivity.update_calendar_entry import (
    UpdateCalendarEntryUseCase,
)
from app.application.use_cases.productivity.update_notification import (
    UpdateNotificationUseCase,
)
from app.application.use_cases.productivity.update_task import UpdateTaskUseCase
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

_TODAY = dt.date.today()


def d(offset: int) -> str:
    return (_TODAY + dt.timedelta(days=offset)).isoformat()


TODAY = d(0)
WEEKDAY_TODAY = _TODAY.strftime("%a").lower()  # frozen abbreviation: "mon" ..


class InMemoryObjectRepository(ObjectRepository):
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


def _meta_entries(**pairs: str) -> tuple:
    return tuple(
        MetadataEntry(k, v, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        for k, v in pairs.items()
    )


def _make(
    repo: InMemoryObjectRepository,
    kind: ObjectType,
    title: str,
    links: list[tuple] | None = None,
    **meta: str,
) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=kind,
        title=title,
        created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(**meta)),
    )
    for target, rel_kind in links or []:
        obj.add_relationship(target, rel_kind, actor="registrar:1")
    repo.save(obj)
    obj.pop_domain_events()
    return obj


@pytest.fixture()
def world() -> InMemoryObjectRepository:
    """Frozen-module world + productivity objects across the PART 5 windows."""
    repo = InMemoryObjectRepository()

    committee = _make(repo, ObjectType.COMMITTEE, "IQAC", committee_type="Internal")
    meeting = _make(
        repo, ObjectType.MEETING, "IQAC August Meet", meeting_date=TODAY,
        links=[(committee.id, RelationshipKind.BELONGS_TO)],
    )
    # Committee action items (institutional reports): one overdue, one D+3.
    _make(
        repo, ObjectType.TASK, "Prepare AQAR draft", due_date=d(-2),
        priority="high", action_status="pending",
        links=[(meeting.id, RelationshipKind.BELONGS_TO)],
    )
    _make(
        repo, ObjectType.TASK, "Upload meeting minutes", due_date=d(3),
        action_status="pending",
        links=[(meeting.id, RelationshipKind.BELONGS_TO)],
    )
    # Events: one today, one clearly outside the next-7-days window.
    _make(
        repo, ObjectType.EVENT, "Mathematics Day", start_date=TODAY,
        end_date=TODAY, event_status="planned", venue="Main Hall",
    )
    _make(
        repo, ObjectType.EVENT, "Two-Day Workshop", start_date=d(9),
        end_date=d(10), event_status="planned",
    )
    # Research: project + pending milestone (tomorrow) + scheduled installment.
    project = _make(
        repo, ObjectType.RESEARCH_PROJECT, "Graph Frontiers",
        start_date=TODAY, end_date=d(17), lifecycle_status="active",
    )
    _make(
        repo, ObjectType.PROJECT_MILESTONE, "Interim report", milestone_date=d(1),
        milestone_status="pending", links=[(project.id, RelationshipKind.BELONGS_TO)],
    )
    grant = _make(repo, ObjectType.GRANT, "SERB Core", grant_number="SERB-1")
    _make(
        repo, ObjectType.GRANT_INSTALLMENT, "Installment 2", installment_no="2",
        installment_date=d(2), installment_status="scheduled",
        links=[(grant.id, RelationshipKind.BELONGS_TO)],
    )
    # Teaching: weekly slot on TODAY's weekday + assignment due today + session today.
    _make(
        repo, ObjectType.COURSE, "Linear Algebra", course_code="MA201",
        weekly_schedule=json.dumps([{"day": WEEKDAY_TODAY, "start": "09:00", "end": "10:00"}]),
    )
    _make(repo, ObjectType.ASSIGNMENT, "Problem Set 4", deadline=TODAY, course_code="MA201")
    _make(repo, ObjectType.ATTENDANCE_SESSION, "MA201 attendance", session_date=TODAY)
    # Finance: open PO delivery tomorrow + unpaid bill (overdue yesterday).
    _make(
        repo, ObjectType.PURCHASE, "Books Purchase", proposal_number="PP-1",
        purchase_orders=json.dumps(
            [{"po_number": "PO-9", "status": "issued", "delivery_date": d(1), "amount": "40000"}]
        ),
        bills=json.dumps(
            [{"bill_number": "B-3", "payment_status": "pending", "bill_date": d(-1), "amount": "38000"}]
        ),
    )

    uc = CreateTaskUseCase(repo)
    uc.execute(CreateTaskCommand(input=CreateTaskInput(
        title="Overdue task", uploaded_by="me", due_date=d(-2), priority="high",
    )))
    uc.execute(CreateTaskCommand(input=CreateTaskInput(
        title="Today task", uploaded_by="me", due_date=TODAY, pinned=True,
    )))
    uc.execute(CreateTaskCommand(input=CreateTaskInput(
        title="Tomorrow task", uploaded_by="me", due_date=d(1), start_date=d(1),
    )))
    uc.execute(CreateTaskCommand(input=CreateTaskInput(
        title="This-week task", uploaded_by="me", due_date=d(4), category="research",
    )))
    uc.execute(CreateTaskCommand(input=CreateTaskInput(
        title="Far-future task", uploaded_by="me", due_date=d(30),
    )))
    # Done task fabricated directly so completion_date is deterministic (TODAY).
    _make(
        repo, ObjectType.TASK, "Done task", task_scope="personal", due_date=TODAY,
        action_status="done", completion_date=TODAY,
    )

    CreateCalendarEntryUseCase(repo).execute(CreateCalendarEntryCommand(input=CreateEntryInput(
        title="Dentist appointment", uploaded_by="me", start_date=TODAY,
        start_time="17:00", end_time="17:30", location="City Care",
    )))
    return repo


# ---------------------------------------------------------------------------
# PART 3 — tasks lifecycle
# ---------------------------------------------------------------------------
def test_create_task_persists_scope_and_fields(world):
    out = CreateTaskUseCase(world).execute(
        CreateTaskCommand(
            input=CreateTaskInput(
                title="Write paper section", uploaded_by="me", description="Intro",
                priority="HIGH", category="Research", start_date=TODAY,
                due_date=d(6), reminder=d(5),
                tags=["paper", "phd"], remarks="draft v2",
            )
        )
    )
    assert out.metadata["task_scope"] == "personal"
    assert out.priority == "high" and out.category == "research"
    assert out.completed is False and out.overdue is False
    assert out.tags == ["paper", "phd"]
    stored = world.get_by_id(out.id)
    assert stored is not None and not stored.relationships  # no committee edge


def test_create_task_duplicate_title_due_409(world):
    with pytest.raises(ObjectAlreadyExistsError):
        CreateTaskUseCase(world).execute(
            CreateTaskCommand(
                input=CreateTaskInput(title="Today task", uploaded_by="me", due_date=TODAY)
            )
        )


def test_create_task_validation_matrix(world):
    uc = CreateTaskUseCase(world)
    with pytest.raises(ValidationError):
        uc.execute(CreateTaskCommand(input=CreateTaskInput(title=" ", uploaded_by="me")))
    with pytest.raises(ValidationError):
        uc.execute(CreateTaskCommand(input=CreateTaskInput(title="x", uploaded_by=" ")))
    with pytest.raises(ValidationError):
        uc.execute(CreateTaskCommand(input=CreateTaskInput(
            title="x", uploaded_by="me", due_date="3 Aug 2026")))
    with pytest.raises(ValidationError):
        uc.execute(CreateTaskCommand(input=CreateTaskInput(
            title="x", uploaded_by="me", priority="urgent")))
    with pytest.raises(ValidationError):
        uc.execute(CreateTaskCommand(input=CreateTaskInput(
            title="x", uploaded_by="me", start_date=d(7), due_date=d(1))))


def test_update_task_merge_and_complete_semantics(world):
    out = ListTasksUseCase(world).execute(ListTasksQuery(q="Tomorrow"))
    task = out.items[0]
    updated = UpdateTaskUseCase(world).execute(
        UpdateTaskCommand(
            object_id=task.id,
            input=UpdateTaskInput(uploaded_by="me", completed=True, priority="low"),
        )
    )
    assert updated.completed is True and updated.priority == "low"
    assert updated.completion_date is not None
    assert updated.due_date == d(1)  # untouched
    toggled = UpdateTaskUseCase(world).execute(
        UpdateTaskCommand(object_id=task.id, input=UpdateTaskInput(completed=False))
    )
    assert toggled.completed is False and not toggled.completion_date


def test_update_and_delete_guards(world):
    action = next(o for o in world.find_by_type(ObjectType.TASK) if o.title == "Prepare AQAR draft")
    with pytest.raises(ObjectNotFoundError):
        UpdateTaskUseCase(world).execute(
            UpdateTaskCommand(object_id=str(action.id), input=UpdateTaskInput(title="hijack"))
        )
    with pytest.raises(ObjectNotFoundError):
        DeleteTaskUseCase(world).execute(DeleteTaskCommand(object_id="obj:task:missing"))
    personal = next(o for o in world.find_by_type(ObjectType.TASK) if o.title == "Far-future task")
    DeleteTaskUseCase(world).execute(DeleteTaskCommand(object_id=str(personal.id)))
    assert world.get_by_id(personal.id) is None
    with pytest.raises(ObjectNotFoundError):
        GetTaskUseCase(world).execute(GetTaskQuery(object_id=str(personal.id)))


def test_list_tasks_filters_and_order(world):
    all_open = ListTasksUseCase(world).execute(ListTasksQuery(completed=False))
    titles = [i.title for i in all_open.items]
    assert titles[0] == "Today task"  # pinned first
    assert "Done task" not in titles
    overdue = ListTasksUseCase(world).execute(ListTasksQuery(overdue=True))
    assert [i.title for i in overdue.items] == ["Overdue task"]
    research = ListTasksUseCase(world).execute(ListTasksQuery(category="research"))
    assert [i.title for i in research.items] == ["This-week task"]
    window = ListTasksUseCase(world).execute(ListTasksQuery(due_from=d(1), due_to=d(4)))
    assert {i.title for i in window.items} == {"Tomorrow task", "This-week task"}
    hay = ListTasksUseCase(world).execute(ListTasksQuery(q="week task"))
    assert [i.title for i in hay.items] == ["This-week task"]


# ---------------------------------------------------------------------------
# PART 2 tail — personal calendar entries
# ---------------------------------------------------------------------------
def test_entry_crud_and_windows(world):
    uc = CreateCalendarEntryUseCase(world)
    entry = uc.execute(
        CreateCalendarEntryCommand(
            input=CreateEntryInput(
                title="Conference travel", uploaded_by="me", start_date=d(17),
                end_date=d(19), location="Chennai", category="Events",
            )
        )
    )
    assert entry.start_date == d(17) and entry.end_date == d(19)
    assert entry.category == "events"
    with pytest.raises(ObjectAlreadyExistsError):
        uc.execute(CreateCalendarEntryCommand(input=CreateEntryInput(
            title="Conference travel", uploaded_by="me", start_date=d(17))))
    with pytest.raises(ValidationError):
        uc.execute(CreateCalendarEntryCommand(input=CreateEntryInput(
            title="bad", uploaded_by="me", start_date=d(19), end_date=d(17))))


def test_entry_merge_window_422(world):
    uc = CreateCalendarEntryUseCase(world)
    entry = uc.execute(CreateCalendarEntryCommand(input=CreateEntryInput(
        title="Seminar", uploaded_by="me", start_date=d(17), end_date=d(19))))
    with pytest.raises(ValidationError):
        UpdateCalendarEntryUseCase(world).execute(
            UpdateCalendarEntryCommand(
                object_id=entry.id, input=UpdateEntryInput(end_date=d(16))
            )
        )
    ok = UpdateCalendarEntryUseCase(world).execute(
        UpdateCalendarEntryCommand(
            object_id=entry.id, input=UpdateEntryInput(start_date=d(16), title="Seminar II")
        )
    )
    assert ok.start_date == d(16) and ok.end_date == d(19) and ok.title == "Seminar II"
    with pytest.raises(ObjectNotFoundError):
        UpdateCalendarEntryUseCase(world).execute(
            UpdateCalendarEntryCommand(object_id="obj:calendar_entry:nope", input=UpdateEntryInput())
        )


# ---------------------------------------------------------------------------
# PART 1 + PART 2 — calendar aggregation
# ---------------------------------------------------------------------------
def test_calendar_feed_aggregates_all_sources(world):
    feed = GetCalendarFeedUseCase(world).execute(
        GetCalendarFeedQuery(date_from=d(-2), date_to=d(7))
    )
    by_source: dict[str, list] = {}
    for item in feed.items:
        by_source.setdefault(item.source, []).append(item)

    assert any(i.title == "Mathematics Day" for i in by_source["events"])
    meet = next(i for i in by_source["committee_meetings"] if i.title == "IQAC August Meet")
    assert meet.subtitle == "IQAC" and meet.date == TODAY
    assert any(i.title.endswith("— starts") for i in by_source["research_projects"])
    mile = next(i for i in by_source["grant_milestones"] if i.kind == "milestone")
    assert mile.date == d(1) and mile.subtitle == "Graph Frontiers"
    inst = next(i for i in by_source["grant_milestones"] if i.kind == "installment")
    assert "Installment #2" in inst.title and inst.date == d(2)
    assert any(i.title == "Linear Algebra" and i.start_time == "09:00" for i in by_source["teaching"])
    assert any(i.title == "Problem Set 4" for i in by_source["assignments"])
    assert any(i.kind == "session" for i in by_source["attendance_sessions"])
    assert any("PO PO-9" in i.title for i in by_source["finance_due"])
    assert any("Bill B-3" in i.title for i in by_source["finance_due"])
    assert any(i.title == "Prepare AQAR draft" for i in by_source["reports_due"])
    assert any(i.title == "Dentist appointment" and i.start_time == "17:00" for i in by_source["personal"])
    assert any(i.title == "Today task" and i.kind == "task" for i in by_source["personal"])

    personal_only = GetCalendarFeedUseCase(world).execute(
        GetCalendarFeedQuery(date_from=d(-2), date_to=d(7), sources=("personal",))
    )
    assert personal_only.sources == ["personal"]
    assert all(i.source == "personal" for i in personal_only.items)

    with pytest.raises(ValidationError):
        GetCalendarFeedUseCase(world).execute(
            GetCalendarFeedQuery(date_from=d(7), date_to=d(-2))
        )
    with pytest.raises(ValidationError):
        GetCalendarFeedUseCase(world).execute(
            GetCalendarFeedQuery(date_from=d(0), date_to=d(7), sources=("nope",))
        )


def test_weekly_schedule_expands_only_matching_weekdays(world):
    feed = GetCalendarFeedUseCase(world).execute(
        GetCalendarFeedQuery(date_from=TODAY, date_to=d(6), sources=("teaching",))
    )
    la = [i for i in feed.items if i.title == "Linear Algebra"]
    assert len(la) == 1 and la[0].date == TODAY
    feed2 = GetCalendarFeedUseCase(world).execute(
        GetCalendarFeedQuery(date_from=TODAY, date_to=d(13), sources=("teaching",))
    )
    assert len([i for i in feed2.items if i.title == "Linear Algebra"]) == 2


# ---------------------------------------------------------------------------
# PART 5 — reminder buckets
# ---------------------------------------------------------------------------
def test_reminder_buckets(world):
    out = GetRemindersUseCase(world).execute(GetRemindersQuery(as_of=TODAY))
    titles = {bucket: {i.title for i in items} for bucket, items in
              (("overdue", out.overdue), ("due_today", out.due_today),
               ("tomorrow", out.tomorrow), ("this_week", out.this_week))}
    assert "Overdue task" in titles["overdue"]
    assert "Prepare AQAR draft" in titles["overdue"]
    assert "Bill B-3 payable" in titles["overdue"]
    assert "Today task" in titles["due_today"]
    assert "Problem Set 4" in titles["due_today"]
    assert "Done task" not in titles["due_today"]
    assert "Tomorrow task" in titles["tomorrow"]
    assert "Interim report" in titles["tomorrow"]
    assert "PO PO-9 delivery" in titles["tomorrow"]
    assert "Installment #2" in titles["this_week"]
    assert "This-week task" in titles["this_week"]
    assert "Upload meeting minutes" in titles["this_week"]
    assert "Far-future task" not in (
        titles["overdue"] | titles["due_today"] | titles["tomorrow"] | titles["this_week"]
    )
    today_haps = {i.title for i in out.upcoming_today}
    assert {"Mathematics Day", "IQAC August Meet", "Linear Algebra"} <= today_haps


def test_dashboard_counts(world):
    dash = GetProductivityDashboardUseCase(world).execute(
        GetProductivityDashboardQuery(as_of=TODAY)
    )
    reminders = GetRemindersUseCase(world).execute(GetRemindersQuery(as_of=TODAY))
    assert dash.todays_tasks == 1            # Today task (Done task excluded)
    assert dash.completed_today == 1         # Done task (completion date = TODAY)
    assert dash.overdue_items == 3           # task + committee action + bill
    assert dash.upcoming_meetings == 2       # today's event + meeting (workshop is d(9))
    assert dash.unread_notifications == 0
    assert dash.upcoming_deadlines == len(reminders.tomorrow) + len(reminders.this_week)
    assert dash.upcoming_deadlines == 6      # 3 tomorrow + 3 this-week


# ---------------------------------------------------------------------------
# PART 4 — notification centre + engine sweep
# ---------------------------------------------------------------------------
def test_notification_state_machine(world):
    uc = CreateNotificationUseCase(world)
    note = uc.execute(
        CreateNotificationCommand(
            input=CreateNotificationInput(
                title="Call the library", uploaded_by="me", body="renew books",
                category="Task", priority="High", link="/productivity",
            )
        )
    )
    assert note.is_read is False and note.generated_by == "user" and note.category == "task"
    uuc = UpdateNotificationUseCase(world)
    read = uuc.execute(UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(is_read=True)))
    assert read.is_read is True and read.read_at is not None
    unread = uuc.execute(UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(is_read=False)))
    assert unread.is_read is False and not unread.read_at
    pinned = uuc.execute(UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(pinned=True)))
    assert pinned.pinned is True
    snoozed = uuc.execute(
        UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(snoozed_until="2999-01-01"))
    )
    assert snoozed.snoozed is True
    cleared = uuc.execute(
        UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(snoozed_until=""))
    )
    assert cleared.snoozed is False
    with pytest.raises(ValidationError):
        uuc.execute(UpdateNotificationCommand(object_id=note.id, input=UpdateNotificationInput(snoozed_until="next week")))
    with pytest.raises(ObjectNotFoundError):
        uuc.execute(UpdateNotificationCommand(object_id="obj:notification:nope", input=UpdateNotificationInput(is_read=True)))


def test_notification_list_states(world):
    uc = CreateNotificationUseCase(world)
    mine = uc.execute(CreateNotificationCommand(input=CreateNotificationInput(title="N1", uploaded_by="me")))
    other = uc.execute(CreateNotificationCommand(input=CreateNotificationInput(title="N2", uploaded_by="me")))
    UpdateNotificationUseCase(world).execute(
        UpdateNotificationCommand(object_id=other.id, input=UpdateNotificationInput(is_read=True))
    )
    luc = ListNotificationsUseCase(world)
    unread = luc.execute(ListNotificationsQuery(state="unread"))
    assert [i.title for i in unread.items] == ["N1"]
    assert unread.unread_count == 1
    read = luc.execute(ListNotificationsQuery(state="read"))
    assert [i.title for i in read.items] == ["N2"]
    archived = UpdateNotificationUseCase(world).execute(
        UpdateNotificationCommand(object_id=mine.id, input=UpdateNotificationInput(archived=True))
    )
    assert archived.archived is True
    assert luc.execute(ListNotificationsQuery(state=None)).total_count == 1  # only N2 active
    assert luc.execute(ListNotificationsQuery(state="archived")).total_count == 1
    assert luc.execute(ListNotificationsQuery(state="all")).total_count == 2
    with pytest.raises(ValidationError):
        luc.execute(ListNotificationsQuery(state="bogus"))


def test_refresh_is_idempotent_and_respects_shelves(world):
    ruc = RefreshNotificationsUseCase(world)
    first = ruc.execute(actor="me")
    assert first.created > 0 and first.skipped_existing == 0
    second = ruc.execute(actor="me")
    assert second.created == 0 and second.skipped_existing == first.considered

    notes = ListNotificationsUseCase(world).execute(ListNotificationsQuery(state="all", page_size=100))
    assert notes.unread_count == first.created
    assert all(n.generated_by == "reminder_engine" for n in notes.items)

    # Archiving never resurrects on the next sweep.
    target = notes.items[0]
    UpdateNotificationUseCase(world).execute(
        UpdateNotificationCommand(object_id=target.id, input=UpdateNotificationInput(archived=True))
    )
    third = ruc.execute(actor="me")
    assert third.created == 0


# ---------------------------------------------------------------------------
# PART 7 — unified search
# ---------------------------------------------------------------------------
def test_search_across_tasks_notifications_feed(world):
    res = ProductivitySearchUseCase(world).execute(ProductivitySearchQuery(q="task"))
    sources = {h.source for h in res.items}
    assert "tasks" in sources
    only_tasks = ProductivitySearchUseCase(world).execute(
        ProductivitySearchQuery(q="task", source="tasks")
    )
    assert all(h.source == "tasks" for h in only_tasks.items)
    high = ProductivitySearchUseCase(world).execute(
        ProductivitySearchQuery(q="Overdue", source="tasks", priority="high")
    )
    assert [h.title for h in high.items] == ["Overdue task"]
    windowed = ProductivitySearchUseCase(world).execute(
        ProductivitySearchQuery(source="calendar", date_from=TODAY, date_to=TODAY)
    )
    day_sources = {h.source for h in windowed.items}
    assert "events" in day_sources and "committee_meetings" in day_sources
    calendar_only = ProductivitySearchUseCase(world).execute(
        ProductivitySearchQuery(q="Dentist", source="calendar")
    )
    assert [h.title for h in calendar_only.items] == ["Dentist appointment"]
    with pytest.raises(ValidationError):
        ProductivitySearchUseCase(world).execute(ProductivitySearchQuery(source="bogus"))
    with pytest.raises(ValidationError):
        ProductivitySearchUseCase(world).execute(
            ProductivitySearchQuery(date_from=d(6), date_to=d(1))
        )
