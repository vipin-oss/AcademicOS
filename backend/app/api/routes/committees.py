"""Committees & Meetings API routes (governance slice).

Mirrors ``research.py`` one-to-one, backed by the frozen Application layer:
  - GET    /committees                      -> ListCommitteesUseCase (PART 9 search/filters)
  - GET    /committees/dashboard            -> PART 8 cards + upcoming meetings
  - POST   /committees                      -> CreateCommitteeUseCase (409 duplicates)
  - GET    /committees/{id}                 -> GetCommitteeUseCase (enriched workspace)
  - PUT    /committees/{id}                 -> UpdateCommitteeUseCase (merge contract)
  - PATCH  /committees/{id}                 -> UpdateCommitteeUseCase (same handler)
  - DELETE /committees/{id}                 -> DeleteCommitteeUseCase (meetings cascade)
  - POST   /committees/{id}/meetings        -> AddMeetingUseCase (number unique 409)
  - GET    /committees/meetings/{mid}       -> GetMeetingUseCase (meeting workspace)
  - PUT    /committees/meetings/{mid}       -> UpdateMeetingUseCase (merge contract)
  - DELETE /committees/meetings/{mid}       -> DeleteMeetingUseCase (actions cascade)
  - POST   /committees/meetings/{mid}/actions -> AddActionItemUseCase (PART 5)
  - PUT    /committees/actions/{aid}        -> UpdateActionItemUseCase
  - DELETE /committees/actions/{aid}        -> DeleteActionItemUseCase

Static routes are declared BEFORE ``/{committee_id}`` so they are never
captured as an id (``meetings`` / ``actions`` / ``dashboard`` included).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.committee_mapper import (
    action_item_response,
    committee_response,
    meeting_response,
    to_create_action_item_input,
    to_create_committee_input,
    to_create_meeting_input,
    to_update_action_item_input,
    to_update_committee_input,
    to_update_meeting_input,
)
from app.application.commands.add_action_item import AddActionItemCommand
from app.application.commands.add_meeting import AddMeetingCommand
from app.application.commands.create_committee import CreateCommitteeCommand
from app.application.commands.delete_action_item import DeleteActionItemCommand
from app.application.commands.delete_committee import DeleteCommitteeCommand
from app.application.commands.delete_meeting import DeleteMeetingCommand
from app.application.commands.update_action_item import UpdateActionItemCommand
from app.application.commands.update_committee import UpdateCommitteeCommand
from app.application.commands.update_meeting import UpdateMeetingCommand
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
from app.application.use_cases.committees.delete_action_item import DeleteActionItemUseCase
from app.application.use_cases.committees.delete_committee import DeleteCommitteeUseCase
from app.application.use_cases.committees.delete_meeting import DeleteMeetingUseCase
from app.application.use_cases.committees.get_committee import GetCommitteeUseCase
from app.application.use_cases.committees.get_committees_dashboard import (
    GetCommitteesDashboardUseCase,
)
from app.application.use_cases.committees.get_meeting import GetMeetingUseCase
from app.application.use_cases.committees.list_committees import ListCommitteesUseCase
from app.application.use_cases.committees.update_action_item import UpdateActionItemUseCase
from app.application.use_cases.committees.update_committee import UpdateCommitteeUseCase
from app.application.use_cases.committees.update_meeting import UpdateMeetingUseCase
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/committees", tags=["committees"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Request / response models (extra keys forbidden — frozen convention)
# ---------------------------------------------------------------------------
class CreateCommitteeRequest(BaseModel):
    """JSON body for POST (registry fields optional)."""

    name: str
    uploaded_by: str
    status: str = "draft"
    committee_code: str | None = None
    committee_type: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    constitution_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    members: list[dict] | None = None
    links: dict | None = None


class UpdateCommitteeRequest(CreateCommitteeRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    name: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class CreateMeetingRequest(BaseModel):
    """JSON body for POST /committees/{id}/meetings."""

    title: str
    uploaded_by: str
    meeting_number: str | None = None
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    agenda_items: list[dict] | None = None
    minutes: str | None = None
    attendance: list[dict] | None = None
    decisions: list[str] | None = None
    remarks: str | None = None


class UpdateMeetingRequest(CreateMeetingRequest):
    """JSON body for PUT /committees/meetings/{id} (partial semantics)."""

    title: str | None = None
    uploaded_by: str = "system"


class CreateActionItemRequest(BaseModel):
    """JSON body for POST /committees/meetings/{id}/actions."""

    title: str
    uploaded_by: str
    assigned_to: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str = "pending"
    progress: int | None = 0
    completion_date: str | None = None
    remarks: str | None = None


class UpdateActionItemRequest(CreateActionItemRequest):
    """JSON body for PUT /committees/actions/{id} (partial semantics)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None
    progress: int | None = None


