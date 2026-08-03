"""Shared helpers for the Productivity Hub use cases.

Mirrors ``use_cases/events/helpers.py`` / the reports Snapshot doctrine:
one place that reads the frozen modules' universal objects and shapes the
module's outputs — no logic duplicated in routes, no state written anywhere
(except the user's own task/entry/notification objects, by their own use
cases).

Aggregation notes (PART 2 read-only sources, documented interpretation):
* ``reports_due`` — committee action items (TASK objects with a committee
  ``BELONGS_TO`` edge) with a due date: institutional reporting duties the
  owner must produce (AQAR, minutes, …). Personal tasks carry
  ``task_scope=personal`` and never a committee edge, so the two sets are
  disjoint by construction.
* ``grant_milestones`` — research project milestones not yet done plus
  scheduled grant installments (the dated deliverables tracked for grant
  reporting).
* ``finance_due`` — purchase orders awaiting delivery (``delivery_date`` set,
  status issued/acknowledged/partially_received) and unpaid/partially-paid
  bills (``bill_date`` = payable anchor).
* ``teaching`` — the classes' ``weekly_schedule`` slots expanded per weekday
  inside the requested window (window-bounded by design).
"""
from __future__ import annotations

import datetime as dt

from app.application.dtos.events import parse_json_list, parse_json_object_list
from app.application.dtos.productivity import (
    CALENDAR_SOURCES,
    KEY_ACTION_STATUS,
    KEY_ARCHIVED,
    KEY_CATEGORY,
    KEY_COMPLETION_DATE,
    KEY_DESCRIPTION,
    KEY_DUE_DATE,
    KEY_END_DATE,
    KEY_END_TIME,
    KEY_GENERATED_BY,
    KEY_IS_READ,
    KEY_LINK,
    KEY_LOCATION,
    KEY_PINNED,
    KEY_PRIORITY,
    KEY_REMARKS,
    KEY_REMINDER,
    KEY_SNOOZED_UNTIL,
    KEY_SOURCE_MODULE,
    KEY_SOURCE_REF,
    KEY_START_DATE,
    KEY_START_TIME,
    KEY_TAGS,
    KEY_TASK_SCOPE,
    MODULE_HREFS,
    CalendarItemOutput,
    EntryOutput,
    NotificationOutput,
    ReminderItemOutput,
    TaskOutput,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectType, RelationshipKind

# Frozen metadata keys re-declared locally (same string values — the local
# KEY_* doctrine; productivity never edits frozen files).
FROZEN_KEY_EVENT_STATUS = "event_status"
FROZEN_KEY_MEETING_DATE = "meeting_date"
FROZEN_KEY_MILESTONE_STATUS = "milestone_status"  # pending | in_progress | done
FROZEN_KEY_MILESTONE_DATE = "milestone_date"
FROZEN_KEY_INSTALLMENT_STATUS = "installment_status"  # scheduled | released
FROZEN_KEY_INSTALLMENT_DATE = "installment_date"
FROZEN_KEY_INSTALLMENT_NO = "installment_no"
FROZEN_KEY_WEEKLY_SCHEDULE = "weekly_schedule"
FROZEN_KEY_DEADLINE = "deadline"
FROZEN_KEY_SESSION_DATE = "session_date"
FROZEN_KEY_LIFECYCLE_STATUS = "lifecycle_status"
FROZEN_KEY_PURCHASE_ORDERS = "purchase_orders"
FROZEN_KEY_BILLS = "bills"

UPCOMING_EVENT_STATUSES = ("planned", "ongoing", "postponed")
OPEN_PO_STATUSES = ("issued", "acknowledged", "partially_received")
UNPAID_BILL_STATUSES = ("pending", "partial")
OPEN_MILESTONE_STATUSES = ("pending", "in_progress")
# Frozen teaching stores abbreviated weekday names (mon..sun — the frozen
# weekly_schedule validator); full names tolerated defensively.
WEEKDAY_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


# ---------------------------------------------------------------------------
# Small accessors
# ---------------------------------------------------------------------------
def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def today_iso(as_of: str | None = None) -> str:
    if as_of:
        return as_of
    return dt.date.today().isoformat()


def add_days(iso_date: str, days: int) -> str:
    base = dt.date.fromisoformat(iso_date)
    return (base + dt.timedelta(days=days)).isoformat()


def dates_in_window(date_from: str, date_to: str) -> list[str]:
    """Inclusive YYYY-MM-DD list between two ISO dates (window-bounded)."""
    start = dt.date.fromisoformat(date_from)
    end = dt.date.fromisoformat(date_to)
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)
    return days


