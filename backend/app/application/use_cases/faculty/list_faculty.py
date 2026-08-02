"""Use case: List the Faculty directory (paginated, PART 7 search + filters).

Mirrors ``ListStudentsUseCase``: filters evaluated in Python over repository
results (frozen interface), deterministic registry ordering (name, then id),
own-metadata haystack — zero extra repository reads for the search text.
"""
from __future__ import annotations

from app.application.dtos.faculty import FacultyOutput, ListFacultyResult
from app.application.queries.list_faculty import ListFacultyQuery
from app.application.validators.faculty import assert_valid_list_faculty_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _searchable_text(out: FacultyOutput) -> str:
    return " ".join(
        [
            out.name,
            out.employee_id or "",
            out.faculty_code or "",
            out.designation or "",
            out.department or "",
            out.school or "",
            out.qualification or "",
            out.specialization or "",
            " ".join(out.research_interests),
            out.email or "",
            " ".join(out.tags),
        ]
    ).casefold()


class ListFacultyUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListFacultyQuery) -> ListFacultyResult:
        assert_valid_list_faculty_query(query)

        rows = [
            FacultyOutput.from_domain(obj, [])
            for obj in self._repository.find_by_type(ObjectType.FACULTY)
        ]

        def matches(out: FacultyOutput) -> bool:
            if query.status and out.status != query.status:
                return False
            if query.department and (out.department or "").casefold() != query.department.casefold():
                return False
            if query.designation and (out.designation or "").casefold() != query.designation.casefold():
                return False
            if query.employment_type and (out.employment_type or "") != query.employment_type:
                return False
            if query.q and query.q.strip():
                haystack = _searchable_text(out)
                tokens = [t for t in query.q.casefold().split() if t]
                if not all(token in haystack for token in tokens):
                    return False
            return True

        rows = [row for row in rows if matches(row)]
        total_count = len(rows)

        rows.sort(key=lambda row: (row.name.casefold(), row.id))
        start = (query.page - 1) * query.page_size
        page_rows = rows[start:start + query.page_size]

        return ListFacultyResult(
            items=page_rows,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
