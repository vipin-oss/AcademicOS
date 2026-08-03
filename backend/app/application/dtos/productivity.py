"""DTOs (application boundary) for the Productivity Hub module.

Personal productivity centre: calendar aggregation, personal tasks,
notifications and the reminder engine. Mirrors the ``dtos/events.py`` /
``dtos/committee.py`` conventions one-to-one:

* file-local ``KEY_*`` metadata keys (same string values as the owning
  frozen modules where semantics align — the ``KEY_START_DATE`` precedent
  shared by events + research; productivity never imports another module's
  constants so frozen files stay untouched),
* labelled vocabularies with server-facing code + display label,
* section/link group whitelists (unknown keys dropped on write),
* Create/Update inputs carrying ``uploaded_by`` (actor) like the events dto.

Storage doctrine (append-only, the VENDOR precedent): personal tasks are
``ObjectType.TASK`` objects carrying ``task_scope=personal`` and **no**
committee ``BELONGS_TO`` edge — the committees helper lenses filter actions
by that edge, so personal tasks can never leak into committee views; calendar
entries are ``ObjectType.CALENDAR_ENTRY``; notifications are
``ObjectType.NOTIFICATION``. All are universal objects with L6 human-asserted
metadata — domain events and audit trail come free from the frozen aggregate.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Metadata keys (productivity-owned; identical string values to the frozen
# owners where semantics align — committee actions / finance proposals)
# ---------------------------------------------------------------------------
KEY_TASK_SCOPE = "task_scope"  # personal | (committee actions carry none)
KEY_DESCRIPTION = "description"
KEY_CATEGORY = "category"
KEY_START_DATE = "start_date"  # YYYY-MM-DD (same value as events/research)
KEY_END_DATE = "end_date"
KEY_START_TIME = "start_time"  # HH:MM (24-hour)
KEY_END_TIME = "end_time"
KEY_LOCATION = "location"
KEY_DUE_DATE = "due_date"  # same value as the committee action key
KEY_PRIORITY = "priority"  # high | medium | low (committee/finance value)
KEY_ACTION_STATUS = "action_status"  # pending | in_progress | done (committee value)
KEY_COMPLETION_DATE = "completion_date"  # same value as committee actions
KEY_PINNED = "pinned"  # "true" | "false"
KEY_REMINDER = "reminder"  # YYYY-MM-DD the owner wants a nudge on
KEY_TAGS = "tags"  # JSON string list (the events precedent)
KEY_REMARKS = "remarks"  # same value as committee actions

# Notification-only keys
KEY_BODY = "body"
KEY_LINK = "link"  # frontend href to the related module page
KEY_SOURCE_MODULE = "source_module"  # tasks | events | committees | research | finance | teaching | reports | system
KEY_SOURCE_REF = "source_ref"  # related universal object id (optional)
KEY_SOURCE_KEY = "source_key"  # engine dedupe key, unique per reminder instance
KEY_GENERATED_BY = "generated_by"  # user | reminder_engine
KEY_IS_READ = "is_read"  # "true" | "false"
KEY_READ_AT = "read_at"  # YYYY-MM-DD
KEY_ARCHIVED = "archived"  # "true" | "false"
KEY_SNOOZED_UNTIL = "snoozed_until"  # YYYY-MM-DD inclusive

# ---------------------------------------------------------------------------
# Vocabularies (code -> display label; events labelled-vocab precedent)
# ---------------------------------------------------------------------------
TASK_PRIORITIES: tuple[tuple[str, str], ...] = (
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
)
TASK_PRIORITY_CODES = tuple(code for code, _ in TASK_PRIORITIES)

TASK_STATUSES: tuple[tuple[str, str], ...] = (
    ("pending", "Pending"),
    ("in_progress", "In Progress"),
    ("done", "Done"),
)
TASK_STATUS_CODES = tuple(code for code, _ in TASK_STATUSES)

TASK_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("research", "Research"),
    ("teaching", "Teaching"),
    ("committees", "Committees"),
    ("finance", "Finance"),
    ("events", "Events"),
    ("publications", "Publications"),
    ("personal", "Personal"),
    ("admin", "Administration"),
    ("other", "Other"),
)
TASK_CATEGORY_CODES = tuple(code for code, _ in TASK_CATEGORIES)

NOTIFICATION_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("task", "Task"),
    ("deadline", "Deadline"),
    ("meeting", "Meeting"),
    ("finance", "Finance"),
    ("milestone", "Milestone"),
    ("system", "System"),
)
NOTIFICATION_CATEGORY_CODES = tuple(code for code, _ in NOTIFICATION_CATEGORIES)

NOTIFICATION_PRIORITIES: tuple[tuple[str, str], ...] = TASK_PRIORITIES
NOTIFICATION_PRIORITY_CODES = TASK_PRIORITY_CODES

NOTIFICATION_GENERATORS = ("user", "reminder_engine")

# Calendar feed sources (PART 2) — read-only aggregation keys.
CALENDAR_SOURCES: tuple[tuple[str, str], ...] = (
    ("events", "Events"),
    ("committee_meetings", "Committee Meetings"),
    ("research_projects", "Research Projects"),
    ("grant_milestones", "Grant Milestones"),
    ("teaching", "Teaching"),
    ("assignments", "Assignments"),
    ("attendance_sessions", "Attendance Sessions"),
    ("finance_due", "Finance Due Dates"),
    ("reports_due", "Reports Due"),
    ("personal", "Personal Entries & Tasks"),
)
CALENDAR_SOURCE_CODES = tuple(code for code, _ in CALENDAR_SOURCES)

# Kinds are the render taxonomy the frontend uses for badges/colours.
CALENDAR_ITEM_KINDS = (
    "event",
    "meeting",
    "project",
    "milestone",
    "installment",
    "class",
    "assignment",
    "session",
    "finance",
    "report_due",
    "task",
    "entry",
)

# Frontend hrefs per module (frozen route map).
MODULE_HREFS: dict[str, str] = {
    "events": "/events",
    "committee_meetings": "/committees",
    "research_projects": "/research",
    "grant_milestones": "/research",
    "teaching": "/teaching",
    "assignments": "/teaching",
    "attendance_sessions": "/teaching",
    "finance_due": "/finance",
    "reports_due": "/committees",
    "personal": "/productivity",
}

# ---------------------------------------------------------------------------
# Personal Tasks (PART 3) — inputs / outputs
# ---------------------------------------------------------------------------
@dataclass
class CreateTaskInput:
    title: str
    uploaded_by: str
    description: str | None = None
    priority: str | None = None  # TASK_PRIORITY_CODES
    category: str | None = None  # TASK_CATEGORY_CODES
    start_date: str | None = None
    due_date: str | None = None
    completed: bool = False
    pinned: bool = False
    reminder: str | None = None
    tags: list[str] | None = None
    remarks: str | None = None


@dataclass
class UpdateTaskInput:
    uploaded_by: str = "system"
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    category: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    completed: bool | None = None  # three-state: None = untouched
    pinned: bool | None = None
    reminder: str | None = None
    tags: list[str] | None = None
    remarks: str | None = None


@dataclass
class TaskOutput:
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    description: str | None
    priority: str | None
    category: str | None
    start_date: str | None
    due_date: str | None
    completed: bool
    completion_date: str | None
    pinned: bool
    reminder: str | None
    tags: list[str]
    remarks: str | None
    overdue: bool  # server-computed: due_date < today and not done
    metadata: dict
    events: list[str]


@dataclass
class ListTasksResult:
    items: list[TaskOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Personal Calendar Entries (PART 2 tail) — inputs / outputs
# ---------------------------------------------------------------------------
@dataclass
class CreateEntryInput:
    title: str
    uploaded_by: str
    start_date: str  # required anchor date
    description: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    category: str | None = None
    tags: list[str] | None = None


@dataclass
class UpdateEntryInput:
    uploaded_by: str = "system"
    title: str | None = None
    start_date: str | None = None
    description: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    category: str | None = None
    tags: list[str] | None = None


@dataclass
class EntryOutput:
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    description: str | None
    start_date: str
    end_date: str | None
    start_time: str | None
    end_time: str | None
    location: str | None
    category: str | None
    tags: list[str]
    metadata: dict
    events: list[str]


@dataclass
class ListCalendarEntriesResult:
    items: list[EntryOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Notifications (PART 4) — inputs / outputs
# ---------------------------------------------------------------------------
@dataclass
class CreateNotificationInput:
    title: str
    uploaded_by: str
    body: str | None = None
    category: str | None = None
    priority: str | None = None
    link: str | None = None
    source_module: str | None = None
    source_ref: str | None = None


@dataclass
class UpdateNotificationInput:
    uploaded_by: str = "system"
    is_read: bool | None = None  # three-state toggles
    pinned: bool | None = None
    archived: bool | None = None
    snoozed_until: str | None = None  # "" clears the snooze
    title: str | None = None
    body: str | None = None


@dataclass
class NotificationOutput:
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    body: str | None
    category: str | None
    priority: str | None
    link: str | None
    source_module: str | None
    source_ref: str | None
    generated_by: str
    is_read: bool
    read_at: str | None
    pinned: bool
    archived: bool
    snoozed_until: str | None
    snoozed: bool  # server-computed: snoozed_until >= today
    metadata: dict
    events: list[str]


@dataclass
class ListNotificationsResult:
    items: list[NotificationOutput]
    total_count: int
    page: int
    page_size: int
    unread_count: int  # across the unarchived, unsnoozed full set (PART 6)


@dataclass
class RefreshNotificationsResult:
    created: int
    skipped_existing: int
    considered: int


# ---------------------------------------------------------------------------
# Calendar feed (PART 1 + PART 2) — normalised aggregated item
# ---------------------------------------------------------------------------
@dataclass
class CalendarItemOutput:
    id: str  # synthetic: f"{source}:{object_id}[:occurrence]"
    source: str  # CALENDAR_SOURCE_CODES
    source_id: str  # backing universal object id
    title: str
    date: str  # YYYY-MM-DD anchor (occurrence date for recurring slots)
    date_end: str | None
    start_time: str | None
    end_time: str | None
    all_day: bool
    kind: str  # CALENDAR_ITEM_KINDS
    subtitle: str | None  # committee name / project title / venue …
    status: str | None
    priority: str | None
    href: str


@dataclass
class CalendarFeedResult:
    items: list[CalendarItemOutput]
    date_from: str
    date_to: str
    sources: list[str]


# ---------------------------------------------------------------------------
# Reminder engine (PART 5) — bucketed due-work view
# ---------------------------------------------------------------------------
@dataclass
class ReminderItemOutput:
    id: str  # f"{source}:{object_id}"
    source: str  # tasks | committee_actions | milestones | assignments | finance | events | committee_meetings
    title: str
    date: str  # the date that drives the bucket
    subtitle: str | None
    priority: str | None
    href: str


@dataclass
class RemindersResult:
    overdue: list[ReminderItemOutput]
    due_today: list[ReminderItemOutput]
    upcoming_today: list[ReminderItemOutput]  # today's meetings/events/classes
    tomorrow: list[ReminderItemOutput]
    this_week: list[ReminderItemOutput]  # > tomorrow .. today+7
    generated_at: str


# ---------------------------------------------------------------------------
# Dashboard (PART 6)
# ---------------------------------------------------------------------------
@dataclass
class ProductivityDashboardOutput:
    todays_tasks: int
    upcoming_deadlines: int
    upcoming_meetings: int
    unread_notifications: int
    overdue_items: int
    completed_today: int


# ---------------------------------------------------------------------------
# Search (PART 7) — unified hit across tasks / notifications / feed
# ---------------------------------------------------------------------------
@dataclass
class SearchHitOutput:
    id: str
    source: str  # tasks | notifications | CALENDAR_SOURCE_CODES
    kind: str
    title: str
    date: str | None
    priority: str | None
    category: str | None
    snippet: str | None
    href: str


@dataclass
class ProductivitySearchResult:
    items: list[SearchHitOutput]
    total_count: int
