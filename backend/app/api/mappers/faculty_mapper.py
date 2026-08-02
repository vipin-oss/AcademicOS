"""Wire <-> boundary mapping for the Faculty API (mirrors research_mapper).

Translates request dictionaries into input DTOs and output DTOs into
response dictionaries; the frozen `uploaded_by` -> `created_by` rename
happens here and only here.
"""
from __future__ import annotations

from app.application.dtos.faculty import (
    CreateFacultyInput,
    FacultyOutput,
    UpdateFacultyInput,
)
from app.domain.value_objects.enums import ObjectStatus


def _str_list(value: object) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _section(value: object) -> list[dict]:
    return [item for item in (value or []) if isinstance(item, dict)]


def _committees(body: dict) -> list[str]:
    links = body.get("links") or {}
    return _str_list(links.get("committees"))


def to_create_faculty_input(*, body: dict) -> CreateFacultyInput:
    return CreateFacultyInput(
        name=str(body.get("name") or ""),
        employee_id=str(body.get("employee_id") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        faculty_code=body.get("faculty_code"),
        designation=body.get("designation"),
        department=body.get("department"),
        school=body.get("school"),
        joining_date=body.get("joining_date"),
        employment_type=body.get("employment_type"),
        email=body.get("email"),
        mobile=body.get("mobile"),
        office=body.get("office"),
        qualification=body.get("qualification"),
        specialization=body.get("specialization"),
        research_interests=_str_list(body.get("research_interests")),
        biography=body.get("biography"),
        orcid=body.get("orcid"),
        scopus_id=body.get("scopus_id"),
        google_scholar=body.get("google_scholar"),
        researchgate=body.get("researchgate"),
        website=body.get("website"),
        notes=body.get("notes"),
        tags=_str_list(body.get("tags")),
        degrees=_section(body.get("degrees")),
        experience=_section(body.get("experience")),
        awards=_section(body.get("awards")),
        memberships=_section(body.get("memberships")),
        certifications=_section(body.get("certifications")),
        admin_positions=_section(body.get("admin_positions")),
        committees=_committees(body),
    )


def to_update_faculty_input(*, body: dict) -> UpdateFacultyInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateFacultyInput(
        actor=str(body.get("uploaded_by") or "system"),
        name=present("name"),
        employee_id=present("employee_id"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        faculty_code=present("faculty_code"),
        designation=present("designation"),
        department=present("department"),
        school=present("school"),
        joining_date=present("joining_date"),
        employment_type=present("employment_type"),
        email=present("email"),
        mobile=present("mobile"),
        office=present("office"),
        qualification=present("qualification"),
        specialization=present("specialization"),
        research_interests=(
            _str_list(body["research_interests"]) if "research_interests" in body else None
        ),
        biography=present("biography"),
        orcid=present("orcid"),
        scopus_id=present("scopus_id"),
        google_scholar=present("google_scholar"),
        researchgate=present("researchgate"),
        website=present("website"),
        notes=present("notes"),
        tags=_str_list(body["tags"]) if "tags" in body else None,
        degrees=_section(body["degrees"]) if "degrees" in body else None,
        experience=_section(body["experience"]) if "experience" in body else None,
        awards=_section(body["awards"]) if "awards" in body else None,
        memberships=_section(body["memberships"]) if "memberships" in body else None,
        certifications=_section(body["certifications"]) if "certifications" in body else None,
        admin_positions=(
            _section(body["admin_positions"]) if "admin_positions" in body else None
        ),
        committees=_committees(body) if "links" in body else None,
    )


def faculty_response(out: FacultyOutput, *, photo_url: str | None = None) -> dict:
    """The wire shape (uploaded_by renamed from created_by — frozen idiom)."""
    return {
        "id": out.id,
        "name": out.name,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "employee_id": out.employee_id,
        "faculty_code": out.faculty_code,
        "designation": out.designation,
        "department": out.department,
        "school": out.school,
        "joining_date": out.joining_date,
        "employment_type": out.employment_type,
        "email": out.email,
        "mobile": out.mobile,
        "office": out.office,
        "qualification": out.qualification,
        "specialization": out.specialization,
        "research_interests": list(out.research_interests),
        "biography": out.biography,
        "orcid": out.orcid,
        "scopus_id": out.scopus_id,
        "google_scholar": out.google_scholar,
        "researchgate": out.researchgate,
        "website": out.website,
        "notes": out.notes,
        "tags": list(out.tags),
        "degrees": list(out.degrees),
        "experience": list(out.experience),
        "awards": list(out.awards),
        "memberships": list(out.memberships),
        "certifications": list(out.certifications),
        "admin_positions": list(out.admin_positions),
        "photo_file_name": out.photo_file_name,
        "photo_file_size": out.photo_file_size,
        "photo_mime_type": out.photo_mime_type,
        "photo_url": photo_url,
        "links": out.links,
        "research": out.research,
        "supervision": out.supervision,
        "teaching": out.teaching,
        "stats": out.stats,
        "metadata": dict(out.metadata),
        "events": list(out.events),
    }
