"""Shared helpers for the Faculty use cases — the derived lenses (PART 3/4/5).

Every lens is computed from the frozen relationship graph, never stored:
research projects are the faculty's OWN LEADS/CO_LEADS/WORKS_IN edges, grants
are FUNDS edges onto those projects, supervision is the students' reverse
SUPERVISED_BY/ADVISED_BY edges, teaching is the classes' TAUGHT_BY edges, and
publications the AUTHORED_BY edges. All scans use the portable repository
interface (``find_by_type`` / ``find_by_ids``) — the frozen N+1 doctrine.
"""
from __future__ import annotations

import re

from app.application.dtos import student as student_dtos
from app.application.dtos import teaching as teaching_dtos
from app.application.dtos.research import link_dict, parse_json_object_list
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})")


def _slot_hours(slot: dict) -> float:
    """One weekly slot → hours (default 1h when times are missing/invalid)."""
    start, end = slot.get("start"), slot.get("end")
    start_match, end_match = _TIME_RE.match(str(start or "")), _TIME_RE.match(str(end or ""))
    if not start_match or not end_match:
        return 1.0
    minutes = (int(end_match.group(1)) * 60 + int(end_match.group(2))) - (
        int(start_match.group(1)) * 60 + int(start_match.group(2))
    )
    return round(max(0.0, minutes / 60), 2) or 1.0


def weekly_hours_of(raw_schedule: str | None) -> float:
    """Total weekly contact hours of a class from its JSON schedule."""
    slots = parse_json_object_list(raw_schedule)
    return round(sum(_slot_hours(slot) for slot in slots), 2)


def _as_int(raw: str | None) -> int | None:
    try:
        return None if raw is None or str(raw).strip() == "" else int(str(raw))
    except ValueError:
        return None


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def _sorted(ids: list[UniversalObject]) -> list[UniversalObject]:
    return sorted(ids, key=lambda item: (item.title.casefold(), str(item.id)))


def research_projects_of_faculty(
    repository: ObjectRepository, obj: UniversalObject
) -> tuple[list[dict], dict[str, UniversalObject]]:
    """The projects the faculty LEADS / CO_LEADS / WORKS_IN (edges on the faculty).

    Returns the denormalised entries AND the resolved project Objects (ONE
    ``find_by_ids`` batch) so callers can read lifecycle metadata without a
    second round trip.
    """
    entries: list[dict] = []
    kinds = (RelationshipKind.LEADS, RelationshipKind.CO_LEADS, RelationshipKind.WORKS_IN)
    targets: dict[str, UniversalObject] = {
        str(o.id): o
        for o in repository.find_by_ids(
            [rel.target for rel in obj.relationships if rel.kind in kinds]
        )
    }
    projects: dict[str, UniversalObject] = {}
    for rel in obj.relationships:
        if rel.kind not in kinds:
            continue
        target = targets.get(str(rel.target))
        if target is not None and target.object_type is ObjectType.RESEARCH_PROJECT:
            entries.append(link_dict(target, rel.kind))
            projects[str(target.id)] = target
    entries.sort(key=lambda entry: (entry["title"].casefold(), entry["id"]))
    return entries, projects


def grants_of_projects(
    repository: ObjectRepository, project_ids: set[str]
) -> list[dict]:
    """Grants FUNDS → any of the faculty's projects (reverse scan over grants)."""
    if not project_ids:
        return []
    entries: list[dict] = []
    for grant in repository.find_by_type(ObjectType.GRANT):
        if any(
            rel.kind is RelationshipKind.FUNDS and str(rel.target) in project_ids
            for rel in grant.relationships
        ):
            entries.append(link_dict(grant, RelationshipKind.FUNDS))
    entries.sort(key=lambda entry: (entry["title"].casefold(), entry["id"]))
    return entries


def supervision_of_faculty(
    repository: ObjectRepository, faculty_id: str
) -> dict[str, list[dict]]:
    """Students SUPERVISED_BY/ADVISED_BY → faculty; current (ug/pg/phd) vs alumni."""
    kinds = (RelationshipKind.SUPERVISED_BY, RelationshipKind.ADVISED_BY)
    current: list[dict] = []
    completed: list[dict] = []
    for student in repository.find_by_type(ObjectType.STUDENT):
        hits = [
            rel
            for rel in student.relationships
            if rel.kind in kinds and str(rel.target) == faculty_id
        ]
        if not hits:
            continue
        student_type = _meta(student).get(student_dtos.KEY_STUDENT_TYPE) or "ug"
        for rel in hits:
            entry = {**link_dict(student, rel.kind), "student_type": student_type}
            (completed if student_type == "alumni" else current).append(entry)
    current.sort(key=lambda entry: (entry["title"].casefold(), entry["id"]))
    completed.sort(key=lambda entry: (entry["title"].casefold(), entry["id"]))
    return {"current": current, "completed": completed}


def classes_of_faculty(
    repository: ObjectRepository, faculty_id: str
) -> tuple[list[dict], float]:
    """Classes TAUGHT_BY → faculty (edge on the class) + derived weekly hours."""
    entries: list[dict] = []
    total = 0.0
    for cls in repository.find_by_type(ObjectType.COURSE):
        if not any(
            rel.kind is RelationshipKind.TAUGHT_BY and str(rel.target) == faculty_id
            for rel in cls.relationships
        ):
            continue
        meta = _meta(cls)
        hours = weekly_hours_of(meta.get(teaching_dtos.KEY_WEEKLY_SCHEDULE))
        total += hours
        entries.append(
            {
                **link_dict(cls, RelationshipKind.TAUGHT_BY),
                "course_code": meta.get(teaching_dtos.KEY_COURSE_CODE),
                "programme": meta.get(teaching_dtos.KEY_PROGRAMME),
                "semester": _as_int(meta.get(teaching_dtos.KEY_SEMESTER)),
                "credits": _as_int(meta.get(teaching_dtos.KEY_CREDITS)),
                "weekly_hours": hours,
            }
        )
    entries.sort(
        key=lambda entry: (
            entry["semester"] if entry["semester"] is not None else 999,
            entry["title"].casefold(),
            entry["id"],
        )
    )
    return entries, round(total, 2)


def publications_count_of_faculty(repository: ObjectRepository, faculty_id: str) -> int:
    """Publications AUTHORED_BY → faculty (publications module edge)."""
    return sum(
        1
        for publication in repository.find_by_type(ObjectType.PUBLICATION)
        if any(
            rel.kind is RelationshipKind.AUTHORED_BY and str(rel.target) == faculty_id
            for rel in publication.relationships
        )
    )
