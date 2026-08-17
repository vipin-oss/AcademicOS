"""Research API routes — Projects & Grants management slice.

Mirrors ``students.py``/``teaching.py`` one-to-one, backed by the frozen
Application layer (Projects, Grants, Agencies, Milestones, Installments and
Expenditures are all Universal Objects):

  - GET    /research/dashboard                          -> PART 10 cards + deadlines
  - GET    /research/projects                           -> filters (PART 9) + object lens
  - POST   /research/projects                           -> 201 (409 duplicate project code)
  - GET    /research/projects/{id}                      -> enriched workspace payload
  - PUT    /research/projects/{id} / PATCH              -> merge update + lifecycle
  - DELETE /research/projects/{id}                      -> 204 (milestones cascade)
  - POST   /research/projects/{id}/milestones           -> timeline milestone (PART 8)
  - POST   /research/projects/{id}/updates              -> progress update (PART 8)
  - PUT|PATCH|DELETE /research/milestones/{id}          -> milestone edit / delete
  - GET    /research/grants                             -> q + project/agency lenses
  - POST   /research/grants                             -> 201 (409 duplicate grant number)
  - GET    /research/grants/{id}                        -> enriched grant workspace payload
  - PUT    /research/grants/{id} / PATCH                -> merge update
  - DELETE /research/grants/{id}                        -> 204 (children cascade)
  - POST   /research/grants/{id}/installments           -> released ≤ sanctioned guard
  - POST   /research/grants/{id}/expenditures           -> utilized ≤ sanctioned guard
  - DELETE /research/installments/{id}                  -> 204 (correction path)
  - DELETE /research/expenditures/{id}                  -> 204 (correction path)
  - GET    /research/agencies                           -> registry list + search
  - POST   /research/agencies                           -> 201 (409 duplicate name)
  - GET    /research/agencies/{id}                      -> one agency
  - PUT    /research/agencies/{id} / PATCH              -> merge update
  - DELETE /research/agencies/{id}                      -> 204

Static routes are declared BEFORE parameterised ones so ids never capture
``dashboard``/``agencies``/``installments``/… .
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_object_acl
from app.domain.entities.object import UniversalObject
from app.api.mappers.research_mapper import (
    agency_response,
    dashboard_response,
    expenditure_response,
    grant_response,
    installment_response,
    milestone_response,
    project_response,
    to_create_agency_input,
    to_create_grant_input,
    to_create_project_input,
    to_expenditure_input,
    to_installment_input,
    to_milestone_input,
    to_progress_update_input,
    to_update_agency_input,
    to_update_grant_input,
    to_update_milestone_input,
    to_update_project_input,
)
from app.application.commands.add_installment import AddInstallmentCommand
from app.application.commands.add_milestone import AddMilestoneCommand
from app.application.commands.create_agency import CreateAgencyCommand
from app.application.commands.create_grant import CreateGrantCommand
from app.application.commands.create_project import CreateProjectCommand
from app.application.commands.delete_agency import DeleteAgencyCommand
from app.application.commands.delete_expenditure import DeleteExpenditureCommand
from app.application.commands.delete_grant import DeleteGrantCommand
from app.application.commands.delete_installment import DeleteInstallmentCommand
from app.application.commands.delete_milestone import DeleteMilestoneCommand
from app.application.commands.delete_project import DeleteProjectCommand
from app.application.commands.record_expenditure import RecordExpenditureCommand
from app.application.commands.record_progress_update import RecordProgressUpdateCommand
from app.application.commands.update_agency import UpdateAgencyCommand
from app.application.commands.update_grant import UpdateGrantCommand
from app.application.commands.update_milestone import UpdateMilestoneCommand
from app.application.commands.update_project import UpdateProjectCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_agency import GetAgencyQuery
from app.application.queries.get_grant import GetGrantQuery
from app.application.queries.get_project import GetProjectQuery
from app.application.queries.get_research_dashboard import GetResearchDashboardQuery
from app.application.queries.list_agencies import ListAgenciesQuery
from app.application.queries.list_grants import ListGrantsQuery
from app.application.queries.list_projects import ListProjectsQuery
from app.application.use_cases.research.add_installment import AddInstallmentUseCase
from app.application.use_cases.research.add_milestone import AddMilestoneUseCase
from app.application.use_cases.research.create_agency import CreateAgencyUseCase
from app.application.use_cases.research.create_grant import CreateGrantUseCase
from app.application.use_cases.research.create_project import CreateProjectUseCase
from app.application.use_cases.research.delete_agency import DeleteAgencyUseCase
from app.application.use_cases.research.delete_expenditure import DeleteExpenditureUseCase
from app.application.use_cases.research.delete_grant import DeleteGrantUseCase
from app.application.use_cases.research.delete_installment import DeleteInstallmentUseCase
from app.application.use_cases.research.delete_milestone import DeleteMilestoneUseCase
from app.application.use_cases.research.delete_project import DeleteProjectUseCase
from app.application.use_cases.research.get_agency import GetAgencyUseCase
from app.application.use_cases.research.get_grant import GetGrantUseCase
from app.application.use_cases.research.get_project import GetProjectUseCase
from app.application.use_cases.research.get_research_dashboard import (
    GetResearchDashboardUseCase,
)
from app.application.use_cases.research.list_agencies import ListAgenciesUseCase
from app.application.use_cases.research.list_grants import ListGrantsUseCase
from app.application.use_cases.research.list_projects import ListProjectsUseCase
from app.application.use_cases.research.record_expenditure import RecordExpenditureUseCase
from app.application.use_cases.research.record_progress_update import (
    RecordProgressUpdateUseCase,
)
from app.application.use_cases.research.update_agency import UpdateAgencyUseCase
from app.application.use_cases.research.update_grant import UpdateGrantUseCase
from app.application.use_cases.research.update_milestone import UpdateMilestoneUseCase
from app.application.use_cases.research.update_project import UpdateProjectUseCase
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(get_current_user), Depends(require_object_acl())])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class CreateAgencyRequest(BaseModel):
    name: str
    uploaded_by: str
    status: str = "draft"
    website: str | None = None
    scheme: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    notes: str | None = None


class UpdateAgencyRequest(CreateAgencyRequest):
    """Partial update contract (every field optional)."""

    name: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class CreateProjectRequest(BaseModel):
    title: str
    uploaded_by: str
    status: str = "draft"
    lifecycle_status: str = "draft"
    project_code: str | None = None
    department: str | None = None
    grant_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    budget_approved: float | None = None
    budget_utilized: float | None = None
    objectives: str | None = None
    keywords: list[str] | None = None
    abstract: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    links: dict | None = None  # {agencies|committees: [object ids]}
    team: dict | None = None  # {principal_investigators|co_investigators|team_members: [ids]}


class UpdateProjectRequest(CreateProjectRequest):
    """Partial update contract (every field optional)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None
    lifecycle_status: str | None = None


