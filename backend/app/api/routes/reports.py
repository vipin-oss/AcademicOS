"""Reports & Analytics API routes (read-only aggregation slice).

Backed by the frozen Application layer, mirroring the events/finance route
modules one-to-one:
  - GET /reports                     -> the module catalogue (kinds + filters)
  - GET /reports/dashboard           -> GetReportsDashboardUseCase (PART 1)
  - GET /reports/publications        -> PART 2   (filters: year/date range/
                                       faculty/project/grant)
  - GET /reports/research            -> PART 3   (year/date/project/grant/dept)
  - GET /reports/faculty             -> PART 4   (faculty/department/year/date)
  - GET /reports/students            -> PART 5   (student/department/year/date)
  - GET /reports/teaching            -> PART 6   (year/date/faculty)
  - GET /reports/finance             -> PART 7   (year/date/project/grant/dept)
  - GET /reports/events              -> PART 8   (year/date/faculty/dept/event)
  - GET /reports/committees          -> PART 9   (year/date/faculty/committee)
  - GET /reports/analytics           -> PART 10  (year-wise trends)
  - GET /reports/export              -> PART 11  (kind, pdf|csv|xlsx)

Every response is computed from the existing modules' Objects at request
time — the module stores nothing. Static branches (catalogue/dashboard/
export and the named kinds) are declared first, the frozen committees
precedent (no ``{id}`` route exists here at all — cross-links go to the
owning modules).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.mappers.reports_mapper import (
    catalogue_response,
    dashboard_response,
    report_response,
    to_export_query,
    to_report_filters,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.queries.get_analytics_report import GetAnalyticsReportQuery
from app.application.queries.get_committees_report import GetCommitteesReportQuery
from app.application.queries.get_events_report import GetEventsReportQuery
from app.application.queries.get_faculty_report import GetFacultyReportQuery
from app.application.queries.get_finance_report import GetFinanceReportQuery
from app.application.queries.get_publications_report import GetPublicationsReportQuery
from app.application.queries.get_reports_dashboard import GetReportsDashboardQuery
from app.application.queries.get_research_report import GetResearchReportQuery
from app.application.queries.get_students_report import GetStudentsReportQuery
from app.application.queries.get_teaching_report import GetTeachingReportQuery
from app.application.use_cases.reports.analytics_report import GetAnalyticsReportUseCase
from app.application.use_cases.reports.committees_report import GetCommitteesReportUseCase
from app.application.use_cases.reports.events_report import GetEventsReportUseCase
from app.application.use_cases.reports.export_report import ExportReportUseCase
from app.application.use_cases.reports.faculty_report import GetFacultyReportUseCase
from app.application.use_cases.reports.finance_report import GetFinanceReportUseCase
from app.application.use_cases.reports.get_dashboard import GetReportsDashboardUseCase
from app.application.use_cases.reports.publications_report import (
    GetPublicationsReportUseCase,
)
from app.application.use_cases.reports.research_report import GetResearchReportUseCase
from app.application.use_cases.reports.students_report import GetStudentsReportUseCase
from app.application.use_cases.reports.teaching_report import GetTeachingReportUseCase
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _unprocessable(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _not_found(exc: ObjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Shared PART 12 filter params (one dependency — the events list precedent)
# ---------------------------------------------------------------------------
def _filter_params(
    year: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    faculty_id: str | None = Query(None),
    student_id: str | None = Query(None),
    project_id: str | None = Query(None),
    grant_id: str | None = Query(None),
    department: str | None = Query(None),
    event_id: str | None = Query(None),
    committee_id: str | None = Query(None),
) -> dict:
    return {
        "year": year,
        "date_from": date_from,
        "date_to": date_to,
        "faculty_id": faculty_id,
        "student_id": student_id,
        "project_id": project_id,
        "grant_id": grant_id,
        "department": department,
        "event_id": event_id,
        "committee_id": committee_id,
    }


def _run(use_case, query) -> dict:
    try:
        return report_response(use_case.execute(query))
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc


# ---------------------------------------------------------------------------
# Catalogue + dashboard + export (static branches)
# ---------------------------------------------------------------------------
@router.get("")
def reports_catalogue():
    """The module's report catalogue (kinds + honoured PART 12 filters)."""
    return catalogue_response()


@router.get("/dashboard")
def reports_dashboard(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        return dashboard_response(
            GetReportsDashboardUseCase(repo).execute(GetReportsDashboardQuery())
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc


@router.get("/export")
def export_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    kind: str = Query(...),
    format: str = Query(...),
    params: dict = Depends(_filter_params),
):
    query = to_export_query(kind=kind, format=format, params=params)
    try:
        result = ExportReportUseCase(repo).execute(query)
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


# ---------------------------------------------------------------------------
# PART 2..10 reports
# ---------------------------------------------------------------------------
@router.get("/publications")
def publications_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetPublicationsReportUseCase(repo),
        GetPublicationsReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/research")
def research_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetResearchReportUseCase(repo),
        GetResearchReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/faculty")
def faculty_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetFacultyReportUseCase(repo),
        GetFacultyReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/students")
def students_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetStudentsReportUseCase(repo),
        GetStudentsReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/teaching")
def teaching_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetTeachingReportUseCase(repo),
        GetTeachingReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/finance")
def finance_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetFinanceReportUseCase(repo),
        GetFinanceReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/events")
def events_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetEventsReportUseCase(repo),
        GetEventsReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/committees")
def committees_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetCommitteesReportUseCase(repo),
        GetCommitteesReportQuery(filters=to_report_filters(params=params)),
    )


@router.get("/analytics")
def analytics_report(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    params: dict = Depends(_filter_params),
):
    return _run(
        GetAnalyticsReportUseCase(repo),
        GetAnalyticsReportQuery(filters=to_report_filters(params=params)),
    )
