"""Objects API routes — Phase 1 vertical slice (full CRUD).

Implements the five Object endpoints, all backed by the frozen Application layer:
  - GET    /objects          -> ListObjectsUseCase  (paginated)
  - GET    /objects/{id}     -> GetObjectUseCase
  - POST   /objects          -> CreateObjectUseCase
  - PUT    /objects/{id}     -> UpdateObjectUseCase
  - DELETE /objects/{id}     -> DeleteObjectUseCase

The API depends only on the Application layer (use cases + ports) and on a
repository injected through the session. No domain logic, no new abstractions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_object_access
from app.api.mappers.object_mapper import to_create_input, to_response, to_update_input
from app.application.commands.create_object import CreateObjectCommand
from app.application.commands.delete_object import DeleteObjectCommand
from app.application.commands.update_object import UpdateObjectCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_object import GetObjectQuery
from app.application.queries.list_objects import ListObjectsQuery
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.create_object import CreateObjectUseCase
from app.application.use_cases.delete_object import DeleteObjectUseCase
from app.application.use_cases.get_object import GetObjectUseCase
from app.application.use_cases.list_object import ListObjectsUseCase
from app.application.use_cases.object_acl import (
    get_object_acl as get_object_acl_uc,
)
from app.application.use_cases.object_acl import (
    update_object_acl as update_object_acl_uc,
)
from app.application.use_cases.update_object import UpdateObjectUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import PermissionAction, RelationshipKind
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/objects", tags=["objects"], dependencies=[Depends(get_current_user)])


class MetadataField(BaseModel):
    key: str
    value: str
    layer: int = 6
    source: str = "asserted"
    confidence: float | None = None


class CreateObjectRequest(BaseModel):
    object_type: str
    title: str
    created_by: str
    object_id: str | None = None
    status: str = "draft"
    metadata: list[MetadataField] | None = None


class UpdateObjectRequest(BaseModel):
    updated_by: str = "system"
    status: str | None = None
    metadata: list[MetadataField] | None = None


class ObjectResponse(BaseModel):
    id: str
    object_type: str
    title: str
    status: str
    version: int
    created_by: str
    created_at: str
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListObjectsResponse(BaseModel):
    items: list[ObjectResponse] = []
    total_count: int
    page: int
    page_size: int


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


@router.get("", response_model=ListObjectsResponse)
def list_objects(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListObjectsResponse:
    try:
        result = ListObjectsUseCase(repo).execute(
            ListObjectsQuery(page=page, page_size=page_size)
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListObjectsResponse(
        items=[ObjectResponse(**to_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{object_id}", response_model=ObjectResponse)
def get_object(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.READ)),
) -> ObjectResponse:
    try:
        out = GetObjectUseCase(repo).execute(
            GetObjectQuery(object_id=ObjectId.parse(object_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ObjectResponse(**to_response(out))


@router.post("", response_model=ObjectResponse, status_code=status.HTTP_201_CREATED)
def create_object(
    req: CreateObjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ObjectResponse:
    try:
        command = CreateObjectCommand(
            input=to_create_input(
                object_type=req.object_type,
                title=req.title,
                created_by=str(user.id),
                object_id=req.object_id,
                status=req.status,
                metadata=[m.model_dump() for m in (req.metadata or [])],
            )
        )
        out = CreateObjectUseCase(repo).execute(command)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ObjectResponse(**to_response(out))


@router.put("/{object_id}", response_model=ObjectResponse)
def update_object(
    object_id: str,
    req: UpdateObjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.WRITE)),
) -> ObjectResponse:
    try:
        command = UpdateObjectCommand(
            object_id=ObjectId.parse(object_id),
            input=to_update_input(
                object_id=object_id,
                updated_by=str(user.id),
                status=req.status,
                metadata=[m.model_dump() for m in (req.metadata or [])],
            ),
        )
        out = UpdateObjectUseCase(repo).execute(command)
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return ObjectResponse(**to_response(out))


@router.delete(
    "/{object_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_object(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.MANAGE)),
) -> None:
    try:
        DeleteObjectUseCase(repo).execute(
            DeleteObjectCommand(object_id=ObjectId.parse(object_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        # Graph integrity: deleting an object others reference is refused.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return None


class ObjectAclRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readers: list[str] = []
    writers: list[str] = []
    managers: list[str] = []


@router.get("/{object_id}/acl")
def get_object_acl_route(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.READ)),
) -> dict:
    try:
        return get_object_acl_uc(repo, object_id)
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{object_id}/acl")
def put_object_acl_route(
    object_id: str,
    body: ObjectAclRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.MANAGE)),
) -> dict:
    try:
        return update_object_acl_uc(repo, object_id, body.model_dump())
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{object_id}/graph")
def object_graph(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.READ)),
    direction: str = Query("outgoing", pattern="^(outgoing|incoming)$"),
    kind: str | None = Query(None),
    depth: int = Query(1, ge=1, le=5),
    mode: str = Query("bfs", pattern="^(bfs|dfs)$"),
) -> dict:
    try:
        kind_enum = RelationshipKind(kind) if kind else None
        result = GraphRuntimeService(repo, ObjectPermissionEvaluator()).traverse(
            ObjectId(object_id),
            direction=direction,
            kind=kind_enum,
            depth=depth,
            mode=mode,
            principal={"sub": str(user.id), "roles": get_roles(user)},
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return result


@router.get("/{object_id}/graph/path")
def object_graph_path(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.READ)),
    target: str = Query(...),
    direction: str = Query("outgoing", pattern="^(outgoing|incoming)$"),
    kind: str | None = Query(None),
    max_hops: int = Query(5, ge=1, le=5),
) -> dict:
    try:
        kind_enum = RelationshipKind(kind) if kind else None
        return GraphRuntimeService(repo, ObjectPermissionEvaluator()).find_shortest_path(
            ObjectId(object_id),
            ObjectId(target),
            direction=direction,
            kind=kind_enum,
            max_hops=max_hops,
            principal={"sub": str(user.id), "roles": get_roles(user)},
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# M28 — SMART_LINK relationship proposals (AI proposes, human approves)
# ---------------------------------------------------------------------------

class LinkProposalModel(BaseModel):
    """One AI-proposed relationship awaiting (or after) human review."""

    target_id: str
    target_type: str
    target_title: str
    kind: str
    confidence: float
    evidence: list[str] = []
    status: str = "pending"
    reviewed_by: str = ""
    reviewed_at: str | None = None


class ProposeLinksResponseModel(BaseModel):
    items: list[LinkProposalModel] = []
    created: int = 0


class LinkProposalsResponseModel(BaseModel):
    items: list[LinkProposalModel] = []


class LinkDecisionModel(BaseModel):
    target_id: str
    target_type: str
    target_title: str
    kind: str
    status: str


def _link_proposal_model(proposal) -> LinkProposalModel:
    return LinkProposalModel(
        target_id=proposal.target_id,
        target_type=proposal.target_type,
        target_title=proposal.target_title,
        kind=proposal.kind,
        confidence=proposal.confidence,
        evidence=list(proposal.evidence),
        status=proposal.status,
        reviewed_by=proposal.reviewed_by,
        reviewed_at=proposal.reviewed_at,
    )


@router.post(
    "/{object_id}/links/propose",
    response_model=ProposeLinksResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def propose_links(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.WRITE)),
) -> ProposeLinksResponseModel:
    """AI proposes candidate relationships (SMART_LINK, inferred provenance,
    confidence + evidence). Human review approves or rejects them."""
    from app.application.use_cases.ai.propose_links import ProposeLinksUseCase

    try:
        result = ProposeLinksUseCase(
            repo, ObjectPermissionEvaluator()
        ).propose(
            ObjectId.parse(object_id),
            actor=str(user.id),
            principal={"sub": str(user.id), "roles": get_roles(user)},
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ProposeLinksResponseModel(
        items=[_link_proposal_model(p) for p in result.items],
        created=result.created,
    )


@router.get("/{object_id}/links/proposals", response_model=LinkProposalsResponseModel)
def list_link_proposals(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.READ)),
) -> LinkProposalsResponseModel:
    """List the SMART_LINK proposals of one object (READ on the source)."""
    from app.application.use_cases.ai.propose_links import ProposeLinksUseCase

    try:
        result = ProposeLinksUseCase(
            repo, ObjectPermissionEvaluator()
        ).list_proposals(ObjectId.parse(object_id))
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return LinkProposalsResponseModel(
        items=[_link_proposal_model(p) for p in result.items]
    )


@router.post("/{object_id}/links/{target_id}/approve", response_model=LinkDecisionModel)
def approve_link_proposal(
    object_id: str,
    target_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.WRITE)),
) -> LinkDecisionModel:
    """Human approval: promote the SMART_LINK edge to its proposed kind with
    asserted provenance. Requires WRITE on the source (dependency) and on the
    target (use case)."""
    from app.application.exceptions import PermissionDeniedError
    from app.application.use_cases.ai.propose_links import ProposeLinksUseCase

    try:
        decision = ProposeLinksUseCase(
            repo, ObjectPermissionEvaluator()
        ).approve(
            ObjectId.parse(object_id),
            ObjectId.parse(target_id),
            actor=str(user.id),
            principal={"sub": str(user.id), "roles": get_roles(user)},
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return LinkDecisionModel(
        target_id=decision.target_id,
        target_type=decision.target_type,
        target_title=decision.target_title,
        kind=decision.kind,
        status=decision.status,
    )


@router.post("/{object_id}/links/{target_id}/reject", response_model=LinkDecisionModel)
def reject_link_proposal(
    object_id: str,
    target_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
    _acl: UniversalObject | None = Depends(require_object_access(PermissionAction.WRITE)),
) -> LinkDecisionModel:
    """Human rejection: remove the SMART_LINK edge and record the decision."""
    from app.application.exceptions import PermissionDeniedError
    from app.application.use_cases.ai.propose_links import ProposeLinksUseCase

    try:
        decision = ProposeLinksUseCase(
            repo, ObjectPermissionEvaluator()
        ).reject(
            ObjectId.parse(object_id),
            ObjectId.parse(target_id),
            actor=str(user.id),
            principal={"sub": str(user.id), "roles": get_roles(user)},
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return LinkDecisionModel(
        target_id=decision.target_id,
        target_type=decision.target_type,
        target_title=decision.target_title,
        kind=decision.kind,
        status=decision.status,
    )