class CreateGrantRequest(BaseModel):
    title: str
    grant_number: str
    uploaded_by: str
    status: str = "draft"
    amount: float | None = None
    release_schedule: str | None = None
    notes: str | None = None
    links: dict | None = None  # {projects|funding_agencies: [object ids]}


class UpdateGrantRequest(CreateGrantRequest):
    """Partial update contract (every field optional)."""

    title: str | None = None
    grant_number: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class MilestoneRequest(BaseModel):
    title: str
    date: str
    status: str = "pending"
    notes: str | None = None
    uploaded_by: str = "system"


class UpdateMilestoneRequest(BaseModel):
    title: str | None = None
    date: str | None = None
    status: str | None = None
    notes: str | None = None
    uploaded_by: str = "system"


class ProgressUpdateRequest(BaseModel):
    date: str
    percent: float
    remark: str
    uploaded_by: str = "system"


class InstallmentRequest(BaseModel):
    installment_no: int
    date: str
    amount: float
    status: str = "released"
    notes: str | None = None
    uploaded_by: str = "system"


class ExpenditureRequest(BaseModel):
    date: str
    head: str
    amount: float
    reference: str | None = None
    notes: str | None = None
    uploaded_by: str = "system"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class AgencyResponseModel(BaseModel):
    id: str
    name: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    website: str | None = None
    scheme: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    notes: str | None = None
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListAgenciesResponseModel(BaseModel):
    items: list[AgencyResponseModel] = []
    total_count: int
    page: int
    page_size: int