class LinkedObjectModel(BaseModel):
    id: str
    title: str
    object_type: str
    kind: str


class MemberModel(BaseModel):
    id: str
    name: str
    object_type: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    remarks: str | None = None


class MeetingSummaryModel(BaseModel):
    id: str
    title: str
    meeting_number: str | None = None
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    status: str


class ActionItemModel(BaseModel):
    id: str
    title: str
    status: str
    assigned_to: str | None = None
    assigned_name: str | None = None
    due_date: str | None = None
    priority: str | None = None
    progress: int = 0
    completion_date: str | None = None
    remarks: str | None = None
    meeting: LinkedObjectModel | None = None
    committee: LinkedObjectModel | None = None


class CommitteeStatsModel(BaseModel):
    meetings: int = 0
    pending_actions: int = 0
    completed_actions: int = 0


class CommitteeResponseModel(BaseModel):
    id: str
    name: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    committee_code: str | None = None
    committee_type: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    constitution_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    tags: list[str] = []
    members: list[MemberModel] = []
    meetings: list[MeetingSummaryModel] = []
    links: dict[str, list[LinkedObjectModel]] = {}
    stats: CommitteeStatsModel = CommitteeStatsModel()
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListCommitteesResponseModel(BaseModel):
    items: list[CommitteeResponseModel]
    total_count: int
    page: int
    page_size: int


class MeetingStatsModel(BaseModel):
    agenda_items: int = 0
    pending_actions: int = 0
    completed_actions: int = 0


class MeetingResponseModel(BaseModel):
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    meeting_number: str | None = None
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    agenda_items: list[dict] = []
    minutes: str | None = None
    attendance: list[dict] = []
    decisions: list[str] = []
    remarks: str | None = None
    committee: LinkedObjectModel | None = None
    action_items: list[ActionItemModel] = []
    stats: MeetingStatsModel = MeetingStatsModel()
    metadata: dict[str, str] = {}
    events: list[str] = []


