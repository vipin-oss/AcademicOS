"""Pure mapping between Research API shapes and Application DTOs.

Mirrors ``student_mapper.py``: framework-free so it stays unit-testable
without FastAPI/Pydantic/SQLAlchemy.
"""
from __future__ import annotations

from app.application.dtos.research import (
    GRANT_GROUP_TO_KIND,
    GRANT_LINK_GROUPS,
    PROJECT_GROUP_TO_KIND,
    PROJECT_LINK_GROUPS,
    TEAM_GROUPS,
    AgencyOutput,
    CreateAgencyInput,
    CreateGrantInput,
    CreateProjectInput,
    ExpenditureInput,
    ExpenditureOutput,
    GrantOutput,
    InstallmentInput,
    InstallmentOutput,
    MilestoneInput,
    MilestoneOutput,
    ProgressUpdateInput,
    ProjectOutput,
    ResearchDashboardOutput,
    UpdateAgencyInput,
    UpdateGrantInput,
    UpdateMilestoneInput,
    UpdateProjectInput,
)
from app.domain.value_objects.enums import ObjectStatus
from app.domain.value_objects.object_id import ObjectId


def parse_links_field(
    raw: dict | None, group_to_kind: dict, groups: tuple[str, ...]
) -> dict[str, tuple[ObjectId, ...]] | None:
    """Parse {group: [object_id, ...]} into typed ObjectId tuples."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"links must be an object of {{{', '.join(groups)}: [ids]}}.")
    links: dict[str, tuple[ObjectId, ...]] = {}
    for group, ids in raw.items():
        if group not in group_to_kind:
            raise ValueError(
                f"Unknown link group: {group!r} (expected one of {', '.join(groups)})."
            )
        if not isinstance(ids, list):
            raise ValueError(f"links.{group} must be an array of Object ids.")
        links[group] = tuple(ObjectId.parse(str(oid)) for oid in ids)
    return links


def parse_team_field(raw: dict | None) -> dict[str, tuple[ObjectId, ...]] | None:
    """Parse {principal_investigators|co_investigators|team_members: [ids]}."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"team must be an object of {{{', '.join(TEAM_GROUPS)}: [ids]}}.")
    team: dict[str, tuple[ObjectId, ...]] = {}
    for group, ids in raw.items():
        if group not in TEAM_GROUPS:
            raise ValueError(
                f"Unknown team group: {group!r} (expected one of {', '.join(TEAM_GROUPS)})."
            )
        if not isinstance(ids, list):
            raise ValueError(f"team.{group} must be an array of Object ids.")
        team[group] = tuple(ObjectId.parse(str(oid)) for oid in ids)
    return team


def _opt_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


# ---------------------------------------------------------------------------
# Project bodies
# ---------------------------------------------------------------------------
def to_create_project_input(*, body: dict) -> CreateProjectInput:
    return CreateProjectInput(
        title=str(body.get("title") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        lifecycle_status=str(body.get("lifecycle_status") or "draft"),
        project_code=body.get("project_code"),
        department=body.get("department"),
        grant_number=body.get("grant_number"),
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        duration=body.get("duration"),
        budget_approved=_opt_float(body.get("budget_approved")),
        budget_utilized=_opt_float(body.get("budget_utilized")),
        objectives=body.get("objectives"),
        keywords=tuple(str(k) for k in (body.get("keywords") or [])),
        abstract=body.get("abstract"),
        priority=body.get("priority"),
        notes=body.get("notes"),
        tags=tuple(str(t) for t in (body.get("tags") or [])),
        links=parse_links_field(body.get("links"), PROJECT_GROUP_TO_KIND, PROJECT_LINK_GROUPS),
        team=parse_team_field(body.get("team")),
    )


def to_update_project_input(*, body: dict) -> UpdateProjectInput:
    """Frozen merge contract: an absent key leaves the field untouched."""

    def present(name: str):
        return body[name] if name in body else None

    return UpdateProjectInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        lifecycle_status=present("lifecycle_status"),
        project_code=present("project_code"),
        department=present("department"),
        grant_number=present("grant_number"),
        start_date=present("start_date"),
        end_date=present("end_date"),
        duration=present("duration"),
        budget_approved=_opt_float(body["budget_approved"]) if "budget_approved" in body else None,
        budget_utilized=_opt_float(body["budget_utilized"]) if "budget_utilized" in body else None,
        objectives=present("objectives"),
        keywords=(tuple(str(k) for k in body["keywords"]) if "keywords" in body else None),
        abstract=present("abstract"),
        priority=present("priority"),
        notes=present("notes"),
        tags=(tuple(str(t) for t in body["tags"]) if "tags" in body else None),
        links=(
            parse_links_field(body["links"], PROJECT_GROUP_TO_KIND, PROJECT_LINK_GROUPS)
            if "links" in body
            else None
        ),
        team=parse_team_field(body["team"]) if "team" in body else None,
    )