class MilestoneResponseModel(BaseModel):
    id: str
    title: str
    date: str | None = None
    status: str = "pending"
    notes: str | None = None


class ProjectResponseModel(BaseModel):
    id: str
    title: str
    status: str
    lifecycle_status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    project_code: str | None = None
    department: str | None = None
    grant_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    budget_approved: float | None = None
    budget_utilized: float | None = None
    objectives: str | None = None
    keywords: list[str] = []
    abstract: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = []
    progress_updates: list[dict] = []
    links: dict[str, list[dict]] = {}
    team: dict[str, list[dict]] = {}
    milestones: list[MilestoneResponseModel] = []
    budget: dict | None = None
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListProjectsResponseModel(BaseModel):
    items: list[ProjectResponseModel] = []
    total_count: int
    page: int
    page_size: int


class InstallmentResponseModel(BaseModel):
    id: str
    installment_no: int | None = None
    date: str | None = None
    amount: float | None = None
    status: str = "released"
    notes: str | None = None


class ExpenditureResponseModel(BaseModel):
    id: str
    date: str | None = None
    head: str | None = None
    amount: float | None = None
    reference: str | None = None
    notes: str | None = None


class GrantResponseModel(BaseModel):
    id: str
    title: str
    grant_number: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    amount: float | None = None
    release_schedule: str | None = None
    notes: str | None = None
    links: dict[str, list[dict]] = {}
    installments: list[InstallmentResponseModel] = []
    expenditures: list[ExpenditureResponseModel] = []
    budget: dict | None = None
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListGrantsResponseModel(BaseModel):
    items: list[GrantResponseModel] = []
    total_count: int
    page: int
    page_size: int


class UpcomingDeadlineModel(BaseModel):
    milestone_id: str
    title: str
    date: str | None = None
    status: str = "pending"
    project_id: str
    project_title: str


