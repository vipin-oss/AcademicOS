"""Pure mapping between Student API shapes and Application DTOs.

Mirrors ``publication_mapper.py``: framework-free so it stays unit-testable
without FastAPI/Pydantic/SQLAlchemy.
"""
from __future__ import annotations

from app.application.dtos.student import (
    GROUP_TO_KIND,
    LINK_GROUPS,
    CreateStudentInput,
    StudentOutput,
    UpdateStudentInput,
)
from app.domain.value_objects.enums import ObjectStatus
from app.domain.value_objects.object_id import ObjectId


def parse_links_field(raw: dict | None) -> dict[str, tuple[ObjectId, ...]] | None:
    """Parse {group: [object_id, ...]} into typed ObjectId tuples."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"links must be an object of {{{', '.join(LINK_GROUPS)}: [ids]}}.")
    links: dict[str, tuple[ObjectId, ...]] = {}
    for group, ids in raw.items():
        if group not in GROUP_TO_KIND:
            raise ValueError(
                f"Unknown link group: {group!r} (expected one of {', '.join(LINK_GROUPS)})."
            )
        if not isinstance(ids, list):
            raise ValueError(f"links.{group} must be an array of Object ids.")
        links[group] = tuple(ObjectId.parse(str(oid)) for oid in ids)
    return links


def to_create_input(*, body: dict) -> CreateStudentInput:
    """Convert the JSON create body into the Application ``CreateStudentInput``."""
    return CreateStudentInput(
        name=str(body.get("name") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        student_type=str(body.get("student_type") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        roll_number=body.get("roll_number"),
        registration_number=body.get("registration_number"),
        university_enrollment=body.get("university_enrollment"),
        email=body.get("email"),
        phone=body.get("phone"),
        programme=body.get("programme"),
        department=body.get("department"),
        semester=body.get("semester"),
        section=body.get("section"),
        batch=body.get("batch"),
        admission_date=body.get("admission_date"),
        expected_graduation=body.get("expected_graduation"),
        research_area=body.get("research_area"),
        orcid=body.get("orcid"),
        google_scholar=body.get("google_scholar"),
        notes=body.get("notes"),
        tags=tuple(str(t) for t in (body.get("tags") or [])),
        links=parse_links_field(body.get("links")),
    )


def to_update_input(*, body: dict) -> UpdateStudentInput:
    """Convert the JSON PUT/PATCH body into the Application ``UpdateStudentInput``.

    Merge semantics (frozen contract): an absent key leaves the field
    untouched; a present key replaces the stored value.
    """
    def present(name: str):
        return body[name] if name in body else None

    return UpdateStudentInput(
        actor=str(body.get("uploaded_by") or "system"),
        name=present("name"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        student_type=present("student_type"),
        roll_number=present("roll_number"),
        registration_number=present("registration_number"),
        university_enrollment=present("university_enrollment"),
        email=present("email"),
        phone=present("phone"),
        programme=present("programme"),
        department=present("department"),
        semester=present("semester"),
        section=present("section"),
        batch=present("batch"),
        admission_date=present("admission_date"),
        expected_graduation=present("expected_graduation"),
        research_area=present("research_area"),
        orcid=present("orcid"),
        google_scholar=present("google_scholar"),
        notes=present("notes"),
        tags=(tuple(str(t) for t in body["tags"]) if "tags" in body else None),
        links=parse_links_field(body["links"]) if "links" in body else None,
    )


def to_response(out: StudentOutput) -> dict:
    """Project an Application ``StudentOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "name": out.name,
        "student_type": out.student_type,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "roll_number": out.roll_number,
        "registration_number": out.registration_number,
        "university_enrollment": out.university_enrollment,
        "email": out.email,
        "phone": out.phone,
        "programme": out.programme,
        "department": out.department,
        "semester": out.semester,
        "section": out.section,
        "batch": out.batch,
        "admission_date": out.admission_date,
        "expected_graduation": out.expected_graduation,
        "research_area": out.research_area,
        "orcid": out.orcid,
        "google_scholar": out.google_scholar,
        "notes": out.notes,
        "tags": out.tags,
        "links": out.links,
        "metadata": out.metadata,
        "events": out.events,
    }