# ---------------------------------------------------------------------------
# Grant bodies
# ---------------------------------------------------------------------------
def to_create_grant_input(*, body: dict) -> CreateGrantInput:
    return CreateGrantInput(
        title=str(body.get("title") or ""),
        grant_number=str(body.get("grant_number") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        amount=_opt_float(body.get("amount")),
        release_schedule=body.get("release_schedule"),
        notes=body.get("notes"),
        links=parse_links_field(body.get("links"), GRANT_GROUP_TO_KIND, GRANT_LINK_GROUPS),
    )


def to_update_grant_input(*, body: dict) -> UpdateGrantInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateGrantInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        grant_number=present("grant_number"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        amount=_opt_float(body["amount"]) if "amount" in body else None,
        release_schedule=present("release_schedule"),
        notes=present("notes"),
        links=(
            parse_links_field(body["links"], GRANT_GROUP_TO_KIND, GRANT_LINK_GROUPS)
            if "links" in body
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Agency bodies
# ---------------------------------------------------------------------------
def to_create_agency_input(*, body: dict) -> CreateAgencyInput:
    return CreateAgencyInput(
        name=str(body.get("name") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        website=body.get("website"),
        scheme=body.get("scheme"),
        contact_person=body.get("contact_person"),
        contact_email=body.get("contact_email"),
        contact_phone=body.get("contact_phone"),
        address=body.get("address"),
        notes=body.get("notes"),
    )


def to_update_agency_input(*, body: dict) -> UpdateAgencyInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateAgencyInput(
        actor=str(body.get("uploaded_by") or "system"),
        name=present("name"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        website=present("website"),
        scheme=present("scheme"),
        contact_person=present("contact_person"),
        contact_email=present("contact_email"),
        contact_phone=present("contact_phone"),
        address=present("address"),
        notes=present("notes"),
    )


# ---------------------------------------------------------------------------
# Timeline / budget child bodies
# ---------------------------------------------------------------------------
def to_milestone_input(*, body: dict) -> MilestoneInput:
    return MilestoneInput(
        title=str(body.get("title") or ""),
        date=str(body.get("date") or ""),
        status=str(body.get("status") or "pending"),
        notes=body.get("notes"),
    )


def to_update_milestone_input(*, body: dict, actor: str) -> UpdateMilestoneInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateMilestoneInput(
        actor=actor,
        title=present("title"),
        date=present("date"),
        status=present("status"),
        notes=present("notes"),
    )


def to_progress_update_input(*, body: dict) -> ProgressUpdateInput:
    return ProgressUpdateInput(
        date=str(body.get("date") or ""),
        percent=float(body.get("percent")),
        remark=str(body.get("remark") or ""),
    )


def to_installment_input(*, body: dict) -> InstallmentInput:
    return InstallmentInput(
        installment_no=int(body.get("installment_no")),
        date=str(body.get("date") or ""),
        amount=float(body.get("amount")),
        status=str(body.get("status") or "released"),
        notes=body.get("notes"),
    )


def to_expenditure_input(*, body: dict) -> ExpenditureInput:
    return ExpenditureInput(
        date=str(body.get("date") or ""),
        head=str(body.get("head") or ""),
        amount=float(body.get("amount")),
        reference=body.get("reference"),
        notes=body.get("notes"),
    )


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
def project_response(out: ProjectOutput) -> dict:
    """Project an Application ``ProjectOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "lifecycle_status": out.lifecycle_status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "project_code": out.project_code,
        "department": out.department,
        "grant_number": out.grant_number,
        "start_date": out.start_date,
        "end_date": out.end_date,
        "duration": out.duration,
        "budget_approved": out.budget_approved,
        "budget_utilized": out.budget_utilized,
        "objectives": out.objectives,
        "keywords": out.keywords,
        "abstract": out.abstract,
        "priority": out.priority,
        "notes": out.notes,
        "tags": out.tags,
        "progress_updates": out.progress_updates,
        "links": out.links,
        "team": out.team,
        "milestones": [
            {
                "id": m.id,
                "title": m.title,
                "date": m.date,
                "status": m.status,
                "notes": m.notes,
            }
            for m in out.milestones
        ],
        "budget": out.budget,
        "metadata": out.metadata,
        "events": out.events,
    }


def grant_response(out: GrantOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "grant_number": out.grant_number,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "amount": out.amount,
        "release_schedule": out.release_schedule,
        "notes": out.notes,
        "links": out.links,
        "installments": [installment_response(i) for i in out.installments],
        "expenditures": [expenditure_response(e) for e in out.expenditures],
        "budget": out.budget,
        "metadata": out.metadata,
        "events": out.events,
    }


def agency_response(out: AgencyOutput) -> dict:
    return {
        "id": out.id,
        "name": out.name,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "website": out.website,
        "scheme": out.scheme,
        "contact_person": out.contact_person,
        "contact_email": out.contact_email,
        "contact_phone": out.contact_phone,
        "address": out.address,
        "notes": out.notes,
        "metadata": out.metadata,
        "events": out.events,
    }


def milestone_response(out: MilestoneOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "date": out.date,
        "status": out.status,
        "notes": out.notes,
    }


def installment_response(out: InstallmentOutput) -> dict:
    return {
        "id": out.id,
        "installment_no": out.installment_no,
        "date": out.date,
        "amount": out.amount,
        "status": out.status,
        "notes": out.notes,
    }


def expenditure_response(out: ExpenditureOutput) -> dict:
    return {
        "id": out.id,
        "date": out.date,
        "head": out.head,
        "amount": out.amount,
        "reference": out.reference,
        "notes": out.notes,
    }


def dashboard_response(out: ResearchDashboardOutput) -> dict:
    return {
        "total_projects": out.total_projects,
        "active_projects": out.active_projects,
        "completed_projects": out.completed_projects,
        "total_grants": out.total_grants,
        "budget_approved": out.budget_approved,
        "budget_utilized": out.budget_utilized,
        "upcoming_deadlines": [
            {
                "milestone_id": d.milestone_id,
                "title": d.title,
                "date": d.date,
                "status": d.status,
                "project_id": d.project_id,
                "project_title": d.project_title,
            }
            for d in out.upcoming_deadlines
        ],
    }