def token_match(haystack: str, query: str | None) -> bool:
    """Token-AND case-insensitive match (the events/search precedent)."""
    if not query or not query.strip():
        return True
    hay = haystack.casefold()
    return all(token in hay for token in query.casefold().split())


def _base(obj: UniversalObject) -> dict:
    audit = obj.audit
    return {
        "id": str(obj.id),
        "title": obj.title,
        "status": obj.status.value,
        "version": obj.version,
        "uploaded_by": audit.created_by if audit else "",
        "created_at": audit.created_at.isoformat() if audit else "",
        "updated_at": audit.updated_at.isoformat() if audit and audit.updated_at else None,
    }


def _event_names(events: list | None, obj: UniversalObject) -> list[str]:
    source = events if events is not None else obj.pop_domain_events()
    return [getattr(event, "name", str(event)) for event in source]


def belongs_to_ids(obj: UniversalObject) -> list[str]:
    return [
        str(rel.target)
        for rel in obj.relationships
        if rel.kind is RelationshipKind.BELONGS_TO
    ]


# ---------------------------------------------------------------------------
# Object collectors
# ---------------------------------------------------------------------------
def is_personal_task(obj: UniversalObject) -> bool:
    return _meta(obj).get(KEY_TASK_SCOPE) == "personal"


def committee_action_tasks(all_tasks: list[UniversalObject]) -> list[UniversalObject]:
    """Committee action items = TASK objects with a BELONGS_TO (meeting) edge
    and NO personal scope marker — disjoint from personal tasks by design."""
    return [
        obj
        for obj in all_tasks
        if not is_personal_task(obj) and belongs_to_ids(obj)
    ]


def personal_tasks(all_tasks: list[UniversalObject]) -> list[UniversalObject]:
    return [obj for obj in all_tasks if is_personal_task(obj)]


def task_is_done(obj: UniversalObject) -> bool:
    return (_meta(obj).get(KEY_ACTION_STATUS) or "pending") == "done"


def task_is_overdue(obj: UniversalObject, today: str) -> bool:
    due = _meta(obj).get(KEY_DUE_DATE) or ""
    return bool(due) and due < today and not task_is_done(obj)


# ---------------------------------------------------------------------------
# Output shapers (the committees meeting_summary_output precedent)
# ---------------------------------------------------------------------------
def task_output(obj: UniversalObject, today: str, events: list | None = None) -> TaskOutput:
    meta = _meta(obj)
    status = meta.get(KEY_ACTION_STATUS) or "pending"
    return TaskOutput(
        **_base(obj),
        description=meta.get(KEY_DESCRIPTION),
        priority=meta.get(KEY_PRIORITY),
        category=meta.get(KEY_CATEGORY),
        start_date=meta.get(KEY_START_DATE),
        due_date=meta.get(KEY_DUE_DATE),
        completed=status == "done",
        completion_date=meta.get(KEY_COMPLETION_DATE),
        pinned=is_true(meta.get(KEY_PINNED)),
        reminder=meta.get(KEY_REMINDER),
        tags=parse_json_list(meta.get(KEY_TAGS)),
        remarks=meta.get(KEY_REMARKS),
        overdue=task_is_overdue(obj, today),
        metadata=meta,
        events=_event_names(events, obj),
    )


