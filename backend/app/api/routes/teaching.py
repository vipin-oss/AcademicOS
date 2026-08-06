"""Teaching API routes — classes, enrollment, assignments, submissions,
marks, attendance, gradebook, reports and the faculty dashboard.

Backed entirely by the frozen Application layer over the Universal Object
model (Class=course, Assignment=assignment, Submission=submission,
AttendanceSession=attendance_session). Route map:

  - GET    /teaching/dashboard                          -> TeachingDashboardUseCase
  - GET    /teaching/classes                            -> ListClassesUseCase
  - POST   /teaching/classes                            -> CreateClassUseCase
  - GET    /teaching/classes/{class_id}                 -> GetClassUseCase
  - PUT    /teaching/classes/{class_id}                 -> UpdateClassUseCase
  - PATCH  /teaching/classes/{class_id}                 -> UpdateClassUseCase
  - DELETE /teaching/classes/{class_id}                 -> DeleteClassUseCase (cascade report)
  - GET    /teaching/classes/{class_id}/roster          -> GetRosterUseCase
  - POST   /teaching/classes/{class_id}/enroll          -> EnrollStudentsUseCase
  - POST   /teaching/classes/{class_id}/enroll/csv      -> EnrollFromCsvUseCase
  - DELETE /teaching/classes/{class_id}/enroll/{sid}    -> UnenrollStudentUseCase
  - GET    /teaching/classes/{class_id}/report          -> GetClassReportUseCase
  - GET    /teaching/classes/{class_id}/gradebook       -> GetGradebookUseCase
  - GET    /teaching/classes/{class_id}/gradebook/export-> gradebook CSV download
  - GET    /teaching/classes/{class_id}/attendance      -> ListAttendanceUseCase
  - POST   /teaching/classes/{class_id}/attendance      -> RecordAttendanceUseCase
  - POST   /teaching/classes/{class_id}/attendance/import -> ImportAttendanceCsvUseCase
  - GET    /teaching/classes/{class_id}/attendance/summary -> GetAttendanceSummaryUseCase
  - GET    /teaching/classes/{class_id}/assignments     -> ListAssignmentsUseCase (class lens)
  - POST   /teaching/classes/{class_id}/assignments     -> CreateAssignmentUseCase (class-scoped)
  - GET    /teaching/assignments                        -> ListAssignmentsUseCase
  - GET    /teaching/assignments/{id}                   -> GetAssignmentUseCase
  - POST   /teaching/assignments                        -> CreateAssignmentUseCase (body class_id)
  - PUT    /teaching/assignments/{id}                   -> UpdateAssignmentUseCase
  - PATCH  /teaching/assignments/{id}                   -> UpdateAssignmentUseCase
  - DELETE /teaching/assignments/{id}                   -> DeleteAssignmentUseCase (cascade report)
  - PUT    /teaching/assignments/{id}/attachment        -> AttachAssignmentFileUseCase
  - GET    /teaching/assignments/{id}/attachment        -> download the attachment
  - GET    /teaching/assignments/{id}/grid              -> GetSubmissionGridUseCase
  - POST   /teaching/assignments/{id}/submit            -> SubmitToAssignmentUseCase (multipart)
  - POST   /teaching/assignments/{id}/marks/import      -> ImportMarksCsvUseCase (Google loop)
  - GET    /teaching/submissions                        -> ListSubmissionsUseCase (lenses)
  - GET    /teaching/submissions/{id}                   -> GetSubmissionUseCase
  - PUT    /teaching/submissions/{id}/grade             -> GradeSubmissionUseCase
  - PATCH  /teaching/submissions/{id}/grade             -> GradeSubmissionUseCase
  - DELETE /teaching/submissions/{id}                   -> DeleteSubmissionUseCase
  - GET    /teaching/submissions/{id}/file              -> download the submission file

``/teaching/dashboard`` and sub-paths under /classes/{class_id}/… are
declared so they are never captured as an id segment.
"""
from __future__ import annotations

