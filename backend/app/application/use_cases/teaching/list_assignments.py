"""Use case: List Assignments (paginated; class lens + filters).

Mirrors ``ListClassesUseCase``. ``object_id`` is the lens used by class
pages and objects (assignments of this Class); ``class_id`` is the strict
ownership filter the class workspace uses. Ordered by deadline (undated
last), then title — the order a faculty gradebook reads.
"""
from __future__ import annotations

from app.application.dtos.teaching import (
    ASSIGNMENT_TYPES,
    VISIBILITIES,
    AssignmentOutput,
    ListAssignmentsResult,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_assignments import ListAssignmentsQuery
from app.application.use_cases.teaching.helpers import class_id_of_assignment
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


def _validate(query: ListAssignmentsQuery) -> None:
    errors = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.assignment_type is not None and query.assignment_type not in ASSIGNMENT_TYPES:
        errors.append(f"assignment_type must be one of: {', '.join(ASSIGNMENT_TYPES)}.")
    if query.visibility is not None and query.visibility not in VISIBILITIES:
        errors.append(f"visibility must be one of: {', '.join(VISIBILITIES)}.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    if errors:
        raise ValidationError("; ".join(errors))


def _searchable(obj) -> str:
    meta = {entry.key: entry.value for entry in obj.metadata.entries}
    return " ".join(
        [obj.title, meta.get("description") or "", meta.get("instructions") or ""]
    ).casefold()


class ListAssignmentsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListAssignmentsQuery) -> ListAssignmentsResult:
        _validate(query)

        assignments = self._repository.find_by_type(ObjectType.ASSIGNMENT)
        wanted_class = str(query.class_id) if query.class_id is not None else None
        lens = str(query.object_id) if query.object_id is not None else None

        outputs = []
        for assignment in assignments:
            owner = class_id_of_assignment(assignment)
            if wanted_class is not None and owner != wanted_class:
                continue
            if lens is not None and lens not in {
                str(r.target) for r in assignment.relationships
            }:
                continue
            out = AssignmentOutput.from_domain(assignment, [])
            if query.assignment_type and out.assignment_type != query.assignment_type:
                continue
            if query.visibility and out.visibility != query.visibility:
                continue
            if query.status and out.status != query.status:
                continue
            if query.q:
                tokens = [t for t in query.q.casefold().split() if t]
                if not all(token in _searchable(assignment) for token in tokens):
                    continue
            outputs.append(out)

        total_count = len(outputs)
        outputs.sort(key=lambda out: (out.deadline or "￿", out.title.casefold(), out.id))
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        # Denormalise owning-class titles in ONE batch call (no N+1).
        class_ids = {
            out.class_id for out in page_items if out.class_id
        }
        class_by_id = {
            str(c.id): c
            for c in self._repository.find_by_ids([ObjectId(cid) for cid in class_ids])
        }
        items = [
            AssignmentOutput.from_domain(
                next(a for a in assignments if str(a.id) == out.id),
                [],
                class_obj=class_by_id.get(out.class_id),
            )
            for out in page_items
        ]
        return ListAssignmentsResult(
            items=items, total_count=total_count, page=query.page, page_size=query.page_size
        )