def entry_output(obj: UniversalObject, events: list | None = None) -> EntryOutput:
    meta = _meta(obj)
    return EntryOutput(
        **_base(obj),
        description=meta.get(KEY_DESCRIPTION),
        start_date=meta.get(KEY_START_DATE) or "",
        end_date=meta.get(KEY_END_DATE),
        start_time=meta.get(KEY_START_TIME),
        end_time=meta.get(KEY_END_TIME),
        location=meta.get(KEY_LOCATION),
        category=meta.get(KEY_CATEGORY),
        tags=parse_json_list(meta.get(KEY_TAGS)),
        metadata=meta,
        events=_event_names(events, obj),
    )


def notification_output(obj: UniversalObject, today: str, events: list | None = None) -> NotificationOutput:
    meta = _meta(obj)
    snoozed_until = meta.get(KEY_SNOOZED_UNTIL)
    return NotificationOutput(
        **_base(obj),
        body=meta.get("body"),
        category=meta.get(KEY_CATEGORY),
        priority=meta.get(KEY_PRIORITY),
        link=meta.get(KEY_LINK),
        source_module=meta.get(KEY_SOURCE_MODULE),
        source_ref=meta.get(KEY_SOURCE_REF),
        generated_by=meta.get(KEY_GENERATED_BY) or "user",
        is_read=is_true(meta.get(KEY_IS_READ)),
        read_at=meta.get("read_at"),
        pinned=is_true(meta.get(KEY_PINNED)),
        archived=is_true(meta.get(KEY_ARCHIVED)),
        snoozed_until=snoozed_until,
        snoozed=bool(snoozed_until) and str(snoozed_until) >= today,
        metadata=meta,
        events=_event_names(events, obj),
    )


def notification_is_active(obj: UniversalObject, today: str) -> bool:
    """Default Notification Center view: not archived, not currently snoozed."""
    meta = _meta(obj)
    if is_true(meta.get(KEY_ARCHIVED)):
        return False
    snoozed_until = meta.get(KEY_SNOOZED_UNTIL)
    return not (snoozed_until and str(snoozed_until) >= today)


def unread_count(objs: list[UniversalObject], today: str) -> int:
    return sum(
        1
        for obj in objs
        if notification_is_active(obj, today) and not is_true(_meta(obj).get(KEY_IS_READ))
    )


# ---------------------------------------------------------------------------
# Feed item factory
# ---------------------------------------------------------------------------
def _item(
    *,
    source: str,
    source_id: str,
    title: str,
    date: str,
    kind: str,
    date_end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    subtitle: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    occurrence: str | None = None,
    href: str | None = None,
) -> CalendarItemOutput:
    synthetic = f"{source}:{source_id}" + (f":{occurrence}" if occurrence else "")
    return CalendarItemOutput(
        id=synthetic,
        source=source,
        source_id=source_id,
        title=title,
        date=date,
        date_end=date_end,
        start_time=start_time,
        end_time=end_time,
        all_day=start_time is None,
        kind=kind,
        subtitle=subtitle,
        status=status,
        priority=priority,
        href=href or MODULE_HREFS.get(source, "/productivity"),
    )


def _in_range(day: str, date_from: str, date_to: str) -> bool:
    return date_from <= day <= date_to


def _overlaps(start: str, end: str, date_from: str, date_to: str) -> bool:
    return start <= date_to and end >= date_from


