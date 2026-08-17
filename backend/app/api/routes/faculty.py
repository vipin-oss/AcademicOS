"""Faculty API routes — Faculty Management slice (directory & profiles).

Mirrors ``research.py``/``students.py`` one-to-one, backed by the frozen
Application layer (a Faculty member is a Universal Object; every field is
metadata, every link a typed edge, the photo a FileStorage blob):

  - GET    /faculty                     -> directory list (PART 7 search + filters)
  - POST   /faculty                     -> 201 (409 duplicate employee id / code)
  - GET    /faculty/{id}                -> enriched workspace payload
                                          (profile, research, supervision,
                                           teaching load, dashboard stats)
  - PUT    /faculty/{id} / PATCH        -> merge update (409 on dup change)
  - DELETE /faculty/{id}                -> 204
  - PUT    /faculty/{id}/photo          -> attach/replace the profile photo
  - GET    /faculty/{id}/photo          -> the photo blob (inline)

Static routes are declared BEFORE parameterised ones so ids never capture
``photo``/… — same rule as every other slice.
"""
from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_object_acl
from app.domain.entities.object import UniversalObject
from app.api.mappers.faculty_mapper import (
    faculty_response,
    to_create_faculty_input,
    to_update_faculty_input,
)
from app.application.commands.attach_faculty_photo import AttachFacultyPhotoCommand
from app.application.commands.create_faculty import CreateFacultyCommand
from app.application.commands.delete_faculty import DeleteFacultyCommand
from app.application.commands.update_faculty import UpdateFacultyCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_faculty import GetFacultyQuery
from app.application.queries.list_faculty import ListFacultyQuery
from app.application.use_cases.faculty.attach_faculty_photo import (
    AttachFacultyPhotoUseCase,
)
from app.application.use_cases.faculty.create_faculty import CreateFacultyUseCase
from app.application.use_cases.faculty.delete_faculty import DeleteFacultyUseCase
from app.application.use_cases.faculty.get_faculty import GetFacultyUseCase
from app.application.use_cases.faculty.list_faculty import ListFacultyUseCase
from app.application.use_cases.faculty.update_faculty import UpdateFacultyUseCase
from app.core.config import settings
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/faculty", tags=["faculty"], dependencies=[Depends(get_current_user), Depends(require_object_acl())])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_storage() -> LocalFileStorage:
    """Storage dependency (overridable in tests; the configured adapter in prod)."""
    return LocalFileStorage(settings.storage_dir)


def _photo_url(out, storage: LocalFileStorage) -> str | None:
    """Absolute photo link when an attached blob exists, else ``None``."""
    if not out.photo_file_path or not storage.exists(out.photo_file_path):
        return None
    return f"{settings.public_base_url}{settings.api_v1_prefix}/faculty/{out.id}/photo"


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class CreateFacultyRequest(BaseModel):
    name: str
    employee_id: str
    uploaded_by: str
    status: str = "draft"
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] | None = None
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    degrees: list[dict] | None = None
    experience: list[dict] | None = None
    awards: list[dict] | None = None
    memberships: list[dict] | None = None
    certifications: list[dict] | None = None
    admin_positions: list[dict] | None = None
    links: dict | None = None  # {committees: [object ids]}


class UpdateFacultyRequest(BaseModel):
    """Partial update contract (every field optional)."""

    name: str | None = None
    employee_id: str | None = None
    uploaded_by: str = "system"
    status: str | None = None
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] | None = None
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    degrees: list[dict] | None = None
    experience: list[dict] | None = None
    awards: list[dict] | None = None
    memberships: list[dict] | None = None
    certifications: list[dict] | None = None
    admin_positions: list[dict] | None = None
    links: dict | None = None


class LinkedObjectModel(BaseModel):
    id: str
    title: str
    object_type: str
    kind: str


class SupervisedStudentModel(LinkedObjectModel):
    student_type: str


class TeachingClassModel(LinkedObjectModel):
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    credits: int | None = None
    weekly_hours: float = 0.0


class ResearchLinksModel(BaseModel):
    projects: list[LinkedObjectModel] = []
    grants: list[LinkedObjectModel] = []


class SupervisionModel(BaseModel):
    current: list[SupervisedStudentModel] = []
    completed: list[SupervisedStudentModel] = []


class TeachingLoadModel(BaseModel):
    classes: list[TeachingClassModel] = []
    total_weekly_hours: float = 0.0


class FacultyStatsModel(BaseModel):
    publications: int = 0
    active_projects: int = 0
    grants: int = 0
    students_supervised: int = 0
    courses: int = 0
    committees: int = 0


