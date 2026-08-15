"""Intake Foundations API routes (v2 — session dashboard slice).

Mirrors ``committees.py`` one-to-one, backed by the frozen Application layer:

  - POST   /intake/sessions              -> CreateIntakeSessionUseCase (201) + enqueue
  - GET    /intake/sessions              -> ListIntakeSessionsUseCase (newest first)
  - GET    /intake/sessions/{sid}        -> GetIntakeSessionUseCase
  - GET    /intake/sessions/{sid}/progress -> GetIntakeProgressUseCase (lean polling)
  - GET    /intake/sessions/{sid}/items  -> ListIntakeItemsUseCase (paginated)
  - POST   /intake/sessions/{sid}/pause  -> PauseIntakeSessionUseCase
  - POST   /intake/sessions/{sid}/resume -> ResumeIntakeSessionUseCase
  - POST   /intake/sessions/{sid}/cancel -> CancelIntakeSessionUseCase
  - DELETE /intake/sessions/{sid}        -> DeleteIntakeSessionUseCase (204)

Composition root notes:
- The storage dependency is *reused* from the documents routes verbatim
  (never duplicated) so a single ``dependency_overrides[get_storage]`` keeps
  working across both modules in tests.
- The job manager is a lazy app-state singleton: first intake request builds
  it against the real session factory + storage and reconciles any sessions
  a previous process left mid-drain.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_object_acl
from app.api.mappers.intake_mapper import (
    CommitItemResponseModel,
    IntakeProgressResponseModel,
    IntakeSessionCreateRequest,
    IntakeSessionResponseModel,
    ListIntakeItemsResponseModel,
    ListIntakeSessionsResponseModel,
    ProposalResponseModel,
    ProposalUpdateRequest,
    commit_item_response,
    item_response,
    progress_response,
    proposal_response,
    session_response,
    to_create_input,
)

# Deliberate reuse (do not duplicate the storage composition point):
from app.api.routes.documents import get_storage
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.commands.control_intake_session import ControlIntakeSessionCommand
from app.application.commands.create_intake_session import CreateIntakeSessionCommand
from app.application.commands.delete_intake_session import DeleteIntakeSessionCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.intake.commit_engine import CommitEngineService
from app.application.intake.jobs import IntakeJobManager
from app.application.intake.proposal_engine import (
    ProposalEngineService,
    ProposalReviewService,
)
from app.application.ports.embedder import Embedder
from app.application.queries.get_intake_extracted_text import GetIntakeExtractedTextQuery
from app.application.queries.get_intake_progress import GetIntakeProgressQuery
from app.application.queries.get_intake_session import GetIntakeSessionQuery
from app.application.queries.list_intake_items import ListIntakeItemsQuery
from app.application.queries.list_intake_sessions import ListIntakeSessionsQuery
from app.application.use_cases.intake.control_session import (
    CancelIntakeSessionUseCase,
    PauseIntakeSessionUseCase,
    ResumeIntakeSessionUseCase,
)
from app.application.use_cases.intake.create_session import CreateIntakeSessionUseCase
from app.application.use_cases.intake.delete_session import DeleteIntakeSessionUseCase
from app.application.use_cases.intake.get_extracted_text import GetIntakeExtractedTextUseCase
from app.application.use_cases.intake.get_progress import GetIntakeProgressUseCase
from app.application.use_cases.intake.get_session import GetIntakeSessionUseCase
from app.application.use_cases.intake.list_items import ListIntakeItemsUseCase
from app.application.use_cases.intake.list_sessions import ListIntakeSessionsUseCase
from app.application.use_cases.intake.retry_session import RetryIntakeSessionUseCase
from app.application.use_cases.intake.review_item import (
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    ReviewItemUseCase,
)
from app.core.config import settings
from app.domain.entities.object import UniversalObject
from app.domain.repositories.vector_repository import VectorRepository
from app.infrastructure.db.session import SessionLocal, get_db
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/intake", tags=["Intake"], dependencies=[Depends(get_current_user), Depends(require_object_acl())])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _storage_root_of(storage: LocalFileStorage) -> str:
    """The on-disk root the composed storage actually serves (so safety guards
    always evaluate against reality, not configuration)."""

    return str(getattr(storage, "_root", settings.storage_dir))


def _repository_factory() -> tuple[SQLAlchemyObjectRepository, object]:
    """Fresh repository + cleanup for one background drain."""

    db = SessionLocal()
    return SQLAlchemyObjectRepository(db), db.close


def get_job_manager(request: Request) -> IntakeJobManager:
    """Lazy app-state singleton (first intake request constructs it).

    Composition note (M2): the deterministic parser registry is built here,
    at the composition root, from infrastructure adapters — never inside the
    application layer.
    """

    manager = getattr(request.app.state, "intake_jobs", None)
    if manager is None:
        manager = IntakeJobManager(
            _repository_factory,
            LocalFileStorage(settings.storage_dir),
            build_document_parsers(),
            max_workers=settings.intake_max_workers,
        )
        manager.reconcile_interrupted()
        request.app.state.intake_jobs = manager
    return manager


def _not_found(exc: ObjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


@router.post(
    "/sessions",
    response_model=IntakeSessionResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def create_intake_session(
    payload: IntakeSessionCreateRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
) -> IntakeSessionResponseModel:
    use_case = CreateIntakeSessionUseCase(repo, _storage_root_of(storage))
    try:
        out = use_case.execute(CreateIntakeSessionCommand(input=to_create_input(payload.model_copy(update={"actor": str(user.id)}))))
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    jobs.enqueue(out.id)
    return session_response(out)


@router.get("/sessions", response_model=ListIntakeSessionsResponseModel)
def list_intake_sessions(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ListIntakeSessionsResponseModel:
    result = ListIntakeSessionsUseCase(repo).execute(
        ListIntakeSessionsQuery(page=page, page_size=page_size)
    )
    return ListIntakeSessionsResponseModel(
        items=[session_response(o) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


class DeadLetterEntryModel(BaseModel):
    kind: str
    id: str
    status: str
    session_id: str | None = None
    relative_path: str | None = None
    error: str = ""
    reason: str = ""
    attempts: int = 0
    retryable: bool = False
    resumable: bool = False


class DeadLetterResponseModel(BaseModel):
    sessions: list[DeadLetterEntryModel]
    items: list[DeadLetterEntryModel]
    total: int


@router.get("/dead-letter", response_model=DeadLetterResponseModel)
def intake_dead_letter(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    limit: int = Query(100, ge=1, le=500),
) -> DeadLetterResponseModel:
    """L10 DLQ view: failed sessions (resumable) and failed items (retryable).
    Surfaces the existing failed/reconcile state as a queryable, actionable
    dead-letter queue — no second persistence system (ADR-048)."""
    from app.application.use_cases.intake.dead_letter import ListDeadLetterUseCase

    view = ListDeadLetterUseCase(repo).execute(limit=limit)
    to_model = lambda e: DeadLetterEntryModel(  # noqa: E731
        kind=e.kind, id=e.id, status=e.status, session_id=e.session_id,
        relative_path=e.relative_path, error=e.error, reason=e.reason,
        attempts=e.attempts, retryable=e.retryable, resumable=e.resumable,
    )
    return DeadLetterResponseModel(
        sessions=[to_model(e) for e in view.sessions],
        items=[to_model(e) for e in view.items],
        total=view.total,
    )


@router.get("/sessions/{session_id}", response_model=IntakeSessionResponseModel)
def get_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> IntakeSessionResponseModel:
    try:
        out = GetIntakeSessionUseCase(repo).execute(
            GetIntakeSessionQuery(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return session_response(out)


@router.get("/sessions/{session_id}/progress", response_model=IntakeProgressResponseModel)
def get_intake_progress(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> IntakeProgressResponseModel:
    try:
        out = GetIntakeProgressUseCase(repo).execute(
            GetIntakeProgressQuery(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return progress_response(out)


@router.get("/sessions/{session_id}/items", response_model=ListIntakeItemsResponseModel)
def list_intake_items(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> ListIntakeItemsResponseModel:
    try:
        result = ListIntakeItemsUseCase(repo).execute(
            ListIntakeItemsQuery(session_id=session_id, page=page, page_size=page_size)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return ListIntakeItemsResponseModel(
        items=[item_response(o) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/sessions/{session_id}/items/{item_id}/extraction/text",
    response_class=PlainTextResponse,
)
def get_intake_extracted_text(
    session_id: str,
    item_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> PlainTextResponse:
    """M2: the raw extracted text of one item (404 until honestly available)."""

    try:
        text = GetIntakeExtractedTextUseCase(repo, storage).execute(
            GetIntakeExtractedTextQuery(session_id=session_id, item_id=item_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")


@router.post("/sessions/{session_id}/pause", response_model=IntakeSessionResponseModel)
def pause_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
) -> IntakeSessionResponseModel:
    try:
        out = PauseIntakeSessionUseCase(repo, jobs).execute(
            ControlIntakeSessionCommand(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return session_response(out)


@router.post("/sessions/{session_id}/retry", response_model=IntakeSessionResponseModel)
def retry_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
) -> IntakeSessionResponseModel:
    try:
        out = RetryIntakeSessionUseCase(repo, jobs).execute(
            ControlIntakeSessionCommand(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return session_response(out)


@router.post("/sessions/{session_id}/resume", response_model=IntakeSessionResponseModel)
def resume_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
) -> IntakeSessionResponseModel:
    try:
        out = ResumeIntakeSessionUseCase(repo, jobs).execute(
            ControlIntakeSessionCommand(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return session_response(out)


@router.post("/sessions/{session_id}/cancel", response_model=IntakeSessionResponseModel)
def cancel_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
) -> IntakeSessionResponseModel:
    try:
        out = CancelIntakeSessionUseCase(repo, jobs).execute(
            ControlIntakeSessionCommand(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return session_response(out)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intake_session(
    session_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    jobs: IntakeJobManager = Depends(get_job_manager),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        DeleteIntakeSessionUseCase(repo, storage, jobs).execute(
            DeleteIntakeSessionCommand(session_id=session_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/items/{item_id}/commit-preview", response_model=CommitItemResponseModel)
def commit_item_preview(
    item_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> CommitItemResponseModel:
    """Preview a commit: runs the same eligibility checks as the commit
    itself without creating or mutating anything. One source of truth —
    CommitEngineService.commit_item(dry_run=True)."""
    try:
        out = CommitEngineService(repo, storage).commit_item(
            item_id=item_id, actor="preview", dry_run=True
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectAlreadyExistsError as exc:
        # Previewing an already-committed item reports the same conflict as
        # the commit (409 with the existing document id).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return commit_item_response(out)


@router.post("/items/{item_id}/commit", response_model=CommitItemResponseModel)
def commit_item(
    item_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> CommitItemResponseModel:
    """Commit one processed intake item into a Document (idempotent).

    409 with the existing document id on a double submit; 422 for any
    ineligible item (same checks as the preview). After a successful
    commit the search index is drained immediately, so the new document
    is searchable right away (M9)."""
    try:
        out = CommitEngineService(
            repo, storage, content_store=SQLDocumentContentStore(db)
        ).commit_item(item_id=item_id, actor=str(user.id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _drain_search_index(db, vector_repository, embedder)
    return commit_item_response(out)


# ---------------------------------------------------------------------------
# M9 — review workflow (approve / reject / bulk)
# ---------------------------------------------------------------------------
class ReviewItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str


class ReviewItemResponseModel(BaseModel):
    item_id: str
    status: str
    document_id: str | None = None


class BulkReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    item_ids: list[str] | None = None


class BulkReviewItemModel(BaseModel):
    item_id: str
    status: str
    document_id: str | None = None
    error: str | None = None


class BulkReviewResponseModel(BaseModel):
    items: list[BulkReviewItemModel]
    succeeded: int


def _review_service(
    repo: SQLAlchemyObjectRepository,
    storage: LocalFileStorage,
    db: Session,
) -> ReviewItemUseCase:
    # M27: wire the document-content search projection at review/commit time.
    return ReviewItemUseCase(
        repo, storage, content_store=SQLDocumentContentStore(db)
    )


def _drain_search_index(
    db: Session,
    vector_repository: VectorRepository | None,
    embedder: Embedder,
) -> None:
    """Drain the durable outbox into the lexical + semantic search index —
    the M9 guarantee that committed documents are searchable immediately."""
    SearchIndexApplier(
        db, vector_repository=vector_repository, embedder=embedder
    ).apply_pending()


WIRE_DECISIONS = ("approve", "reject")


def _map_decision(decision: str) -> str:
    """Wire values (approve/reject) -> internal decision values."""
    return {
        "approve": REVIEW_APPROVED,
        "reject": REVIEW_REJECTED,
    }.get(decision, "")


@router.post("/items/{item_id}/review", response_model=ReviewItemResponseModel)
def review_item(
    item_id: str,
    body: ReviewItemRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> ReviewItemResponseModel:
    """Review one awaiting item: ``approve`` commits it (and the search
    index is drained immediately), ``reject`` marks it terminal-rejected.
    The review decision is persisted as item metadata."""
    decision = _map_decision(body.decision)
    if not decision:
        raise _unprocessable(
            ValidationError("decision must be one of: approve, reject.")
        )
    service = _review_service(repo, storage, db)
    try:
        if decision == REVIEW_APPROVED:
            out = service.approve(item_id, actor=str(user.id))
            _drain_search_index(db, vector_repository, embedder)
            return ReviewItemResponseModel(
                item_id=item_id,
                status="committed",
                document_id=out.document_id or None,
            )
        service.reject(item_id, actor=str(user.id))
        return ReviewItemResponseModel(item_id=item_id, status="rejected")
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except (ValidationError, ObjectAlreadyExistsError) as exc:
        raise _unprocessable(exc) from exc


@router.post("/sessions/{session_id}/review", response_model=BulkReviewResponseModel)
def bulk_review_items(
    session_id: str,
    body: BulkReviewRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
    db: Session = Depends(get_db),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> BulkReviewResponseModel:
    """Bulk review: apply one decision to every awaiting item of the
    session (or the explicit ``item_ids`` subset). Each item's outcome is
    reported; approvals commit and drain the search index."""
    decision = _map_decision(body.decision)
    if not decision:
        raise _unprocessable(
            ValidationError("decision must be one of: approve, reject.")
        )
    service = _review_service(repo, storage, db)
    try:
        result = service.bulk(
            session_id,
            decision,
            actor=str(user.id),
            item_ids=body.item_ids,
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    if decision == REVIEW_APPROVED and result.succeeded:
        _drain_search_index(db, vector_repository, embedder)
    return BulkReviewResponseModel(
        items=[
            BulkReviewItemModel(
                item_id=item.item_id,
                status=item.status,
                document_id=item.document_id,
                error=item.error,
            )
            for item in result.items
        ],
        succeeded=result.succeeded,
    )

@router.get("/items/{item_id}/proposal", response_model=ProposalResponseModel)
def get_item_proposal(
    item_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ProposalResponseModel:
    """The item's current proposal (422 when none generated yet)."""
    try:
        proposal = ProposalEngineService(repo).get(item_id)
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return proposal_response(item_id, proposal)


@router.put("/items/{item_id}/proposal", response_model=ProposalResponseModel)
def put_item_proposal(
    item_id: str,
    body: ProposalUpdateRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ProposalResponseModel:
    """Review (or create) the item's proposal. A generated proposal is
    required first (422); the reviewed title/type drive the eventual commit."""
    try:
        proposal = ProposalReviewService(repo).update(
            item_id,
            title=body.title,
            document_type=body.document_type,
            description=body.description,
            actor=str(user.id),
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return proposal_response(item_id, proposal)


@router.post("/items/{item_id}/proposal/regenerate", response_model=ProposalResponseModel)
def regenerate_item_proposal(
    item_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ProposalResponseModel:
    """Discard human edits and regenerate the proposal from the item's facts."""
    try:
        proposal = ProposalReviewService(repo).regenerate(item_id, actor=str(user.id))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return proposal_response(item_id, proposal)