# ---------------------------------------------------------------------------
# The PART 2 aggregators (read-only over frozen objects)
# ---------------------------------------------------------------------------
def _feed_events(objects: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in objects:
        meta = _meta(obj)
        start = meta.get(KEY_START_DATE) or ""
        if not start:
            continue
        end = meta.get(KEY_END_DATE) or start
        if not _overlaps(start, end, date_from, date_to):
            continue
        items.append(
            _item(
                source="events",
                source_id=str(obj.id),
                title=obj.title,
                date=max(start, date_from),
                date_end=min(end, date_to) if end != start else None,
                kind="event",
                subtitle=meta.get("venue") or meta.get("department"),
                status=meta.get(FROZEN_KEY_EVENT_STATUS),
                href=f"/events/{obj.id}",
            )
        )
    return items


def _feed_meetings(
    meetings: list[UniversalObject], by_id: dict[str, UniversalObject], date_from: str, date_to: str
) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in meetings:
        meta = _meta(obj)
        day = meta.get(FROZEN_KEY_MEETING_DATE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        parents = belongs_to_ids(obj)
        committee = by_id.get(parents[0]) if parents else None
        items.append(
            _item(
                source="committee_meetings",
                source_id=str(obj.id),
                title=obj.title,
                date=day,
                kind="meeting",
                subtitle=committee.title if committee else None,
                start_time=meta.get("start_time"),
                end_time=meta.get("end_time"),
                status=meta.get("status"),
            )
        )
    return items


def _feed_projects(projects: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in projects:
        meta = _meta(obj)
        lifecycle = meta.get(FROZEN_KEY_LIFECYCLE_STATUS)
        for role, key in (("starts", KEY_START_DATE), ("due", KEY_END_DATE)):
            day = meta.get(key) or ""
            if not day or not _in_range(day, date_from, date_to):
                continue
            items.append(
                _item(
                    source="research_projects",
                    source_id=str(obj.id),
                    title=f"{obj.title} — {role}",
                    date=day,
                    kind="project",
                    status=lifecycle,
                    occurrence=role,
                )
            )
    return items


def _feed_grant_milestones(
    milestones: list[UniversalObject],
    installments: list[UniversalObject],
    by_id: dict[str, UniversalObject],
    date_from: str,
    date_to: str,
) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in milestones:
        meta = _meta(obj)
        status = meta.get(FROZEN_KEY_MILESTONE_STATUS) or "pending"
        if status == "done":
            continue
        day = meta.get(FROZEN_KEY_MILESTONE_DATE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        parents = belongs_to_ids(obj)
        project = by_id.get(parents[0]) if parents else None
        items.append(
            _item(
                source="grant_milestones",
                source_id=str(obj.id),
                title=obj.title,
                date=day,
                kind="milestone",
                subtitle=project.title if project else None,
                status=status,
            )
        )
    for obj in installments:
        meta = _meta(obj)
        if (meta.get(FROZEN_KEY_INSTALLMENT_STATUS) or "") != "scheduled":
            continue
        day = meta.get(FROZEN_KEY_INSTALLMENT_DATE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        parents = belongs_to_ids(obj)
        grant = by_id.get(parents[0]) if parents else None
        number = meta.get(FROZEN_KEY_INSTALLMENT_NO) or "?"
        items.append(
            _item(
                source="grant_milestones",
                source_id=str(obj.id),
                title=f"Installment #{number} — {grant.title if grant else obj.title}",
                date=day,
                kind="installment",
                subtitle=grant.title if grant else None,
                status="scheduled",
            )
        )
    return items


def _feed_teaching(classes: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    days = dates_in_window(date_from, date_to)
    for obj in classes:
        meta = _meta(obj)
        slots = parse_json_object_list(meta.get(FROZEN_KEY_WEEKLY_SCHEDULE))
        for index, slot in enumerate(slots):
            weekday = WEEKDAY_INDEX.get(str(slot.get("day") or "").strip().lower())
            if weekday is None:
                continue
            for day in days:
                if dt.date.fromisoformat(day).weekday() != weekday:
                    continue
                items.append(
                    _item(
                        source="teaching",
                        source_id=str(obj.id),
                        title=obj.title,
                        date=day,
                        kind="class",
                        start_time=str(slot.get("start")) if slot.get("start") else None,
                        end_time=str(slot.get("end")) if slot.get("end") else None,
                        subtitle=meta.get("programme") or meta.get("department"),
                        occurrence=f"{index}-{day}",
                    )
                )
    return items


def _feed_assignments(assignments: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in assignments:
        meta = _meta(obj)
        day = meta.get(FROZEN_KEY_DEADLINE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        items.append(
            _item(
                source="assignments",
                source_id=str(obj.id),
                title=obj.title,
                date=day,
                kind="assignment",
                status=meta.get("status"),
                priority="high",
            )
        )
    return items


def _feed_attendance_sessions(
    sessions: list[UniversalObject], by_id: dict[str, UniversalObject], date_from: str, date_to: str
) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in sessions:
        meta = _meta(obj)
        day = meta.get(FROZEN_KEY_SESSION_DATE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        parents = belongs_to_ids(obj)
        course = by_id.get(parents[0]) if parents else None
        items.append(
            _item(
                source="attendance_sessions",
                source_id=str(obj.id),
                title=obj.title if obj.title else (course.title if course else "Attendance session"),
                date=day,
                kind="session",
                subtitle=course.title if course else None,
            )
        )
    return items


def _feed_finance(proposals: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in proposals:
        meta = _meta(obj)
        for index, row in enumerate(parse_json_object_list(meta.get(FROZEN_KEY_PURCHASE_ORDERS))):
            status = str(row.get("status") or "").strip().lower()
            day = str(row.get("delivery_date") or "").strip()
            if status not in OPEN_PO_STATUSES or not day or not _in_range(day, date_from, date_to):
                continue
            items.append(
                _item(
                    source="finance_due",
                    source_id=str(obj.id),
                    title=f"PO {row.get('po_number') or '?'} delivery — {obj.title}",
                    date=day,
                    kind="finance",
                    subtitle=obj.title,
                    status=status,
                    occurrence=f"po-{index}",
                )
            )
        for row in parse_json_object_list(meta.get(FROZEN_KEY_BILLS)):
            status = str(row.get("payment_status") or "").strip().lower()
            day = str(row.get("bill_date") or "").strip()
            if status not in UNPAID_BILL_STATUSES or not day or not _in_range(day, date_from, date_to):
                continue
            items.append(
                _item(
                    source="finance_due",
                    source_id=str(obj.id),
                    title=f"Bill {row.get('bill_number') or '?'} payable — {obj.title}",
                    date=day,
                    kind="finance",
                    subtitle=obj.title,
                    status=status,
                    occurrence=f"bill-{index}",
                )
            )
    return items


def _feed_reports_due(tasks: list[UniversalObject], date_from: str, date_to: str) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in tasks:
        if task_is_done(obj):
            continue
        meta = _meta(obj)
        day = meta.get(KEY_DUE_DATE) or ""
        if not day or not _in_range(day, date_from, date_to):
            continue
        priority = meta.get(KEY_PRIORITY)
        items.append(
            _item(
                source="reports_due",
                source_id=str(obj.id),
                title=obj.title,
                date=day,
                kind="report_due",
                priority=priority,
                status=meta.get(KEY_ACTION_STATUS) or "pending",
            )
        )
    return items


def _feed_personal(
    tasks: list[UniversalObject],
    entries: list[UniversalObject],
    today: str,
    date_from: str,
    date_to: str,
) -> list[CalendarItemOutput]:
    items: list[CalendarItemOutput] = []
    for obj in tasks:
        meta = _meta(obj)
        if task_is_done(obj):
            continue
        due = meta.get(KEY_DUE_DATE) or ""
        if due and _in_range(due, date_from, date_to):
            items.append(
                _item(
                    source="personal",
                    source_id=str(obj.id),
                    title=obj.title,
                    date=due,
                    kind="task",
                    priority=meta.get(KEY_PRIORITY),
                    status=meta.get(KEY_ACTION_STATUS) or "pending",
                    occurrence="due",
                )
            )
        start = meta.get(KEY_START_DATE) or ""
        if start and start != due and _in_range(start, date_from, date_to):
            items.append(
                _item(
                    source="personal",
                    source_id=str(obj.id),
                    title=f"{obj.title} — start",
                    date=start,
                    kind="task",
                    priority=meta.get(KEY_PRIORITY),
                    status=meta.get(KEY_ACTION_STATUS) or "pending",
                    occurrence="start",
                )
            )
    for obj in entries:
        meta = _meta(obj)
        start = meta.get(KEY_START_DATE) or ""
        if not start:
            continue
        end = meta.get(KEY_END_DATE) or start
        if not _overlaps(start, end, date_from, date_to):
            continue
        items.append(
            _item(
                source="personal",
                source_id=str(obj.id),
                title=obj.title,
                date=max(start, date_from),
                date_end=min(end, date_to) if end != start else None,
                kind="entry",
                start_time=meta.get(KEY_START_TIME),
                end_time=meta.get(KEY_END_TIME),
                subtitle=meta.get(KEY_LOCATION),
                occurrence="entry",
            )
        )
    return items


# ---------------------------------------------------------------------------
# The one feed entry point
# ---------------------------------------------------------------------------
class ProductivitySnapshot:
    """One repository pass for every productivity read (the reports Snapshot
    precedent — all frozen objects fetched once, shared by aggregators)."""

    def __init__(self, repository) -> None:  # ObjectRepository — structural
        self.tasks_all = repository.find_by_type(ObjectType.TASK)
        self.events = repository.find_by_type(ObjectType.EVENT)
        self.meetings = repository.find_by_type(ObjectType.MEETING)
        self.projects = repository.find_by_type(ObjectType.RESEARCH_PROJECT)
        self.milestones = repository.find_by_type(ObjectType.PROJECT_MILESTONE)
        self.installments = repository.find_by_type(ObjectType.GRANT_INSTALLMENT)
        self.classes = repository.find_by_type(ObjectType.COURSE)
        self.assignments = repository.find_by_type(ObjectType.ASSIGNMENT)
        self.sessions = repository.find_by_type(ObjectType.ATTENDANCE_SESSION)
        self.proposals = repository.find_by_type(ObjectType.PURCHASE)
        self.entries = repository.find_by_type(ObjectType.CALENDAR_ENTRY)
        self.notifications = repository.find_by_type(ObjectType.NOTIFICATION)
        self._by_id: dict[str, UniversalObject] = {}
        for group in (
            self.tasks_all,
            self.events,
            self.meetings,
            self.projects,
            self.milestones,
            self.installments,
            self.classes,
            self.assignments,
            self.sessions,
            self.proposals,
            self.entries,
            self.notifications,
        ):
            for obj in group:
                self._by_id[str(obj.id)] = obj
        # parents we point at (committees, grants) once more, cheap on SQLite
        for needed in self._parent_ids() - set(self._by_id):
            found = repository.get_by_id(needed)
            if found is not None:
                self._by_id[str(found.id)] = found

    def _parent_ids(self) -> set[str]:
        ids: set[str] = set()
        for obj in self.meetings + self.milestones + self.installments + self.sessions:
            ids.update(belongs_to_ids(obj))
        return ids

    def by_id(self) -> dict[str, UniversalObject]:
        return self._by_id


_FEED_BUILDERS = (
    "events",
    "committee_meetings",
    "research_projects",
    "grant_milestones",
    "teaching",
    "assignments",
    "attendance_sessions",
    "finance_due",
    "reports_due",
    "personal",
)


def build_calendar_feed(
    snapshot: ProductivitySnapshot,
    date_from: str,
    date_to: str,
    sources: tuple[str, ...] | None,
    today: str,
) -> list[CalendarItemOutput]:
    wanted = tuple(sources) if sources else tuple(code for code, _ in CALENDAR_SOURCES)
    by_id = snapshot.by_id()
    items: list[CalendarItemOutput] = []
    if "events" in wanted:
        items += _feed_events(snapshot.events, date_from, date_to)
    if "committee_meetings" in wanted:
        items += _feed_meetings(snapshot.meetings, by_id, date_from, date_to)
    if "research_projects" in wanted:
        items += _feed_projects(snapshot.projects, date_from, date_to)
    if "grant_milestones" in wanted:
        items += _feed_grant_milestones(snapshot.milestones, snapshot.installments, by_id, date_from, date_to)
    if "teaching" in wanted:
        items += _feed_teaching(snapshot.classes, date_from, date_to)
    if "assignments" in wanted:
        items += _feed_assignments(snapshot.assignments, date_from, date_to)
    if "attendance_sessions" in wanted:
        items += _feed_attendance_sessions(snapshot.sessions, by_id, date_from, date_to)
    if "finance_due" in wanted:
        items += _feed_finance(snapshot.proposals, date_from, date_to)
    if "reports_due" in wanted:
        items += _feed_reports_due(committee_action_tasks(snapshot.tasks_all), date_from, date_to)
    if "personal" in wanted:
        items += _feed_personal(personal_tasks(snapshot.tasks_all), snapshot.entries, today, date_from, date_to)
    items.sort(key=lambda i: (i.date, i.start_time or "", i.title.casefold(), i.id))
    return items


# ---------------------------------------------------------------------------
# Reminder engine (PART 5)
# ---------------------------------------------------------------------------
def _reminder(source: str, obj: UniversalObject, title: str, day: str, subtitle: str | None = None, priority: str | None = None, href: str | None = None) -> ReminderItemOutput:
    return ReminderItemOutput(
        id=f"{source}:{obj.id}",
        source=source,
        title=title,
        date=day,
        subtitle=subtitle,
        priority=priority,
        href=href or "/productivity",
    )


def build_reminders(snapshot: ProductivitySnapshot, today: str) -> dict[str, list[ReminderItemOutput]]:
    """overdue | due_today | upcoming_today | tomorrow | this_week (PART 5).

    Due-work is drawn from personal tasks, committee action items, research
    milestones, scheduled grant installments, assignment deadlines and
    finance due dates; ``upcoming_today`` additionally carries today's
    scheduled happenings (events, committee meetings, class slots) so the
    panel answers "what is on today" as well as "what is due".
    """
    tomorrow = add_days(today, 1)
    week_end = add_days(today, 7)
    by_id = snapshot.by_id()

    dated: list[ReminderItemOutput] = []  # (due-driven items)
    for obj in personal_tasks(snapshot.tasks_all):
        if task_is_done(obj):
            continue
        meta = _meta(obj)
        due = meta.get(KEY_DUE_DATE)
        if due:
            dated.append(_reminder("tasks", obj, obj.title, due, priority=meta.get(KEY_PRIORITY)))
    for obj in committee_action_tasks(snapshot.tasks_all):
        if task_is_done(obj):
            continue
        meta = _meta(obj)
        due = meta.get(KEY_DUE_DATE)
        if due:
            dated.append(_reminder("committee_actions", obj, obj.title, due, priority=meta.get(KEY_PRIORITY), href="/committees"))
    for obj in snapshot.milestones:
        meta = _meta(obj)
        if (meta.get(FROZEN_KEY_MILESTONE_STATUS) or "pending") == "done":
            continue
        day = meta.get(FROZEN_KEY_MILESTONE_DATE)
        if day:
            parents = belongs_to_ids(obj)
            project = by_id.get(parents[0]) if parents else None
            dated.append(_reminder("milestones", obj, obj.title, day, subtitle=project.title if project else None, href="/research"))
    for obj in snapshot.installments:
        meta = _meta(obj)
        if (meta.get(FROZEN_KEY_INSTALLMENT_STATUS) or "") != "scheduled":
            continue
        day = meta.get(FROZEN_KEY_INSTALLMENT_DATE)
        if day:
            parents = belongs_to_ids(obj)
            grant = by_id.get(parents[0]) if parents else None
            number = meta.get(FROZEN_KEY_INSTALLMENT_NO) or "?"
            dated.append(_reminder("milestones", obj, f"Installment #{number}", day, subtitle=grant.title if grant else None, href="/research"))
    for obj in snapshot.assignments:
        meta = _meta(obj)
        day = meta.get(FROZEN_KEY_DEADLINE)
        if day:
            dated.append(_reminder("assignments", obj, obj.title, day, priority="high", href="/teaching"))
    for obj in snapshot.proposals:
        meta = _meta(obj)
        for row in parse_json_object_list(meta.get(FROZEN_KEY_PURCHASE_ORDERS)):
            status = str(row.get("status") or "").strip().lower()
            day = str(row.get("delivery_date") or "").strip()
            if status in OPEN_PO_STATUSES and day:
                dated.append(_reminder("finance", obj, f"PO {row.get('po_number') or '?'} delivery", day, subtitle=obj.title, href="/finance"))
        for row in parse_json_object_list(meta.get(FROZEN_KEY_BILLS)):
            status = str(row.get("payment_status") or "").strip().lower()
            day = str(row.get("bill_date") or "").strip()
            if status in UNPAID_BILL_STATUSES and day:
                dated.append(_reminder("finance", obj, f"Bill {row.get('bill_number') or '?'} payable", day, subtitle=obj.title, href="/finance"))

    buckets: dict[str, list[ReminderItemOutput]] = {
        "overdue": [],
        "due_today": [],
        "upcoming_today": [],
        "tomorrow": [],
        "this_week": [],
    }
    for item in dated:
        if item.date < today:
            buckets["overdue"].append(item)
        elif item.date == today:
            buckets["due_today"].append(item)
        elif item.date == tomorrow:
            buckets["tomorrow"].append(item)
        elif tomorrow < item.date <= week_end:
            buckets["this_week"].append(item)

    # Scheduled happenings due TODAY (not overdue-driven).
    feed_today = build_calendar_feed(snapshot, today, today, ("events", "committee_meetings", "teaching"), today)
    for feed_item in feed_today:
        buckets["upcoming_today"].append(
            ReminderItemOutput(
                id=feed_item.id,
                source=feed_item.source,
                title=feed_item.title,
                date=feed_item.date,
                subtitle=feed_item.subtitle,
                priority=feed_item.priority,
                href=feed_item.href,
            )
        )

    for bucket in buckets.values():
        bucket.sort(key=lambda i: (i.date, i.title.casefold(), i.id))
    return buckets


# ---------------------------------------------------------------------------
# Notification materialisation for the engine sweep (idempotent)
# ---------------------------------------------------------------------------
def engine_candidates(snapshot: ProductivitySnapshot, today: str) -> list[dict]:
    """Notification candidates from the reminder buckets (dedupe-safe).

    source_key = f"{bucket}:{source}:{object_id}:{date}" — one notification
    per reminder instance per day-window, never resurrected once archived.
    """
    buckets = build_reminders(snapshot, today)
    candidates: list[dict] = []
    for bucket_name, items in buckets.items():
        if bucket_name == "upcoming_today":
            continue  # schedule facts are calendar items, not nudges
        for item in items:
            candidates.append(
                {
                    "title": item.title,
                    "body": f"{bucket_name.replace('_', ' ').title()} — due {item.date}"
                    + (f" ({item.subtitle})" if item.subtitle else ""),
                    "category": _CATEGORY_BY_SOURCE.get(item.source, "deadline"),
                    "priority": item.priority or ("high" if bucket_name == "overdue" else "medium"),
                    "link": item.href,
                    "source_module": item.source,
                    "source_ref": item.id.split(":", 1)[1],
                    "source_key": f"{bucket_name}:{item.source}:{item.id}:{item.date}",
                }
            )
    return candidates


_CATEGORY_BY_SOURCE = {
    "tasks": "task",
    "committee_actions": "task",
    "milestones": "milestone",
    "assignments": "deadline",
    "finance": "finance",
    "events": "meeting",
    "committee_meetings": "meeting",
    "teaching": "meeting",
}