class ResearchDashboardModel(BaseModel):
    total_projects: int
    active_projects: int
    completed_projects: int
    total_grants: int
    budget_approved: float
    budget_utilized: float
    upcoming_deadlines: list[UpcomingDeadlineModel] = []


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ---------------------------------------------------------------------------
# Dashboard (static route first)
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=ResearchDashboardModel)
def research_dashboard(
    upcoming_limit: int = Query(10, ge=1, le=50),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ResearchDashboardModel:
    try:
        out = GetResearchDashboardUseCase(repo).execute(
            GetResearchDashboardQuery(upcoming_limit=upcoming_limit)
        )
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ResearchDashboardModel(**dashboard_response(out))


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------
@router.get("/agencies", response_model=ListAgenciesResponseModel)
def list_agencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    q: str | None = None,
    agency_status: str | None = Query(None, alias="status"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListAgenciesResponseModel:
    try:
        result = ListAgenciesUseCase(repo).execute(
            ListAgenciesQuery(page=page, page_size=page_size, q=q or None,
                              status=agency_status or None)
        )
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ListAgenciesResponseModel(
        items=[AgencyResponseModel(**agency_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/agencies", response_model=AgencyResponseModel, status_code=status.HTTP_201_CREATED)
def create_agency(
    req: CreateAgencyRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> AgencyResponseModel:
    try:
        out = CreateAgencyUseCase(repo).execute(
            CreateAgencyCommand(input=to_create_agency_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return AgencyResponseModel(**agency_response(out))


@router.get("/agencies/{agency_id}", response_model=AgencyResponseModel)
def get_agency(
    agency_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> AgencyResponseModel:
    try:
        out = GetAgencyUseCase(repo).execute(GetAgencyQuery(object_id=ObjectId.parse(agency_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return AgencyResponseModel(**agency_response(out))


@router.put("/agencies/{agency_id}", response_model=AgencyResponseModel)
@router.patch("/agencies/{agency_id}", response_model=AgencyResponseModel)
def update_agency(
    agency_id: str,
    req: UpdateAgencyRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> AgencyResponseModel:
    try:
        out = UpdateAgencyUseCase(repo).execute(
            UpdateAgencyCommand(
                object_id=ObjectId.parse(agency_id),
                input=to_update_agency_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _unprocessable(exc)
    return AgencyResponseModel(**agency_response(out))


@router.delete("/agencies/{agency_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_agency(
    agency_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteAgencyUseCase(repo).execute(DeleteAgencyCommand(object_id=ObjectId.parse(agency_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@router.get("/projects", response_model=ListProjectsResponseModel)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="title/code/objectives/abstract/keywords"),
    pi: str | None = Query(None, description="PI / team member name filter"),
    agency: str | None = Query(None, description="linked funding agency name filter"),
    lifecycle_status: str | None = Query(None, alias="status"),
    year: int | None = Query(None, ge=1900, le=2200),
    department: str | None = None,
    object_id: str | None = Query(
        None, description="restrict to projects linked to this Object id"
    ),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListProjectsResponseModel:
    try:
        result = ListProjectsUseCase(repo).execute(
            ListProjectsQuery(
                page=page,
                page_size=page_size,
                q=q or None,
                pi=pi or None,
                agency=agency or None,
                status=lifecycle_status or None,
                year=year,
                department=department or None,
                object_id=ObjectId.parse(object_id) if object_id else None,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ListProjectsResponseModel(
        items=[ProjectResponseModel(**project_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/projects", response_model=ProjectResponseModel, status_code=status.HTTP_201_CREATED)
def create_project(
    req: CreateProjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ProjectResponseModel:
    try:
        out = CreateProjectUseCase(repo).execute(
            CreateProjectCommand(input=to_create_project_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ProjectResponseModel(**project_response(out))


@router.get("/projects/{project_id}", response_model=ProjectResponseModel)
def get_project(
    project_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ProjectResponseModel:
    try:
        out = GetProjectUseCase(repo).execute(GetProjectQuery(object_id=ObjectId.parse(project_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return ProjectResponseModel(**project_response(out))


@router.put("/projects/{project_id}", response_model=ProjectResponseModel)
@router.patch("/projects/{project_id}", response_model=ProjectResponseModel)
def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ProjectResponseModel:
    try:
        out = UpdateProjectUseCase(repo).execute(
            UpdateProjectCommand(
                object_id=ObjectId.parse(project_id),
                input=to_update_project_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _unprocessable(exc)
    return ProjectResponseModel(**project_response(out))


@router.delete(
    "/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_project(
    project_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteProjectUseCase(repo).execute(
            DeleteProjectCommand(object_id=ObjectId.parse(project_id))
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


# ---------------------------------------------------------------------------
# Project timeline (milestones + progress updates)
# ---------------------------------------------------------------------------
@router.post(
    "/projects/{project_id}/milestones",
    response_model=MilestoneResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def add_milestone(
    project_id: str,
    req: MilestoneRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> MilestoneResponseModel:
    try:
        out = AddMilestoneUseCase(repo).execute(
            AddMilestoneCommand(
                project_id=ObjectId.parse(project_id),
                input=to_milestone_input(body={**req.model_dump(), "uploaded_by": str(user.id)}),
                actor=str(user.id),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return MilestoneResponseModel(**milestone_response(out))


@router.post("/projects/{project_id}/updates", response_model=ProjectResponseModel)
def record_progress_update(
    project_id: str,
    req: ProgressUpdateRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ProjectResponseModel:
    try:
        out = RecordProgressUpdateUseCase(repo).execute(
            RecordProgressUpdateCommand(
                project_id=ObjectId.parse(project_id),
                input=to_progress_update_input(body={**req.model_dump(), "updated_by": str(user.id)}),
                actor=str(user.id),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ProjectResponseModel(**project_response(out))


@router.put("/milestones/{milestone_id}", response_model=MilestoneResponseModel)
@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponseModel)
def update_milestone(
    milestone_id: str,
    req: UpdateMilestoneRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> MilestoneResponseModel:
    try:
        out = UpdateMilestoneUseCase(repo).execute(
            UpdateMilestoneCommand(
                milestone_id=ObjectId.parse(milestone_id),
                input=to_update_milestone_input(
                    body=req.model_dump(exclude_unset=True), actor=str(user.id)
                ),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return MilestoneResponseModel(**milestone_response(out))


@router.delete(
    "/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_milestone(
    milestone_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteMilestoneUseCase(repo).execute(
            DeleteMilestoneCommand(milestone_id=ObjectId.parse(milestone_id))
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------
@router.get("/grants", response_model=ListGrantsResponseModel)
def list_grants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="grant number/title/schedule"),
    project_id: str | None = Query(None, description="grants funding this project"),
    agency_id: str | None = Query(None, description="grants of this agency"),
    grant_status: str | None = Query(None, alias="status"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListGrantsResponseModel:
    try:
        result = ListGrantsUseCase(repo).execute(
            ListGrantsQuery(
                page=page,
                page_size=page_size,
                q=q or None,
                project_id=ObjectId.parse(project_id) if project_id else None,
                agency_id=ObjectId.parse(agency_id) if agency_id else None,
                status=grant_status or None,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ListGrantsResponseModel(
        items=[GrantResponseModel(**grant_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/grants", response_model=GrantResponseModel, status_code=status.HTTP_201_CREATED)
def create_grant(
    req: CreateGrantRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> GrantResponseModel:
    try:
        out = CreateGrantUseCase(repo).execute(
            CreateGrantCommand(input=to_create_grant_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return GrantResponseModel(**grant_response(out))


@router.get("/grants/{grant_id}", response_model=GrantResponseModel)
def get_grant(
    grant_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> GrantResponseModel:
    try:
        out = GetGrantUseCase(repo).execute(GetGrantQuery(object_id=ObjectId.parse(grant_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return GrantResponseModel(**grant_response(out))


@router.put("/grants/{grant_id}", response_model=GrantResponseModel)
@router.patch("/grants/{grant_id}", response_model=GrantResponseModel)
def update_grant(
    grant_id: str,
    req: UpdateGrantRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> GrantResponseModel:
    try:
        out = UpdateGrantUseCase(repo).execute(
            UpdateGrantCommand(
                object_id=ObjectId.parse(grant_id),
                input=to_update_grant_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _unprocessable(exc)
    return GrantResponseModel(**grant_response(out))


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_grant(
    grant_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteGrantUseCase(repo).execute(DeleteGrantCommand(object_id=ObjectId.parse(grant_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


@router.post(
    "/grants/{grant_id}/installments",
    response_model=InstallmentResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def add_installment(
    grant_id: str,
    req: InstallmentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> InstallmentResponseModel:
    try:
        out = AddInstallmentUseCase(repo).execute(
            AddInstallmentCommand(
                grant_id=ObjectId.parse(grant_id),
                input=to_installment_input(body={**req.model_dump(), "uploaded_by": str(user.id)}),
                actor=str(user.id),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return InstallmentResponseModel(**installment_response(out))


@router.post(
    "/grants/{grant_id}/expenditures",
    response_model=ExpenditureResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def record_expenditure(
    grant_id: str,
    req: ExpenditureRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ExpenditureResponseModel:
    try:
        out = RecordExpenditureUseCase(repo).execute(
            RecordExpenditureCommand(
                grant_id=ObjectId.parse(grant_id),
                input=to_expenditure_input(body={**req.model_dump(), "uploaded_by": str(user.id)}),
                actor=str(user.id),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return ExpenditureResponseModel(**expenditure_response(out))


@router.delete(
    "/installments/{installment_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_installment(
    installment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteInstallmentUseCase(repo).execute(
            DeleteInstallmentCommand(installment_id=ObjectId.parse(installment_id))
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


@router.delete(
    "/expenditures/{expenditure_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_expenditure(
    expenditure_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteExpenditureUseCase(repo).execute(
            DeleteExpenditureCommand(expenditure_id=ObjectId.parse(expenditure_id))
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return None


@router.get("/export")
def export_projects(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> Response:
    """Export research projects as CSV."""
    import csv
    import io

    from app.domain.value_objects.enums import ObjectType

    projects = repo.list_by_type(ObjectType.PROJECT)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "status", "start_date", "end_date", "budget", "created_at"])
    for p in projects:
        writer.writerow([
            p.title or "",
            p.metadata.get_value("status") or "",
            p.metadata.get_value("start_date") or "",
            p.metadata.get_value("end_date") or "",
            p.metadata.get_value("budget_approved") or "",
            str(p.created_at) if p.created_at else "",
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="research_projects.csv"'},
    )
