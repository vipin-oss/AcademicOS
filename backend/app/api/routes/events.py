"""Events & Academic Activities API routes (personal activity slice).

Mirrors ``finance.py``/``committees.py`` one-to-one, backed by the frozen
Application layer:
  - GET    /events              -> ListEventsUseCase (PART 10 search/filters)
  - POST   /events              -> CreateEventUseCase (409 duplicates)
  - GET    /events/dashboard    -> GetEventsDashboardUseCase (PART 9 cards)
  - GET    /events/{id}         -> GetEventUseCase (enriched workspace)
  - PUT    /events/{id}         -> UpdateEventUseCase (merge contract)
  - PATCH  /events/{id}         -> UpdateEventUseCase (same handler)
  - DELETE /events/{id}         -> DeleteEventUseCase

The static branch (dashboard) is declared BEFORE the parameterised one so it
is never captured as an id (the committees precedent).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.mappers.events_mapper import (
    event_response,
    to_create_event_input,
    to_update_event_input,
)
from app.application.commands.create_event import CreateEventCommand
from app.application.commands.delete_event import DeleteEventCommand
from app.application.commands.update_event import UpdateEventCommand
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
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/events", tags=["events"])


# ---------------------------------------------------------------------------
# Request / response models (extra keys forbidden — frozen convention)
# ---------------------------------------------------------------------------
class CreateEventRequest(BaseModel):
    """JSON body for POST /events."""

    title: str
    uploaded_by: str
    status: str = "active"
    event_code: str | None = None
    event_type: str | None = None
    organizer: str | None = None
    co_organizer: str | None = None
    venue: str | None = None
    mode: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    objectives: str | None = None
    outcome: str | None = None
    event_status: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    participation: list[dict] | None = None
    speakers: list[dict] | None = None
    schedule: list[dict] | None = None
    registration: dict | None = None
    presentations: list[dict] | None = None
    links: dict | None = None


class UpdateEventRequest(CreateEventRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class EventResponseModel(BaseModel):
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    event_code: str | None
    event_type: str | None
    organizer: str | None
    co_organizer: str | None
    venue: str | None
    mode: str | None
    start_date: str | None
    end_date: str | None
    department: str | None
    school: str | None
    description: str | None
    objectives: str | None
    outcome: str | None
    event_status: str
    priority: str | None
    notes: str | None
    tags: list[str]
    participation: list[dict]
    speakers: list[dict]
    schedule: list[dict]
    registration: dict
    presentations: list[dict]
    links: dict
    stats: dict
    metadata: dict
    events: list[str]


class ListEventsResponseModel(BaseModel):
    items: list[EventResponseModel]
    total_count: int
    page: int
    page_size: int


class EventsDashboardModel(BaseModel):
    upcoming_events: int
    completed_events: int
    events_organized: int
    events_attended: int
    certificates: int
    presentations: int
    invited_talks: int


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
# Events directory (declared before /{event_id} so "dashboard" is never
# captured as an id — the committees precedent)
# ---------------------------------------------------------------------------
@router.get("", response_model=ListEventsResponseModel)
def list_events(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    event_type: str | None = Query(None),
    year: str | None = Query(None),
    role: str | None = Query(None),
    department: str | None = Query(None),
    organizer: str | None = Query(None),
    status_: str | None = Query(None, alias="status"),
):
    query = ListEventsQuery(
        page=page,
        page_size=page_size,
        q=q,
        event_type=event_type,
        year=year,
        role=role,
        department=department,
        organizer=organizer,
        status=status_,
    )
    try:
        result = ListEventsUseCase(repo).execute(query)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return ListEventsResponseModel(
        items=[EventResponseModel(**event_response(item)) for item in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=EventResponseModel, status_code=status.HTTP_201_CREATED)
def create_event(
    request: CreateEventRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = CreateEventUseCase(repo).execute(
            CreateEventCommand(input=to_create_event_input(body=request.model_dump()))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return EventResponseModel(**event_response(out))


@router.get("/dashboard", response_model=EventsDashboardModel)
def events_dashboard(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return GetEventsDashboardUseCase(repo).execute(GetEventsDashboardQuery())


@router.get("/{event_id}", response_model=EventResponseModel)
def get_event(event_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = GetEventUseCase(repo).execute(GetEventQuery(object_id=event_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return EventResponseModel(**event_response(out))


@router.put("/{event_id}", response_model=EventResponseModel)
def update_event(
    event_id: str,
    request: UpdateEventRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateEventUseCase(repo).execute(
            UpdateEventCommand(
                object_id=event_id,
                input=to_update_event_input(body=request.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return EventResponseModel(**event_response(out))


@router.patch("/{event_id}", response_model=EventResponseModel)
def patch_event(
    event_id: str,
    request: UpdateEventRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    return update_event(event_id, request, repo)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        DeleteEventUseCase(repo).execute(DeleteEventCommand(object_id=event_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
