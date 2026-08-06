"""Students API routes — the student registry slice (full CRUD + CSV).

Mirrors ``publications.py`` one-to-one, backed by the frozen Application
layer (a Student is a Universal Object with ``object_type = student``):
  - GET    /students           -> ListStudentsUseCase (filters + object lens)
  - GET    /students/export    -> CSV download of the same filtered query
  - POST   /students/import    -> bulk roster CSV import with duplicate report
  - GET    /students/{id}      -> GetStudentUseCase
  - POST   /students           -> CreateStudentUseCase (409 on duplicate)
  - PUT    /students/{id}      -> UpdateStudentUseCase
  - PATCH  /students/{id}      -> UpdateStudentUseCase (same handler)
  - DELETE /students/{id}      -> DeleteStudentUseCase

Static routes are declared BEFORE ``/{student_id}`` so they are never
captured as an id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.api.mappers.student_mapper import (
    to_create_input,
    to_response,
    to_update_input,
)
from app.application.commands.create_student import CreateStudentCommand
from app.application.commands.delete_student import DeleteStudentCommand
from app.application.commands.update_student import UpdateStudentCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_student import GetStudentQuery
from app.application.queries.list_students import ListStudentsQuery
from app.application.services.teaching_csv import export_students_csv
from app.application.use_cases.students.create_student import CreateStudentUseCase
from app.application.use_cases.students.delete_student import DeleteStudentUseCase
from app.application.use_cases.students.get_student import GetStudentUseCase
from app.application.use_cases.students.import_students import (
    ImportStudentsCommand,
    ImportStudentsUseCase,
)
from app.application.use_cases.students.list_students import ListStudentsUseCase
from app.application.use_cases.students.update_student import UpdateStudentUseCase
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/students", tags=["students"], dependencies=[Depends(get_current_user)])


class CreateStudentRequest(BaseModel):
    """JSON body for POST (manual admission). Registry fields optional."""

    name: str
    student_type: str  # ug | pg | phd | alumni
    uploaded_by: str
    status: str = "draft"
    roll_number: str | None = None
    registration_number: str | None = None
    university_enrollment: str | None = None
    email: str | None = None
    phone: str | None = None
    programme: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    batch: str | None = None
    admission_date: str | None = None
    expected_graduation: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    google_scholar: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    links: dict | None = None


class UpdateStudentRequest(CreateStudentRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    name: str | None = None
    student_type: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class ImportStudentsRequest(BaseModel):
    text: str
    uploaded_by: str


class StudentResponseModel(BaseModel):
    id: str
    name: str
    student_type: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    roll_number: str | None = None
    registration_number: str | None = None
    university_enrollment: str | None = None
    email: str | None = None
    phone: str | None = None
    programme: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    batch: str | None = None
    admission_date: str | None = None
    expected_graduation: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    google_scholar: str | None = None
    notes: str | None = None
    tags: list[str] = []
    links: dict[str, list[dict]] = {}
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListStudentsResponseModel(BaseModel):
    items: list[StudentResponseModel] = []
    total_count: int
    page: int
    page_size: int


class ImportStudentsResultModel(BaseModel):
    created: list[str] = []
    skipped_duplicates: list[dict] = []
    errors: list[dict] = []


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _list_query(
    page: int,
    page_size: int,
    q: str | None,
    student_type: str | None,
    programme: str | None,
    semester: int | None,
    section: str | None,
    student_status: str | None,
    object_id: str | None,
) -> ListStudentsQuery:
    return ListStudentsQuery(
        page=page,
        page_size=page_size,
        q=q or None,
        student_type=student_type or None,
        programme=programme or None,
        semester=semester,
        section=section or None,
        status=student_status or None,
        object_id=ObjectId.parse(object_id) if object_id else None,
    )


@router.get("", response_model=ListStudentsResponseModel)
def list_students(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    q: str | None = Query(
        None, description="name/roll/registration/enrollment/email/programme/batch"
    ),
    student_type: str | None = Query(None, description="ug | pg | phd | alumni"),
    programme: str | None = Query(None),
    semester: int | None = Query(None, ge=1, le=12),
    section: str | None = Query(None),
    student_status: str | None = Query(None, alias="status"),
    object_id: str | None = Query(
        None, description="restrict to students linked to this Object id"
    ),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListStudentsResponseModel:
    try:
        result = ListStudentsUseCase(repo).execute(
            _list_query(page, page_size, q, student_type, programme, semester,
                        section, student_status, object_id)
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListStudentsResponseModel(
        items=[StudentResponseModel(**to_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


# --- static routes are declared BEFORE /{student_id} on purpose -----------


@router.get("/export")
def export_students(
    q: str | None = None,
    student_type: str | None = None,
    programme: str | None = None,
    semester: int | None = Query(None, ge=1, le=12),
    section: str | None = None,
    student_status: str | None = Query(None, alias="status"),
    object_id: str | None = None,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> Response:
    """CSV download of the SAME filtered query (ERP/Google-Sheets round-trip)."""
    use_case = ListStudentsUseCase(repo)
    records: list[dict] = []
    page = 1
    try:
        while True:  # walk every page of the same filtered query
            result = use_case.execute(
                _list_query(page, 100, q, student_type, programme, semester,
                            section, student_status, object_id)
            )
            records.extend(o.to_record() for o in result.items)
            if len(records) >= result.total_count or not result.items:
                break
            page += 1
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return Response(
        content=export_students_csv(records),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students.csv"'},
    )


@router.post("/import", response_model=ImportStudentsResultModel)
def import_students(
    req: ImportStudentsRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ImportStudentsResultModel:
    try:
        result = ImportStudentsUseCase(repo).execute(
            ImportStudentsCommand(text=req.text, created_by=str(user.id))
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ImportStudentsResultModel(
        created=result.created,
        skipped_duplicates=result.skipped_duplicates,
        errors=result.errors,
    )


@router.get("/{student_id}", response_model=StudentResponseModel)
def get_student(
    student_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> StudentResponseModel:
    try:
        out = GetStudentUseCase(repo).execute(
            GetStudentQuery(object_id=ObjectId.parse(student_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return StudentResponseModel(**to_response(out))


@router.post("", response_model=StudentResponseModel, status_code=status.HTTP_201_CREATED)
def create_student(
    req: CreateStudentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> StudentResponseModel:
    try:
        out = CreateStudentUseCase(repo).execute(
            CreateStudentCommand(input=to_create_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return StudentResponseModel(**to_response(out))


@router.put("/{student_id}", response_model=StudentResponseModel)
@router.patch("/{student_id}", response_model=StudentResponseModel)
def update_student(
    student_id: str,
    req: UpdateStudentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> StudentResponseModel:
    try:
        out = UpdateStudentUseCase(repo).execute(
            UpdateStudentCommand(
                object_id=ObjectId.parse(student_id),
                input=to_update_input(body={**req.model_dump(exclude_unset=True), "updated_by": str(user.id)}),
            )
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return StudentResponseModel(**to_response(out))


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_student(
    student_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteStudentUseCase(repo).execute(
            DeleteStudentCommand(object_id=ObjectId.parse(student_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return None