class CommitteesDashboardModel(BaseModel):
    total_committees: int
    active_committees: int
    meetings_this_month: int
    pending_actions: int
    completed_actions: int
    upcoming_meetings: list[dict]


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
# Directory list + create
# ---------------------------------------------------------------------------
@router.get("", response_model=ListCommitteesResponseModel)
def list_committees(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    committee_type: str | None = Query(None),
    department: str | None = Query(None),
    status_: str | None = Query(None, alias="status"),
    chairperson: str | None = Query(None),
    meeting_year: int | None = Query(None),
):
    query = ListCommitteesQuery(
        page=page,
        page_size=page_size,
        q=q,
        committee_type=committee_type,
        department=department,
        status=status_,
        chairperson=chairperson,
        meeting_year=meeting_year,
    )
    try:
        result = ListCommitteesUseCase(repo).execute(query)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return ListCommitteesResponseModel(
        items=[CommitteeResponseModel(**committee_response(item)) for item in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=CommitteeResponseModel, status_code=status.HTTP_201_CREATED)
def create_committee(
    request: CreateCommitteeRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = CreateCommitteeUseCase(repo).execute(
            CreateCommitteeCommand(
                input=to_create_committee_input(body=request.model_dump())
            )
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return CommitteeResponseModel(**committee_response(out))


# ---------------------------------------------------------------------------
# Dashboard + meetings/action static branches (declared before /{committee_id})
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=CommitteesDashboardModel)
def committees_dashboard(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    upcoming_limit: int = Query(10, ge=1, le=50),
):
    dashboard = GetCommitteesDashboardUseCase(repo).execute(
        GetCommitteesDashboardQuery(upcoming_limit=upcoming_limit)
    )
    return CommitteesDashboardModel(**dashboard.__dict__)


@router.post(
    "/{committee_id}/meetings",
    response_model=MeetingResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def add_meeting(
    committee_id: str,
    request: CreateMeetingRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = AddMeetingUseCase(repo).execute(
            AddMeetingCommand(
                committee_id=committee_id,
                input=to_create_meeting_input(
                    committee_id=committee_id, body=request.model_dump()
                ),
                actor=request.uploaded_by,
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return MeetingResponseModel(**meeting_response(out))


@router.get("/meetings/{meeting_id}", response_model=MeetingResponseModel)
def get_meeting(
    meeting_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = GetMeetingUseCase(repo).execute(GetMeetingQuery(meeting_id=meeting_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return MeetingResponseModel(**meeting_response(out))


@router.put("/meetings/{meeting_id}", response_model=MeetingResponseModel)
def update_meeting(
    meeting_id: str,
    request: UpdateMeetingRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateMeetingUseCase(repo).execute(
            UpdateMeetingCommand(
                meeting_id=meeting_id,
                input=to_update_meeting_input(body=request.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return MeetingResponseModel(**meeting_response(out))


@router.delete("/meetings/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(
    meeting_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        DeleteMeetingUseCase(repo).execute(DeleteMeetingCommand(meeting_id=meeting_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/meetings/{meeting_id}/actions",
    response_model=ActionItemModel,
    status_code=status.HTTP_201_CREATED,
)
def add_action_item(
    meeting_id: str,
    request: CreateActionItemRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = AddActionItemUseCase(repo).execute(
            AddActionItemCommand(
                meeting_id=meeting_id,
                input=to_create_action_item_input(
                    meeting_id=meeting_id, body=request.model_dump()
                ),
                actor=request.uploaded_by,
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return ActionItemModel(**action_item_response(out))


@router.put("/actions/{action_id}", response_model=ActionItemModel)
def update_action_item(
    action_id: str,
    request: UpdateActionItemRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateActionItemUseCase(repo).execute(
            UpdateActionItemCommand(
                action_id=action_id,
                input=to_update_action_item_input(
                    body=request.model_dump(exclude_unset=True)
                ),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return ActionItemModel(**action_item_response(out))


@router.delete("/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action_item(
    action_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        DeleteActionItemUseCase(repo).execute(DeleteActionItemCommand(action_id=action_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Committee detail / update / delete (declared after the static branches)
# ---------------------------------------------------------------------------
@router.get("/{committee_id}", response_model=CommitteeResponseModel)
def get_committee(
    committee_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = GetCommitteeUseCase(repo).execute(GetCommitteeQuery(object_id=committee_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return CommitteeResponseModel(**committee_response(out))


@router.put("/{committee_id}", response_model=CommitteeResponseModel)
def update_committee(
    committee_id: str,
    request: UpdateCommitteeRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateCommitteeUseCase(repo).execute(
            UpdateCommitteeCommand(
                object_id=committee_id,
                input=to_update_committee_input(body=request.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return CommitteeResponseModel(**committee_response(out))


@router.patch("/{committee_id}", response_model=CommitteeResponseModel)
def patch_committee(
    committee_id: str,
    request: UpdateCommitteeRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    return update_committee(committee_id, request, repo)


@router.delete("/{committee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_committee(
    committee_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        DeleteCommitteeUseCase(repo).execute(DeleteCommitteeCommand(object_id=committee_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Keep the frozen mapper import referenced (ObjectId is used by sibling routes).
_ = ObjectId
