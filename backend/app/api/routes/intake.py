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
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.intake_mapper import (
    IntakeProgressResponseModel,
    IntakeSessionCreateRequest,
    IntakeSessionResponseModel,
    ListIntakeItemsResponseModel,
    ListIntakeSessionsResponseModel,
    item_response,
    progress_response,
    session_response,
    to_create_input,
)

# Deliberate reuse (do not duplicate the storage composition point):
from app.api.routes.documents import get_storage
from app.application.commands.control_intake_session import ControlIntakeSessionCommand
from app.application.commands.create_intake_session import CreateIntakeSessionCommand
from app.application.commands.delete_intake_session import DeleteIntakeSessionCommand
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.intake.jobs import IntakeJobManager
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
from app.core.config import settings
from app.infrastructure.db.session import SessionLocal, get_db
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/intake", tags=["Intake"], dependencies=[Depends(get_current_user)])


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
) -> IntakeSessionResponseModel:
    use_case = CreateIntakeSessionUseCase(repo, _storage_root_of(storage))
    try:
        out = use_case.execute(CreateIntakeSessionCommand(input=to_create_input(payload)))
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
