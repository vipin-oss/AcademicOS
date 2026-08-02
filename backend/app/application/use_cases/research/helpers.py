"""Shared builders for the Research use cases (single implementation doctrine,
like ``use_cases/teaching/helpers.py``).

Everything here is portable across engines: scans run in Python over the
frozen ``find_by_type`` interface — identical on PostgreSQL, SQLite and the
in-memory test repository (no JSONB / vendor SQL).
"""
from __future__ import annotations

from app.application.dtos.research import (
    KEY_AMOUNT,
    KEY_BUDGET_APPROVED,
    KEY_BUDGET_UTILIZED,
    KEY_EXPENDITURE_DATE,
    KEY_EXPENDITURE_HEAD,
    KEY_EXPENDITURE_REFERENCE,
    KEY_INSTALLMENT_DATE,
    KEY_INSTALLMENT_NO,
    KEY_INSTALLMENT_STATUS,
    KEY_MILESTONE_DATE,
    KEY_MILESTONE_STATUS,
    KEY_NOTES,
    TEAM_GROUP_TO_KIND,
    ExpenditureOutput,
    InstallmentOutput,
    MilestoneOutput,
    link_dict,
    parse_amount,
    team_edge_group,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, Provenance, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


def people(repository: ObjectRepository) -> list[UniversalObject]:
    """All team-eligible Objects (faculty + students) in one pass each."""
    return repository.find_by_type(ObjectType.FACULTY) + repository.find_by_type(
        ObjectType.STUDENT
    )


def team_edges_of_project(
    repository: ObjectRepository, project_id: str
) -> list[tuple[UniversalObject, RelationshipKind]]:
    """Reverse scan: (person, kind) whose outgoing edge targets this project.

    Mirrors ``enrolled_students`` (teaching): enrollment/team edges live on
    the person aggregate, so the project view is a reverse scan.
    """
    members: list[tuple[UniversalObject, RelationshipKind]] = []
    for person in people(repository):
        # One person can legitimately hold several team roles at once
        # (e.g. Co-PI and working member) — classify every matching edge.
        for rel in person.relationships:
            if str(rel.target) == project_id and team_edge_group(
                rel.kind, person.object_type
            ):
                members.append((person, rel.kind))
    return members


def deflated_team(
    repository: ObjectRepository, project_id: str
) -> dict[str, list[dict]]:
    """Denormalised team payload grouped for the project response."""
    team: dict[str, list[dict]] = {group: [] for group in TEAM_GROUP_TO_KIND}
    for person, kind in team_edges_of_project(repository, project_id):
        group = team_edge_group(kind, person.object_type)
        if group is not None:
            team[group].append(link_dict(person, kind))
    for group in team:
        team[group].sort(key=lambda item: item["title"].casefold())
    return team


def team_names_of_project(repository: ObjectRepository, project_id: str) -> str:
    """Search haystack of every team member's name (the PART 9 PI filter)."""
    return " ".join(person.title for person, _ in team_edges_of_project(repository, project_id))


def replace_team_group(
    repository: ObjectRepository,
    project: UniversalObject,
    group: str,
    target_ids: list[ObjectId] | tuple[ObjectId, ...],
    *,
    actor: str,
) -> list[UniversalObject]:
    """Replace one team group (PI / Co-PI / members) — merge semantics: the
    present group is rewritten, absent groups are never touched.

    Edges live on the person aggregates (LEADS / CO_LEADS / WORKS_IN →
    project); updating a group removes that kind's edges pointing at the
    project from every person and asserts the new set — the multi-aggregate
    ``enroll_students`` precedent. Every mutated aggregate is saved.
    """
    kind = TEAM_GROUP_TO_KIND[group]
    project_id = str(project.id)

    for person in people(repository):
        if any(
            str(rel.target) == project_id and rel.kind is kind
            for rel in person.relationships
        ):
            person.remove_relationship(project.id, kind, actor=actor)
            repository.save(person)

    changed: list[UniversalObject] = []
    for target_id in target_ids:
        person = repository.get_by_id(target_id)
        if person is None:
            continue  # existence is validated by the caller (ValidationError)
        person.add_relationship(project.id, kind, Provenance.ASSERTED, actor=actor)
        repository.save(person)
        changed.append(person)
    return changed


def milestones_of_project(
    repository: ObjectRepository, project_id: str
) -> list[UniversalObject]:
    """Milestone children (BELONGS_TO → project), date order."""
    milestones = [
        obj
        for obj in repository.find_by_type(ObjectType.PROJECT_MILESTONE)
        if any(rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) == project_id
               for rel in obj.relationships)
    ]
    milestones.sort(key=lambda m: ((m.metadata.get_value(KEY_MILESTONE_DATE) or "￿"), str(m.id)))
    return milestones


def milestone_output(obj: UniversalObject) -> MilestoneOutput:
    meta = {entry.key: entry.value for entry in obj.metadata.entries}
    return MilestoneOutput(
        id=str(obj.id),
        title=obj.title,
        date=meta.get(KEY_MILESTONE_DATE),
        status=meta.get(KEY_MILESTONE_STATUS) or "pending",
        notes=meta.get(KEY_NOTES),
    )