import mimetypes

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.api.mappers import teaching_mapper as m
from app.application.commands.attach_assignment_file import AttachAssignmentFileCommand
from app.application.commands.create_assignment import CreateAssignmentCommand
from app.application.commands.create_class import CreateClassCommand
from app.application.commands.delete_assignment import DeleteAssignmentCommand
from app.application.commands.delete_class import DeleteClassCommand
from app.application.commands.delete_submission import DeleteSubmissionCommand
from app.application.commands.enroll_from_csv import EnrollFromCsvCommand
from app.application.commands.enroll_students import EnrollStudentsCommand
from app.application.commands.grade_submission import GradeSubmissionCommand
from app.application.commands.import_attendance_csv import ImportAttendanceCsvCommand
from app.application.commands.import_marks_csv import ImportMarksCsvCommand
from app.application.commands.record_attendance import RecordAttendanceCommand
from app.application.commands.submit_to_assignment import SubmitToAssignmentCommand
from app.application.commands.unenroll_student import UnenrollStudentCommand
from app.application.commands.update_assignment import UpdateAssignmentCommand
from app.application.commands.update_class import UpdateClassCommand
from app.application.exceptions import (
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_assignment import GetAssignmentQuery
from app.application.queries.get_attendance_summary import GetAttendanceSummaryQuery
from app.application.queries.get_class import GetClassQuery
from app.application.queries.get_class_report import GetClassReportQuery
from app.application.queries.get_gradebook import GetGradebookQuery
from app.application.queries.get_roster import GetRosterQuery
from app.application.queries.get_submission import GetSubmissionQuery
from app.application.queries.get_submission_grid import GetSubmissionGridQuery
from app.application.queries.get_teaching_dashboard import GetTeachingDashboardQuery
from app.application.queries.list_assignments import ListAssignmentsQuery
from app.application.queries.list_attendance import ListAttendanceQuery
from app.application.queries.list_classes import ListClassesQuery
from app.application.queries.list_submissions import ListSubmissionsQuery
from app.application.services.teaching_csv import export_gradebook_csv
from app.application.use_cases.teaching.attach_assignment_file import (
    AttachAssignmentFileUseCase,
)
from app.application.use_cases.teaching.attendance_summary import (
    GetAttendanceSummaryUseCase,
)
from app.application.use_cases.teaching.create_assignment import CreateAssignmentUseCase
from app.application.use_cases.teaching.create_class import CreateClassUseCase
from app.application.use_cases.teaching.delete_assignment import DeleteAssignmentUseCase
from app.application.use_cases.teaching.delete_class import DeleteClassUseCase
from app.application.use_cases.teaching.delete_submission import DeleteSubmissionUseCase
from app.application.use_cases.teaching.enroll_from_csv import EnrollFromCsvUseCase
from app.application.use_cases.teaching.enroll_students import EnrollStudentsUseCase
from app.application.use_cases.teaching.get_assignment import GetAssignmentUseCase
from app.application.use_cases.teaching.get_class import GetClassUseCase
from app.application.use_cases.teaching.get_class_report import GetClassReportUseCase
from app.application.use_cases.teaching.get_gradebook import GetGradebookUseCase
from app.application.use_cases.teaching.get_submission import GetSubmissionUseCase
from app.application.use_cases.teaching.get_submission_grid import (
    GetSubmissionGridUseCase,
)
from app.application.use_cases.teaching.get_teaching_dashboard import (
    GetTeachingDashboardUseCase,
)
from app.application.use_cases.teaching.grade_submission import GradeSubmissionUseCase
from app.application.use_cases.teaching.import_attendance_csv import (
    ImportAttendanceCsvUseCase,
)
from app.application.use_cases.teaching.import_marks_csv import ImportMarksCsvUseCase
from app.application.use_cases.teaching.list_assignments import ListAssignmentsUseCase
from app.application.use_cases.teaching.list_attendance import ListAttendanceUseCase
from app.application.use_cases.teaching.list_classes import ListClassesUseCase
from app.application.use_cases.teaching.list_submissions import ListSubmissionsUseCase
from app.application.use_cases.teaching.record_attendance import RecordAttendanceUseCase
from app.application.use_cases.teaching.roster import GetRosterUseCase
from app.application.use_cases.teaching.submit_to_assignment import (
    SubmitToAssignmentUseCase,
)
from app.application.use_cases.teaching.unenroll_student import UnenrollStudentUseCase
from app.application.use_cases.teaching.update_assignment import UpdateAssignmentUseCase
from app.application.use_cases.teaching.update_class import UpdateClassUseCase
from app.core.config import settings
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/teaching", tags=["teaching"], dependencies=[Depends(get_current_user)])


# --------------------------------------------------------------------------
# Request / response shapes (Pydantic at the boundary, like publications)
# --------------------------------------------------------------------------
class CreateClassRequest(BaseModel):
    """JSON body for POST /teaching/classes (manual creation)."""

    title: str
    uploaded_by: str
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    session: str | None = None
    credits: float | None = None
    weekly_schedule: list | None = None
    room: str | None = None
    class_mode: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    status: str = "draft"
    links: dict | None = None
    students: list[str] | None = None  # initial enrollment (Object ids)


class UpdateClassRequest(CreateClassRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class EnrollRequest(BaseModel):
    student_ids: list[str]
    actor: str = "system"


class CsvImportRequest(BaseModel):
    text: str
    actor: str = "system"


class CreateAssignmentRequest(BaseModel):
    """JSON body for creating an Assignment (class id from path OR body)."""

    title: str
    uploaded_by: str
    class_id: str | None = None
    assignment_type: str = "assignment"
    description: str | None = None
    instructions: str | None = None
    max_marks: float | None = None
    deadline: str | None = None
    late_allowed: bool = False
    rubric: list | None = None
    visibility: str = "visible"
    weightage: float | None = None
    status: str = "draft"


class UpdateAssignmentRequest(CreateAssignmentRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    title: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class RecordAttendanceRequest(BaseModel):
    session_date: str  # YYYY-MM-DD
    records: dict[str, str]  # {student_id: present|absent|late|medical_leave}
    actor: str = "system"


class ImportAttendanceRequest(BaseModel):
    session_date: str
    text: str
    actor: str = "system"


class GradeSubmissionRequest(BaseModel):
    marks: float | None = None
    faculty_feedback: str | None = None
    rubric_score: list | None = None
    actor: str = "system"


class ClassResponseModel(BaseModel):
    id: str
    title: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    session: str | None = None
    credits: float | None = None
    weekly_schedule: list[dict] = []
    room: str | None = None
    class_mode: str | None = None
    notes: str | None = None
    tags: list[str] = []
    student_count: int = 0
    links: dict[str, list[dict]] = {}
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListClassesResponseModel(BaseModel):
    items: list[ClassResponseModel] = []
    total_count: int
    page: int
    page_size: int


class AssignmentResponseModel(BaseModel):
    id: str
    title: str
    class_id: str
    class_title: str | None = None
    assignment_type: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    description: str | None = None
    instructions: str | None = None
    max_marks: float | None = None
    deadline: str | None = None
    late_allowed: bool = False
    rubric: list[dict] = []
    visibility: str = "visible"
    weightage: float | None = None
    attachment_file_name: str | None = None
    attachment_file_size: int = 0
    attachment_mime_type: str | None = None
    attachment_file_path: str | None = None
    attachment_url: str | None = None
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListAssignmentsResponseModel(BaseModel):
    items: list[AssignmentResponseModel] = []
    total_count: int
    page: int
    page_size: int


class SubmissionResponseModel(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student_name: str | None = None
    student_roll: str | None = None
    submitted_at: str | None = None
    is_late: bool = False
    comments: str | None = None
    marks: float | None = None
    faculty_feedback: str | None = None
    rubric_score: list[dict] = []
    graded_at: str | None = None
    graded_by: str | None = None
    file_name: str | None = None
    file_size: int = 0
    file_mime_type: str | None = None
    file_path: str | None = None
    file_url: str | None = None
    status: str
    version: int
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListSubmissionsResponseModel(BaseModel):
    items: list[SubmissionResponseModel] = []
    total_count: int
    page: int
    page_size: int


# --------------------------------------------------------------------------
# Dependencies (mirror publications.py)
# --------------------------------------------------------------------------
def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_storage() -> LocalFileStorage:
    """Storage dependency (overridable in tests; the configured adapter in prod)."""
    return LocalFileStorage(settings.storage_dir)


def _attachment_url(out, storage: LocalFileStorage) -> str | None:
    if not out.attachment_file_path or not storage.exists(out.attachment_file_path):
        return None
    return (
        f"{settings.public_base_url}{settings.api_v1_prefix}"
        f"/teaching/assignments/{out.id}/attachment"
    )


def _file_url(out, storage: LocalFileStorage) -> str | None:
    if not out.file_path or not storage.exists(out.file_path):
        return None
    return (
        f"{settings.public_base_url}{settings.api_v1_prefix}"
        f"/teaching/submissions/{out.id}/file"
    )


def _assignment_response(out, storage) -> AssignmentResponseModel:
    return AssignmentResponseModel(
        **m.assignment_to_response(out, attachment_url=_attachment_url(out, storage))
    )


def _submission_response(out, storage) -> SubmissionResponseModel:
    return SubmissionResponseModel(
        **m.submission_to_response(out, file_url=_file_url(out, storage))
    )


def _handle_common(exc: Exception) -> HTTPException:
    if isinstance(exc, ObjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError | InvalidStateTransitionError | ValueError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# --------------------------------------------------------------------------
# Faculty dashboard (PART J) — declared before /classes so it is never an id
# --------------------------------------------------------------------------
@router.get("/dashboard")
def teaching_dashboard(
    attendance_threshold: float = Query(75.0, ge=0, le=100),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        dashboard = GetTeachingDashboardUseCase(repo).execute(
            GetTeachingDashboardQuery(attendance_threshold=attendance_threshold)
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return m.dashboard_to_response(dashboard)


# --------------------------------------------------------------------------
# Classes (PART B)
# --------------------------------------------------------------------------
@router.get("/classes", response_model=ListClassesResponseModel)
def list_classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    semester: int | None = Query(None, ge=1, le=12),
    session: str | None = Query(None),
    class_status: str | None = Query(None, alias="status"),
    object_id: str | None = Query(
        None, description="lens: classes this Object is linked to (student/faculty)"
    ),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListClassesResponseModel:
    try:
        result = ListClassesUseCase(repo).execute(
            ListClassesQuery(
                page=page,
                page_size=page_size,
                q=q or None,
                semester=semester,
                session=session or None,
                status=class_status or None,
                object_id=ObjectId.parse(object_id) if object_id else None,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListClassesResponseModel(
        items=[ClassResponseModel(**m.class_to_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post(
    "/classes", response_model=ClassResponseModel, status_code=status.HTTP_201_CREATED
)
def create_class(
    req: CreateClassRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ClassResponseModel:
    try:
        out = CreateClassUseCase(repo).execute(
            CreateClassCommand(input=m.to_create_class_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ClassResponseModel(**m.class_to_response(out))


@router.get("/classes/{class_id}", response_model=ClassResponseModel)
def get_class(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ClassResponseModel:
    try:
        out = GetClassUseCase(repo).execute(GetClassQuery(object_id=ObjectId.parse(class_id)))
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return ClassResponseModel(**m.class_to_response(out))


@router.put("/classes/{class_id}", response_model=ClassResponseModel)
@router.patch("/classes/{class_id}", response_model=ClassResponseModel)
def update_class(
    class_id: str,
    req: UpdateClassRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ClassResponseModel:
    try:
        out = UpdateClassUseCase(repo).execute(
            UpdateClassCommand(
                object_id=ObjectId.parse(class_id),
                input=m.to_update_class_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except (ObjectNotFoundError, ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _handle_common(exc)
    return ClassResponseModel(**m.class_to_response(out))


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> dict:
    try:
        return DeleteClassUseCase(repo, storage).execute(
            DeleteClassCommand(object_id=ObjectId.parse(class_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)


# --------------------------------------------------------------------------
# Enrollment (PART C)
# --------------------------------------------------------------------------
@router.get("/classes/{class_id}/roster")
def class_roster(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> list[dict]:
    try:
        entries = GetRosterUseCase(repo).execute(
            GetRosterQuery(class_id=ObjectId.parse(class_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return m.roster_to_response(entries)


@router.post("/classes/{class_id}/enroll")
def enroll_students(
    class_id: str,
    req: EnrollRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        result = EnrollStudentsUseCase(repo).execute(
            EnrollStudentsCommand(
                class_id=ObjectId.parse(class_id),
                student_ids=tuple(ObjectId.parse(sid) for sid in req.student_ids),
                actor=req.actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return m.enrollment_result_to_response(result)


@router.post("/classes/{class_id}/enroll/csv")
def enroll_students_csv(
    class_id: str,
    req: CsvImportRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        result = EnrollFromCsvUseCase(repo).execute(
            EnrollFromCsvCommand(
                class_id=ObjectId.parse(class_id), text=req.text, actor=req.actor
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return m.enrollment_result_to_response(result)


@router.delete(
    "/classes/{class_id}/enroll/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def unenroll_student(
    class_id: str,
    student_id: str,
    actor: str = "system",
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        UnenrollStudentUseCase(repo).execute(
            UnenrollStudentCommand(
                class_id=ObjectId.parse(class_id),
                student_id=ObjectId.parse(student_id),
                actor=actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return None


# --------------------------------------------------------------------------
# Class report + gradebook (PARTS H + K)
# --------------------------------------------------------------------------
@router.get("/classes/{class_id}/report")
def class_report(
    class_id: str,
    attendance_threshold: float = Query(75.0, ge=0, le=100),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        report = GetClassReportUseCase(repo).execute(
            GetClassReportQuery(
                class_id=ObjectId.parse(class_id),
                attendance_threshold=attendance_threshold,
            )
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return m.report_to_response(report)


@router.get("/classes/{class_id}/gradebook")
def class_gradebook(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        gradebook = GetGradebookUseCase(repo).execute(
            GetGradebookQuery(class_id=ObjectId.parse(class_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return m.gradebook_to_response(gradebook)


@router.get("/classes/{class_id}/gradebook/export")
def class_gradebook_export(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> Response:
    """University-format marks sheet foundation (CSV download)."""
    try:
        gradebook = GetGradebookUseCase(repo).execute(
            GetGradebookQuery(class_id=ObjectId.parse(class_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    headers, rows = m.gradebook_csv_parts(gradebook)
    return Response(
        content=export_gradebook_csv(headers, rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="gradebook.csv"'},
    )


# --------------------------------------------------------------------------
# Attendance (PART I)
# --------------------------------------------------------------------------
@router.get("/classes/{class_id}/attendance")
def list_attendance(
    class_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> list[dict]:
    try:
        sessions = ListAttendanceUseCase(repo).execute(
            ListAttendanceQuery(class_id=ObjectId.parse(class_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return [m.attendance_session_to_response(s) for s in sessions]


@router.post("/classes/{class_id}/attendance", status_code=status.HTTP_201_CREATED)
def record_attendance(
    class_id: str,
    req: RecordAttendanceRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        out = RecordAttendanceUseCase(repo).execute(
            RecordAttendanceCommand(
                class_id=ObjectId.parse(class_id),
                session_date=req.session_date,
                records=req.records,
                actor=req.actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return m.attendance_session_to_response(out)


@router.post("/classes/{class_id}/attendance/import")
def import_attendance_csv(
    class_id: str,
    req: ImportAttendanceRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        result = ImportAttendanceCsvUseCase(repo).execute(
            ImportAttendanceCsvCommand(
                class_id=ObjectId.parse(class_id),
                session_date=req.session_date,
                text=req.text,
                actor=req.actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return m.attendance_import_to_response(result)


@router.get("/classes/{class_id}/attendance/summary")
def attendance_summary(
    class_id: str,
    threshold: float = Query(75.0, ge=0, le=100),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        summary = GetAttendanceSummaryUseCase(repo).execute(
            GetAttendanceSummaryQuery(
                class_id=ObjectId.parse(class_id), threshold=threshold
            )
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return m.attendance_summary_to_response(summary)


# --------------------------------------------------------------------------
# Assignments (PART D)
# --------------------------------------------------------------------------
@router.post(
    "/classes/{class_id}/assignments",
    response_model=AssignmentResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment_for_class(
    class_id: str,
    req: CreateAssignmentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> AssignmentResponseModel:
    try:
        out = CreateAssignmentUseCase(repo).execute(
            CreateAssignmentCommand(
                input=m.to_create_assignment_input(
                    body=req.model_dump(), class_id=ObjectId.parse(class_id)
                )
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return _assignment_response(out, storage)


@router.get("/classes/{class_id}/assignments", response_model=ListAssignmentsResponseModel)
def list_class_assignments(
    class_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> ListAssignmentsResponseModel:
    try:
        result = ListAssignmentsUseCase(repo).execute(
            ListAssignmentsQuery(
                page=page, page_size=page_size, class_id=ObjectId.parse(class_id)
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return ListAssignmentsResponseModel(
        items=[_assignment_response(o, storage) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/assignments", response_model=ListAssignmentsResponseModel)
def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    class_id: str | None = Query(None),
    q: str | None = Query(None),
    assignment_type: str | None = Query(None),
    visibility: str | None = Query(None),
    assignment_status: str | None = Query(None, alias="status"),
    object_id: str | None = Query(None, description="lens: assignments of this Class"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> ListAssignmentsResponseModel:
    try:
        result = ListAssignmentsUseCase(repo).execute(
            ListAssignmentsQuery(
                page=page,
                page_size=page_size,
                class_id=ObjectId.parse(class_id) if class_id else None,
                q=q or None,
                assignment_type=assignment_type or None,
                visibility=visibility or None,
                status=assignment_status or None,
                object_id=ObjectId.parse(object_id) if object_id else None,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListAssignmentsResponseModel(
        items=[_assignment_response(o, storage) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.post(
    "/assignments",
    response_model=AssignmentResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    req: CreateAssignmentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
) -> AssignmentResponseModel:
    try:
        out = CreateAssignmentUseCase(repo).execute(
            CreateAssignmentCommand(input=m.to_create_assignment_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return _assignment_response(out, storage)


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponseModel)
def get_assignment(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> AssignmentResponseModel:
    try:
        out = GetAssignmentUseCase(repo).execute(
            GetAssignmentQuery(object_id=ObjectId.parse(assignment_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return _assignment_response(out, storage)


@router.put("/assignments/{assignment_id}", response_model=AssignmentResponseModel)
@router.patch("/assignments/{assignment_id}", response_model=AssignmentResponseModel)
def update_assignment(
    assignment_id: str,
    req: UpdateAssignmentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> AssignmentResponseModel:
    try:
        out = UpdateAssignmentUseCase(repo).execute(
            UpdateAssignmentCommand(
                object_id=ObjectId.parse(assignment_id),
                input=m.to_update_assignment_input(body=req.model_dump(exclude_unset=True)),
            )
        )
    except (ObjectNotFoundError, ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise _handle_common(exc)
    return _assignment_response(out, storage)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> dict:
    try:
        return DeleteAssignmentUseCase(repo, storage).execute(
            DeleteAssignmentCommand(object_id=ObjectId.parse(assignment_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)


@router.put("/assignments/{assignment_id}/attachment", response_model=AssignmentResponseModel)
def attach_assignment_file(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    file: UploadFile = File(...),
    uploaded_by: str = "system",
) -> AssignmentResponseModel:
    content = file.file.read()
    file_name = file.filename or "attachment"
    mime_type = (
        file.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    )
    try:
        out = AttachAssignmentFileUseCase(repo, storage).execute(
            AttachAssignmentFileCommand(
                object_id=ObjectId.parse(assignment_id),
                file_name=file_name,
                content=content,
                mime_type=mime_type,
                actor=uploaded_by,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return _assignment_response(out, storage)


@router.get("/assignments/{assignment_id}/attachment")
def download_assignment_attachment(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        out = GetAssignmentUseCase(repo).execute(
            GetAssignmentQuery(object_id=ObjectId.parse(assignment_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    if not out.attachment_file_path or not storage.exists(out.attachment_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No file is attached to this assignment.",
        )
    safe_name = (out.attachment_file_name or out.title or "attachment").replace('"', "_")
    return Response(
        content=storage.read(out.attachment_file_path),
        media_type=out.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


# --------------------------------------------------------------------------
# Submissions (PART E) + grid + marks CSV (PARTS F/G)
# --------------------------------------------------------------------------
@router.get("/assignments/{assignment_id}/grid")
def submission_grid(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> dict:
    try:
        grid = GetSubmissionGridUseCase(repo).execute(
            GetSubmissionGridQuery(assignment_id=ObjectId.parse(assignment_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    payload = m.grid_to_response(grid)
    for row in payload["rows"]:
        if row["submission"] is not None:
            row["submission"]["file_url"] = (
                f"{settings.public_base_url}{settings.api_v1_prefix}"
                f"/teaching/submissions/{row['submission']['id']}/file"
                if row["submission"].get("file_path")
                and storage.exists(row["submission"]["file_path"])
                else None
            )
    return payload


@router.post(
    "/assignments/{assignment_id}/submit",
    response_model=SubmissionResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def submit_to_assignment(
    assignment_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    student_id: str = Form(...),
    comments: str | None = Form(None),
    submitted_at: str | None = Form(None),
    actor: str = Form("system"),
    file: UploadFile | None = File(None),
) -> SubmissionResponseModel:
    content = file.file.read() if file is not None else None
    file_name = file.filename if file is not None else None
    mime_type = (
        (file.content_type or mimetypes.guess_type(file_name or "")[0])
        if file is not None
        else None
    )
    try:
        out = SubmitToAssignmentUseCase(repo, storage).execute(
            SubmitToAssignmentCommand(
                assignment_id=ObjectId.parse(assignment_id),
                student_id=ObjectId.parse(student_id),
                file_name=file_name,
                content=content,
                mime_type=mime_type,
                comments=comments,
                submitted_at=submitted_at,
                actor=actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return _submission_response(out, storage)


@router.post("/assignments/{assignment_id}/marks/import")
def import_marks_csv(
    assignment_id: str,
    req: CsvImportRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> dict:
    try:
        result = ImportMarksCsvUseCase(repo).execute(
            ImportMarksCsvCommand(
                assignment_id=ObjectId.parse(assignment_id),
                text=req.text,
                actor=req.actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return m.marks_import_to_response(result)


@router.get("/submissions", response_model=ListSubmissionsResponseModel)
def list_submissions(
    assignment_id: str | None = Query(None),
    student_id: str | None = Query(None),
    state: str | None = Query(None, description="submitted | late | graded"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> ListSubmissionsResponseModel:
    try:
        result = ListSubmissionsUseCase(repo).execute(
            ListSubmissionsQuery(
                assignment_id=ObjectId.parse(assignment_id) if assignment_id else None,
                student_id=ObjectId.parse(student_id) if student_id else None,
                state=state or None,
                page=page,
                page_size=page_size,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListSubmissionsResponseModel(
        items=[_submission_response(o, storage) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionResponseModel)
def get_submission(
    submission_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> SubmissionResponseModel:
    try:
        out = GetSubmissionUseCase(repo).execute(
            GetSubmissionQuery(object_id=ObjectId.parse(submission_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return _submission_response(out, storage)


@router.put("/submissions/{submission_id}/grade", response_model=SubmissionResponseModel)
@router.patch("/submissions/{submission_id}/grade", response_model=SubmissionResponseModel)
def grade_submission(
    submission_id: str,
    req: GradeSubmissionRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> SubmissionResponseModel:
    try:
        out = GradeSubmissionUseCase(repo).execute(
            GradeSubmissionCommand(
                object_id=ObjectId.parse(submission_id),
                marks=req.marks,
                faculty_feedback=req.faculty_feedback,
                rubric_score=tuple(req.rubric_score) if req.rubric_score is not None else None,
                actor=req.actor,
            )
        )
    except (ObjectNotFoundError, ValidationError, ValueError) as exc:
        raise _handle_common(exc)
    return _submission_response(out, storage)


@router.delete(
    "/submissions/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_submission(
    submission_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> None:
    try:
        DeleteSubmissionUseCase(repo, storage).execute(
            DeleteSubmissionCommand(object_id=ObjectId.parse(submission_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    return None


@router.get("/submissions/{submission_id}/file")
def download_submission_file(
    submission_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        out = GetSubmissionUseCase(repo).execute(
            GetSubmissionQuery(object_id=ObjectId.parse(submission_id))
        )
    except (ObjectNotFoundError, ValueError) as exc:
        raise _handle_common(exc)
    if not out.file_path or not storage.exists(out.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No file is attached to this submission.",
        )
    safe_name = (out.file_name or "submission").replace('"', "_")
    return Response(
        content=storage.read(out.file_path),
        media_type=out.file_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
