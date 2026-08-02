"""Use case: List Students (paginated, manager filters).

Mirrors ``ListPublicationsUseCase``: pagination in the Application layer over
repository results (frozen interface), stable id ordering, ONE ``find_by_ids``
batch for link denormalisation (no N+1). Filters power both the UI and the
object lens (``object_id`` = students linked to that Object, e.g. scholars of
one supervisor).
"""
from __future__ import annotations

from app.application.dtos.student import (
    ListStudentsResult,
    StudentOutput,
    linked_target_ids,
)
from app.application.queries.list_students import ListStudentsQuery
from app.application.validators.student import assert_valid_list_students_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _searchable_text(out: StudentOutput) -> str:
    return " ".join(
        [
            out.name,
            out.roll_number or "",
            out.registration_number or "",
            out.university_enrollment or "",
            out.email or "",
            out.programme or "",
            out.department or "",
            out.batch or "",
            " ".join(out.tags),
        ]
    ).casefold()


def _matches(out: StudentOutput, query: ListStudentsQuery) -> bool:
    if query.student_type and out.student_type != query.student_type:
        return False
    if query.programme and (out.programme or "").casefold() != query.programme.casefold():
        return False
    if query.semester is not None and out.semester != query.semester:
        return False
    if query.section and (out.section or "").casefold() != query.section.casefold():
        return False
    if query.status and out.status != query.status:
        return False
    if query.q:
        haystack = _searchable_text(out)
        tokens = [t for t in query.q.casefold().split() if t]
        if not all(token in haystack for token in tokens):
            return False
    return True


class ListStudentsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListStudentsQuery) -> ListStudentsResult:
        assert_valid_list_students_query(query)

        students = self._repository.find_by_type(ObjectType.STUDENT)

        if query.object_id is not None:
            target = str(query.object_id)
            students = [
                student
                for student in students
                if target in {str(oid) for oid in linked_target_ids(student)}
            ]

        outputs = [StudentOutput.from_domain(s, []) for s in students]
        outputs = [out for out in outputs if _matches(out, query)]

        total_count = len(outputs)

        # Default ordering: roll number, then name, then id (registry reading
        # order; stable and deterministic like the objects list).
        outputs.sort(
            key=lambda out: (out.roll_number or "￿", out.name.casefold(), out.id)
        )
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        # Batch-resolve linked objects for the page slice only (no N+1).
        all_ids = []
        for out in page_items:
            raw = next(s for s in students if str(s.id) == out.id)
            all_ids.extend(linked_target_ids(raw))
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        items = []
        for out in page_items:
            raw = next(s for s in students if str(s.id) == out.id)
            items.append(StudentOutput.from_domain(raw, [], linked_by_id=linked_by_id))

        return ListStudentsResult(
            items=items,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