def installments_of_grant(
    repository: ObjectRepository, grant_id: str
) -> list[UniversalObject]:
    """Installment children (BELONGS_TO → grant), installment-number order."""
    def no(obj: UniversalObject) -> tuple[int, str]:
        try:
            return (int(obj.metadata.get_value(KEY_INSTALLMENT_NO) or "0"), str(obj.id))
        except ValueError:
            return (0, str(obj.id))

    children = [
        obj
        for obj in repository.find_by_type(ObjectType.GRANT_INSTALLMENT)
        if any(rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) == grant_id
               for rel in obj.relationships)
    ]
    children.sort(key=no)
    return children


def installment_output(obj: UniversalObject) -> InstallmentOutput:
    meta = {entry.key: entry.value for entry in obj.metadata.entries}
    raw_no = meta.get(KEY_INSTALLMENT_NO)
    try:
        number = int(raw_no) if raw_no not in (None, "") else None
    except ValueError:
        number = None
    return InstallmentOutput(
        id=str(obj.id),
        installment_no=number,
        date=meta.get(KEY_INSTALLMENT_DATE),
        amount=parse_amount(meta.get(KEY_AMOUNT)),
        status=meta.get(KEY_INSTALLMENT_STATUS) or "released",
        notes=meta.get(KEY_NOTES),
    )


def expenditures_of_grant(
    repository: ObjectRepository, grant_id: str
) -> list[UniversalObject]:
    """Expenditure children (BELONGS_TO → grant), date order."""
    children = [
        obj
        for obj in repository.find_by_type(ObjectType.GRANT_EXPENDITURE)
        if any(rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) == grant_id
               for rel in obj.relationships)
    ]
    children.sort(key=lambda e: ((e.metadata.get_value(KEY_EXPENDITURE_DATE) or "￿"), str(e.id)))
    return children


def expenditure_output(obj: UniversalObject) -> ExpenditureOutput:
    meta = {entry.key: entry.value for entry in obj.metadata.entries}
    return ExpenditureOutput(
        id=str(obj.id),
        date=meta.get(KEY_EXPENDITURE_DATE),
        head=meta.get(KEY_EXPENDITURE_HEAD),
        amount=parse_amount(meta.get(KEY_AMOUNT)),
        reference=meta.get(KEY_EXPENDITURE_REFERENCE),
        notes=meta.get(KEY_NOTES),
    )


def grant_totals(
    repository: ObjectRepository, grant: UniversalObject
) -> dict[str, float | None]:
    """The simple MVP budget view (PART 7): approved / released / utilized /
    remaining — computed from the installment & expenditure children, never
    stored redundantly.
    """
    approved = parse_amount(grant.metadata.get_value(KEY_AMOUNT))
    grant_id = str(grant.id)
    released = 0.0
    for inst in installments_of_grant(repository, grant_id):
        if (inst.metadata.get_value(KEY_INSTALLMENT_STATUS) or "released") == "released":
            released += parse_amount(inst.metadata.get_value(KEY_AMOUNT)) or 0.0
    utilized = 0.0
    for exp in expenditures_of_grant(repository, grant_id):
        utilized += parse_amount(exp.metadata.get_value(KEY_AMOUNT)) or 0.0
    remaining = (approved - utilized) if approved is not None else None
    return {
        "approved": approved,
        "released": round(released, 2),
        "utilized": round(utilized, 2),
        "remaining": round(remaining, 2) if remaining is not None else None,
    }


def grants_of_project(
    repository: ObjectRepository, project_id: str
) -> list[UniversalObject]:
    """Grant Objects funding a project (FUNDS → project edge on the grant)."""
    grants = [
        obj
        for obj in repository.find_by_type(ObjectType.GRANT)
        if any(rel.kind is RelationshipKind.FUNDS and str(rel.target) == project_id
               for rel in obj.relationships)
    ]
    grants.sort(key=lambda g: (g.title.casefold(), str(g.id)))
    return grants


def project_budget(repository: ObjectRepository, project: UniversalObject) -> dict:
    """Project-level MVP budget (PART 7): approved / utilized ride on the
    project record; ``grants_released`` is the sum of released installments
    across the project's grant objects; remaining is derived.
    """
    approved = parse_amount(project.metadata.get_value(KEY_BUDGET_APPROVED))
    utilized = parse_amount(project.metadata.get_value(KEY_BUDGET_UTILIZED))
    released = 0.0
    seen = False
    for grant in grants_of_project(repository, str(project.id)):
        totals = grant_totals(repository, grant)
        if totals["released"]:
            released += totals["released"] or 0.0
            seen = True
    remaining = (approved - utilized) if approved is not None and utilized is not None else None
    return {
        "approved": approved,
        "utilized": utilized,
        "remaining": round(remaining, 2) if remaining is not None else None,
        "grants_released": round(released, 2) if seen else None,
    }
