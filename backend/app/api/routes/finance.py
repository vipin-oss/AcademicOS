"""Finance & Procurement API routes (procurement governance slice).

Mirrors ``committees.py``/``research.py`` one-to-one, backed by the frozen
Application layer:
  - GET    /finance/dashboard            -> PART 11 cards
  - GET    /finance/proposals            -> ListProposalsUseCase (PART 12 search/filters)
  - POST   /finance/proposals            -> CreateProposalUseCase (409 duplicates)
  - GET    /finance/proposals/{id}       -> GetProposalUseCase (enriched workspace)
  - PUT    /finance/proposals/{id}       -> UpdateProposalUseCase (merge contract)
  - PATCH  /finance/proposals/{id}       -> UpdateProposalUseCase (same handler)
  - DELETE /finance/proposals/{id}       -> DeleteProposalUseCase
  - GET    /finance/vendors              -> ListVendorsUseCase (PART 3 registry)
  - POST   /finance/vendors              -> CreateVendorUseCase (409 GST/name)
  - GET    /finance/vendors/{id}         -> GetVendorUseCase (+ computed stats)
  - PUT    /finance/vendors/{id}         -> UpdateVendorUseCase (merge contract)
  - DELETE /finance/vendors/{id}         -> DeleteVendorUseCase
  - GET    /finance/budgets              -> ListBudgetLinesUseCase (PART 9 lens)
  - GET    /finance/assets               -> ListAssetRegisterUseCase (PART 8 register)

Static branches (dashboard/vendors/budgets/assets) are declared BEFORE the
parameterised ones inside each family so they are never captured as an id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.finance_mapper import (
    proposal_response,
    to_create_proposal_input,
    to_create_vendor_input,
    to_update_proposal_input,
    to_update_vendor_input,
    vendor_response,
)
from app.application.commands.create_proposal import CreateProposalCommand
from app.application.commands.create_vendor import CreateVendorCommand
from app.application.commands.delete_proposal import DeleteProposalCommand
from app.application.commands.delete_vendor import DeleteVendorCommand
from app.application.commands.update_proposal import UpdateProposalCommand
from app.application.commands.update_vendor import UpdateVendorCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_finance_dashboard import GetFinanceDashboardQuery
from app.application.queries.get_proposal import GetProposalQuery
from app.application.queries.get_vendor import GetVendorQuery
from app.application.queries.list_asset_register import ListAssetRegisterQuery
from app.application.queries.list_budget_lines import ListBudgetLinesQuery
from app.application.queries.list_proposals import ListProposalsQuery
from app.application.queries.list_vendors import ListVendorsQuery
from app.application.use_cases.finance.create_proposal import CreateProposalUseCase
from app.application.use_cases.finance.create_vendor import CreateVendorUseCase
from app.application.use_cases.finance.delete_proposal import DeleteProposalUseCase
from app.application.use_cases.finance.delete_vendor import DeleteVendorUseCase
from app.application.use_cases.finance.get_finance_dashboard import (
    GetFinanceDashboardUseCase,
)
from app.application.use_cases.finance.get_proposal import GetProposalUseCase
from app.application.use_cases.finance.get_vendor import GetVendorUseCase
from app.application.use_cases.finance.list_asset_register import ListAssetRegisterUseCase
from app.application.use_cases.finance.list_budget_lines import ListBudgetLinesUseCase
from app.application.use_cases.finance.list_proposals import ListProposalsUseCase
from app.application.use_cases.finance.list_vendors import ListVendorsUseCase
from app.application.use_cases.finance.update_proposal import UpdateProposalUseCase
from app.application.use_cases.finance.update_vendor import UpdateVendorUseCase
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/finance", tags=["finance"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Request / response models (extra keys forbidden — frozen convention)
# ---------------------------------------------------------------------------
class CreateVendorRequest(BaseModel):
    """JSON body for POST /finance/vendors."""

    name: str
    uploaded_by: str
    status: str = "active"
    gst_number: str | None = None
    pan: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_details: dict | None = None
    notes: str | None = None
    tags: list[str] | None = None


class UpdateVendorRequest(CreateVendorRequest):
    """JSON body for PUT (partial semantics; every field optional)."""

    name: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class CreateProposalRequest(BaseModel):
    """JSON body for POST /finance/proposals."""

    title: str
    uploaded_by: str
    status: str = "draft"
    proposal_number: str | None = None
    department: str | None = None
    requested_by: str | None = None
    proposal_date: str | None = None
    purpose: str | None = None
    budget_head: str | None = None
    estimated_cost: float | str | None = None
    proposal_status: str = "draft"
    priority: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    approval_meeting_id: str | None = None
    minutes: str | None = None
    recommendations: str | None = None
    quotations: list[dict] | None = None
    comparative: list[dict] | None = None
    purchase_orders: list[dict] | None = None
    bills: list[dict] | None = None
    assets: list[dict] | None = None
    links: dict | None = None


class UpdateProposalRequest(CreateProposalRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None
    proposal_status: str | None = None


class VendorResponseModel(BaseModel):
    id: str
    name: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    gst_number: str | None
    pan: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    address: str | None
    bank_details: dict
    notes: str | None
    tags: list[str]
    stats: dict
    metadata: dict
    events: list[str]


class ListVendorsResponseModel(BaseModel):
    items: list[VendorResponseModel]
    total_count: int
    page: int
    page_size: int


class MeetingRefModel(BaseModel):
    id: str
    title: str
    meeting_number: str | None
    meeting_date: str | None
    mode: str | None
    venue: str | None


class ProposalResponseModel(BaseModel):
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None
    proposal_number: str | None
    department: str | None
    requested_by: str | None
    requested_name: str | None
    proposal_date: str | None
    purpose: str | None
    budget_head: str | None
    estimated_cost: float | None
    proposal_status: str
    priority: str | None
    notes: str | None
    tags: list[str]
    approval_meeting_id: str | None
    approval_meeting: MeetingRefModel | None
    minutes: str | None
    recommendations: str | None
    quotations: list[dict]
    comparative: list[dict]
    purchase_orders: list[dict]
    bills: list[dict]
    assets: list[dict]
    links: dict
    stats: dict
    metadata: dict
    events: list[str]


class ListProposalsResponseModel(BaseModel):
    items: list[ProposalResponseModel]
    total_count: int
    page: int
    page_size: int


class FinanceDashboardModel(BaseModel):
    active_procurements: int
    pending_approvals: int
    total_vendors: int
    total_purchase_orders: int
    budget_utilized: float
    budget_remaining: float | None
    pending_bills: int


class BudgetLineModel(BaseModel):
    project_id: str
    title: str
    approved: float | None
    released: float
    utilized: float
    remaining: float | None
    proposals: int
    spent: float


class ListBudgetsResponseModel(BaseModel):
    items: list[BudgetLineModel]


class AssetRegisterRowModel(BaseModel):
    proposal_id: str
    proposal_number: str | None
    proposal_title: str
    row: dict


class ListAssetsResponseModel(BaseModel):
    items: list[AssetRegisterRowModel]
    total_count: int
    page: int
    page_size: int


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
# Dashboard + budgets + assets (declared before /vendors & /proposals ids are
# distinct families, so ordering is illustrative — kept for parity)
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=FinanceDashboardModel)
def finance_dashboard(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return GetFinanceDashboardUseCase(repo).execute(GetFinanceDashboardQuery())


@router.get("/budgets", response_model=ListBudgetsResponseModel)
def list_budget_lines(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    result = ListBudgetLinesUseCase(repo).execute(ListBudgetLinesQuery())
    return ListBudgetsResponseModel(
        items=[BudgetLineModel(**vars(line)) for line in result.items]
    )


@router.get("/assets", response_model=ListAssetsResponseModel)
def list_asset_register(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    q: str | None = Query(None),
    category: str | None = Query(None),
    status_: str | None = Query(None, alias="status"),
):
    query = ListAssetRegisterQuery(
        page=page, page_size=page_size, q=q, category=category, status=status_
    )
    try:
        result = ListAssetRegisterUseCase(repo).execute(query)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return ListAssetsResponseModel(
        items=[AssetRegisterRowModel(**vars(item)) for item in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


# ---------------------------------------------------------------------------
# Vendor registry
# ---------------------------------------------------------------------------
@router.get("/vendors", response_model=ListVendorsResponseModel)
def list_vendors(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
):
    query = ListVendorsQuery(page=page, page_size=page_size, q=q)
    try:
        result = ListVendorsUseCase(repo).execute(query)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return ListVendorsResponseModel(
        items=[VendorResponseModel(**vendor_response(item)) for item in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("/vendors", response_model=VendorResponseModel, status_code=status.HTTP_201_CREATED)
def create_vendor(
    request: CreateVendorRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = CreateVendorUseCase(repo).execute(
            CreateVendorCommand(input=to_create_vendor_input(body=request.model_dump()))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return VendorResponseModel(**vendor_response(out))


@router.get("/vendors/{vendor_id}", response_model=VendorResponseModel)
def get_vendor(vendor_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = GetVendorUseCase(repo).execute(GetVendorQuery(object_id=vendor_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return VendorResponseModel(**vendor_response(out))


@router.put("/vendors/{vendor_id}", response_model=VendorResponseModel)
def update_vendor(
    vendor_id: str,
    request: UpdateVendorRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateVendorUseCase(repo).execute(
            UpdateVendorCommand(
                object_id=vendor_id, input=to_update_vendor_input(body=request.model_dump(exclude_unset=True))
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return VendorResponseModel(**vendor_response(out))


@router.delete("/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(vendor_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        DeleteVendorUseCase(repo).execute(DeleteVendorCommand(object_id=vendor_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Purchase proposals directory
# ---------------------------------------------------------------------------
@router.get("/proposals", response_model=ListProposalsResponseModel)
def list_proposals(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    vendor: str | None = Query(None),
    project: str | None = Query(None),
    grant: str | None = Query(None),
    status_: str | None = Query(None, alias="status"),
    department: str | None = Query(None),
    financial_year: str | None = Query(None),
):
    query = ListProposalsQuery(
        page=page,
        page_size=page_size,
        q=q,
        vendor=vendor,
        project=project,
        grant=grant,
        status=status_,
        department=department,
        financial_year=financial_year,
    )
    try:
        result = ListProposalsUseCase(repo).execute(query)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return ListProposalsResponseModel(
        items=[ProposalResponseModel(**proposal_response(item)) for item in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post(
    "/proposals", response_model=ProposalResponseModel, status_code=status.HTTP_201_CREATED
)
def create_proposal(
    request: CreateProposalRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = CreateProposalUseCase(repo).execute(
            CreateProposalCommand(input=to_create_proposal_input(body=request.model_dump()))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return ProposalResponseModel(**proposal_response(out))


@router.get("/proposals/{proposal_id}", response_model=ProposalResponseModel)
def get_proposal(proposal_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = GetProposalUseCase(repo).execute(GetProposalQuery(object_id=proposal_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return ProposalResponseModel(**proposal_response(out))


@router.put("/proposals/{proposal_id}", response_model=ProposalResponseModel)
def update_proposal(
    proposal_id: str,
    request: UpdateProposalRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = UpdateProposalUseCase(repo).execute(
            UpdateProposalCommand(
                object_id=proposal_id,
                input=to_update_proposal_input(body=request.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc) from exc
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc) from exc
    return ProposalResponseModel(**proposal_response(out))


@router.patch("/proposals/{proposal_id}", response_model=ProposalResponseModel)
def patch_proposal(
    proposal_id: str,
    request: UpdateProposalRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    return update_proposal(proposal_id, request, repo)


@router.delete("/proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proposal(proposal_id: str, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        DeleteProposalUseCase(repo).execute(DeleteProposalCommand(object_id=proposal_id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
