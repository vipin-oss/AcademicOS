"""Productivity Hub API routes (personal productivity centre).

Mirrors ``events.py``/``finance.py`` one-to-one, backed by the frozen
Application layer:

  Dashboard / engine / feed / search (READ-ONLY aggregations):
  - GET  /productivity/dashboard              -> GetProductivityDashboardUseCase
  - GET  /productivity/calendar               -> GetCalendarFeedUseCase (window)
  - GET  /productivity/reminders              -> GetRemindersUseCase (PART 5 buckets)
  - POST /productivity/notifications/refresh  -> RefreshNotificationsUseCase
  - GET  /productivity/search                 -> ProductivitySearchUseCase (PART 7)

  Personal objects (own write paths, append-only ObjectType doctrine):
  - POST|GET        /productivity/tasks {/{id} PATCH, DELETE}
  - POST|GET        /productivity/calendar-entries {/{id} PATCH, DELETE}
  - POST|GET        /productivity/notifications {/{id} PATCH, DELETE}

Static branches (dashboard/calendar/reminders/search/refresh) are declared
BEFORE the parameterised ``/{task_id}``-style routes so they are never
captured as ids (the committees precedent).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.api.mappers.productivity_mapper import (
    output_dict,
    to_create_entry_input,
    to_create_notification_input,
    to_create_task_input,
    to_update_entry_input,
    to_update_notification_input,
    to_update_task_input,
)
from app.application.commands.create_calendar_entry import CreateCalendarEntryCommand
from app.application.commands.create_notification import CreateNotificationCommand
from app.application.commands.create_task import CreateTaskCommand
from app.application.commands.delete_calendar_entry import DeleteCalendarEntryCommand
from app.application.commands.delete_notification import DeleteNotificationCommand
from app.application.commands.delete_task import DeleteTaskCommand
from app.application.commands.update_calendar_entry import UpdateCalendarEntryCommand
from app.application.commands.update_notification import UpdateNotificationCommand
from app.application.commands.update_task import UpdateTaskCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_calendar_entry import GetCalendarEntryQuery
from app.application.queries.get_calendar_feed import GetCalendarFeedQuery
from app.application.queries.get_productivity_dashboard import (
    GetProductivityDashboardQuery,
)
from app.application.queries.get_reminders import GetRemindersQuery
from app.application.queries.get_task import GetTaskQuery
from app.application.queries.list_calendar_entries import ListCalendarEntriesQuery
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
from app.application.use_cases.productivity.delete_calendar_entry import (
    DeleteCalendarEntryUseCase,
)
from app.application.use_cases.productivity.delete_notification import (
    DeleteNotificationUseCase,
)
from app.application.use_cases.productivity.delete_task import DeleteTaskUseCase
from app.application.use_cases.productivity.get_calendar_entry import (
    GetCalendarEntryUseCase,
)
from app.application.use_cases.productivity.get_calendar_feed import (
    GetCalendarFeedUseCase,
)
from app.application.use_cases.productivity.get_dashboard import (
    GetProductivityDashboardUseCase,
)
from app.application.use_cases.productivity.get_reminders import GetRemindersUseCase
from app.application.use_cases.productivity.get_task import GetTaskUseCase
from app.application.use_cases.productivity.list_calendar_entries import (
    ListCalendarEntriesUseCase,
)
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
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/productivity", tags=["productivity"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Request / response models (extra keys forbidden — frozen convention)
# ---------------------------------------------------------------------------
class TaskRequest(BaseModel):
    """JSON body for POST /productivity/tasks."""

    title: str
    uploaded_by: str
    description: str | None = None
    priority: str | None = None
    category: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    completed: bool = False
    pinned: bool = False
    reminder: str | None = None
    tags: list[str] | None = None
    remarks: str | None = None


class UpdateTaskRequest(BaseModel):
    """JSON body for PATCH /productivity/tasks/{id} (merge semantics)."""

    uploaded_by: str = "system"
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    category: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    completed: bool | None = None
    pinned: bool | None = None
    reminder: str | None = None
    tags: list[str] | None = None
    remarks: str | None = None


class EntryRequest(BaseModel):
    """JSON body for POST /productivity/calendar-entries."""

    title: str
    uploaded_by: str
    start_date: str
    description: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class UpdateEntryRequest(BaseModel):
    """JSON body for PATCH /productivity/calendar-entries/{id}."""

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


class NotificationRequest(BaseModel):
    """JSON body for POST /productivity/notifications."""

    title: str
    uploaded_by: str
    body: str | None = None
    category: str | None = None
    priority: str | None = None
    link: str | None = None
    source_module: str | None = None
    source_ref: str | None = None


class UpdateNotificationRequest(BaseModel):
    """JSON body for PATCH /productivity/notifications/{id}."""

    uploaded_by: str = "system"
    is_read: bool | None = None
    pinned: bool | None = None
    archived: bool | None = None
    snoozed_until: str | None = None  # "" clears
    title: str | None = None
    body: str | None = None


class RefreshRequest(BaseModel):
    """JSON body for POST /productivity/notifications/refresh."""

    uploaded_by: str = "system"


# ---------------------------------------------------------------------------
# Infrastructure plumbing + error mapping (frozen helpers, same shape)
# ---------------------------------------------------------------------------
def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _not_found(exc: ObjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: ObjectAlreadyExistsError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


# ---------------------------------------------------------------------------
# Static read branches FIRST (dashboard / calendar / reminders / search)
# ---------------------------------------------------------------------------
@router.get("/dashboard")
def productivity_dashboard(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    as_of: str | None = Query(None),
):
    try:
        out = GetProductivityDashboardUseCase(repo).execute(
            GetProductivityDashboardQuery(as_of=as_of)
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/calendar")
def calendar_feed(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    date_from: str = Query(...),
    date_to: str = Query(...),
    sources: str | None = Query(None, description="CSV of source codes"),
):
    source_tuple = tuple(s.strip() for s in sources.split(",") if s.strip()) if sources else None
    try:
        out = GetCalendarFeedUseCase(repo).execute(
            GetCalendarFeedQuery(date_from=date_from, date_to=date_to, sources=source_tuple)
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/reminders")
def reminders(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    as_of: str | None = Query(None),
):
    out = GetRemindersUseCase(repo).execute(GetRemindersQuery(as_of=as_of))
    return output_dict(out)


@router.get("/search")
def productivity_search(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    q: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        out = ProductivitySearchUseCase(repo).execute(
            ProductivitySearchQuery(
                q=q,
                date_from=date_from,
                date_to=date_to,
                priority=priority,
                category=category,
                source=source,
                limit=limit,
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.post("/notifications/refresh", status_code=status.HTTP_200_OK)
def refresh_notifications(
    request: RefreshRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = RefreshNotificationsUseCase(repo).execute(actor=request.uploaded_by)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


# ---------------------------------------------------------------------------
# Personal Tasks (PART 3)
# ---------------------------------------------------------------------------
@router.get("/tasks")
def list_tasks(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    completed: bool | None = Query(None),
    pinned: bool | None = Query(None),
    overdue: bool | None = Query(None),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
):
    try:
        out = ListTasksUseCase(repo).execute(
            ListTasksQuery(
                page=page,
                page_size=page_size,
                q=q,
                priority=priority,
                category=category,
                completed=completed,
                pinned=pinned,
                overdue=overdue,
                due_from=due_from,
                due_to=due_to,
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    request: TaskRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = CreateTaskUseCase(repo).execute(
            CreateTaskCommand(input=to_create_task_input(body={**request.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = GetTaskUseCase(repo).execute(GetTaskQuery(object_id=task_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return output_dict(out)


@router.put("/tasks/{task_id}")
@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = UpdateTaskUseCase(repo).execute(
            UpdateTaskCommand(object_id=task_id, input=to_update_task_input(body={**request.model_dump(), "updated_by": str(user.id)}))
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        DeleteTaskUseCase(repo).execute(DeleteTaskCommand(object_id=task_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Personal Calendar Entries (PART 2 tail)
# ---------------------------------------------------------------------------
@router.get("/calendar-entries")
def list_calendar_entries(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    category: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    try:
        out = ListCalendarEntriesUseCase(repo).execute(
            ListCalendarEntriesQuery(
                page=page,
                page_size=page_size,
                q=q,
                category=category,
                date_from=date_from,
                date_to=date_to,
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.post("/calendar-entries", status_code=status.HTTP_201_CREATED)
def create_calendar_entry(
    request: EntryRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = CreateCalendarEntryUseCase(repo).execute(
            CreateCalendarEntryCommand(input=to_create_entry_input(body={**request.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/calendar-entries/{entry_id}")
def get_calendar_entry(entry_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = GetCalendarEntryUseCase(repo).execute(
            GetCalendarEntryQuery(object_id=entry_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return output_dict(out)


@router.put("/calendar-entries/{entry_id}")
@router.patch("/calendar-entries/{entry_id}")
def update_calendar_entry(
    entry_id: str,
    request: UpdateEntryRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = UpdateCalendarEntryUseCase(repo).execute(
            UpdateCalendarEntryCommand(
                object_id=entry_id, input=to_update_entry_input(body={**request.model_dump(), "updated_by": str(user.id)})
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.delete("/calendar-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar_entry(entry_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        DeleteCalendarEntryUseCase(repo).execute(DeleteCalendarEntryCommand(object_id=entry_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Notifications (PART 4)
# ---------------------------------------------------------------------------
@router.get("/notifications")
def list_notifications(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    state: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    source_module: str | None = Query(None),
):
    try:
        out = ListNotificationsUseCase(repo).execute(
            ListNotificationsQuery(
                page=page,
                page_size=page_size,
                q=q,
                state=state,
                priority=priority,
                category=category,
                source_module=source_module,
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.post("/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(
    request: NotificationRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = CreateNotificationUseCase(repo).execute(
            CreateNotificationCommand(input=to_create_notification_input(body={**request.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.put("/notifications/{notification_id}")
@router.patch("/notifications/{notification_id}")
def update_notification(
    notification_id: str,
    request: UpdateNotificationRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = UpdateNotificationUseCase(repo).execute(
            UpdateNotificationCommand(
                object_id=notification_id,
                input=to_update_notification_input(body={**request.model_dump(), "updated_by": str(user.id)}),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)
):
    try:
        DeleteNotificationUseCase(repo).execute(DeleteNotificationCommand(object_id=notification_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