class FacultyResponseModel(BaseModel):
    id: str
    name: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    employee_id: str | None = None
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] = []
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] = []
    degrees: list[dict] = []
    experience: list[dict] = []
    awards: list[dict] = []
    memberships: list[dict] = []
    certifications: list[dict] = []
    admin_positions: list[dict] = []
    photo_file_name: str | None = None
    photo_file_size: int = 0
    photo_mime_type: str | None = None
    photo_url: str | None = None
    links: dict[str, list[LinkedObjectModel]] = {}
    research: ResearchLinksModel = ResearchLinksModel()
    supervision: SupervisionModel = SupervisionModel()
    teaching: TeachingLoadModel = TeachingLoadModel()
    stats: FacultyStatsModel = FacultyStatsModel()
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListFacultyResponseModel(BaseModel):
    items: list[FacultyResponseModel]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Directory list + create
# ---------------------------------------------------------------------------
@router.get("", response_model=ListFacultyResponseModel)
def list_faculty(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    *,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    department: str | None = Query(None),
    designation: str | None = Query(None),
    employment_type: str | None = Query(None),
    status: str | None = Query(None),
) -> ListFacultyResponseModel:
    try:
        result = ListFacultyUseCase(repo).execute(
            ListFacultyQuery(
                page=page,
                page_size=page_size,
                q=q,
                department=department,
                designation=designation,
                employment_type=employment_type,
                status=status,
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc)
    return ListFacultyResponseModel(
        items=[FacultyResponseModel(**faculty_response(out)) for out in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=FacultyResponseModel, status_code=status.HTTP_201_CREATED)
def create_faculty(
    req: CreateFacultyRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> FacultyResponseModel:
    try:
        out = CreateFacultyUseCase(repo).execute(
            CreateFacultyCommand(input=to_create_faculty_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return FacultyResponseModel(**faculty_response(out))


# ---------------------------------------------------------------------------
# Single faculty: fetch / update / delete / photo
# ---------------------------------------------------------------------------
@router.get("/{faculty_id}", response_model=FacultyResponseModel)
def get_faculty(
    faculty_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> FacultyResponseModel:
    try:
        out = GetFacultyUseCase(repo).execute(GetFacultyQuery(object_id=ObjectId.parse(faculty_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    return FacultyResponseModel(**faculty_response(out, photo_url=_photo_url(out, storage)))


@router.put("/{faculty_id}", response_model=FacultyResponseModel)
@router.patch("/{faculty_id}", response_model=FacultyResponseModel)
def update_faculty(
    faculty_id: str,
    req: UpdateFacultyRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> FacultyResponseModel:
    try:
        out = UpdateFacultyUseCase(repo).execute(
            UpdateFacultyCommand(
                object_id=ObjectId.parse(faculty_id),
                input=to_update_faculty_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ObjectAlreadyExistsError as exc:
        raise _conflict(exc)
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _unprocessable(exc)
    return FacultyResponseModel(**faculty_response(out, photo_url=_photo_url(out, storage)))


@router.delete("/{faculty_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_faculty(
    faculty_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteFacultyUseCase(repo).execute(DeleteFacultyCommand(object_id=ObjectId.parse(faculty_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)


@router.put("/{faculty_id}/photo", response_model=FacultyResponseModel)
def attach_faculty_photo(
    faculty_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    file: UploadFile = File(...),
    uploaded_by: str = "system",
) -> FacultyResponseModel:
    content = file.file.read()
    file_name = file.filename or "profile.jpg"
    mime_type = file.content_type or mimetypes.guess_type(file_name)[0] or "image/jpeg"
    try:
        out = AttachFacultyPhotoUseCase(repo, storage).execute(
            AttachFacultyPhotoCommand(
                object_id=ObjectId.parse(faculty_id),
                file_name=file_name,
                content=content,
                mime_type=mime_type,
                actor=uploaded_by,
            )
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except (ValidationError, ValueError) as exc:
        raise _unprocessable(exc)
    return FacultyResponseModel(**faculty_response(out, photo_url=_photo_url(out, storage)))


@router.get("/{faculty_id}/photo")
def download_faculty_photo(
    faculty_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        out = GetFacultyUseCase(repo).execute(GetFacultyQuery(object_id=ObjectId.parse(faculty_id)))
    except ObjectNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _unprocessable(exc)
    if not out.photo_file_path or not storage.exists(out.photo_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile photo is attached to this faculty member.",
        )
    return Response(
        content=storage.read(out.photo_file_path),
        media_type=out.photo_mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/export")
def export_faculty(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> Response:
    """Export faculty as CSV."""
    import csv
    import io

    from app.domain.value_objects.enums import ObjectType

    faculty = repo.list_by_type(ObjectType.FACULTY)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "designation", "department", "email", "phone", "created_at"])
    for f in faculty:
        writer.writerow([
            f.title or "",
            f.metadata.get_value("designation") or "",
            f.metadata.get_value("department") or "",
            f.metadata.get_value("email") or "",
            f.metadata.get_value("phone") or "",
            str(f.created_at) if f.created_at else "",
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="faculty.csv"'},
    )
