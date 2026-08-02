"""Use case: List Classes (paginated, dashboard filters + object lens).

Mirrors ``ListStudentsUseCase``. The ``object_id`` lens serves both
dashboards: classes a STUDENT is enrolled in (edge on the student), and
classes a FACULTY member teaches (TAUGHT_BY edge on the class) — both
resolved through the frozen interface.
"""
from __future__ import annotations

from app.application.dtos.teaching import ClassOutput, ListClassesResult
from app.application.queries.list_classes import ListClassesQuery
from app.application.use_cases.teaching.helpers import enrolled_students
from app.application.validators.teaching import assert_valid_list_classes_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _searchable_text(out: ClassOutput) -> str:
    return " ".join(
        [
            out.title,
            out.course_code or "",
            out.programme or "",
            out.session or "",
            out.section or "",
            " ".join(out.tags),
        ]
    ).casefold()


def _matches(out: ClassOutput, query: ListClassesQuery) -> bool:
    if query.semester is not None and out.semester != query.semester:
        return False
    if query.session and (out.session or "").casefold() != query.session.casefold():
        return False
    if query.status and out.status != query.status:
        return False
    if query.q:
        haystack = _searchable_text(out)
        tokens = [t for t in query.q.casefold().split() if t]
        if not all(token in haystack for token in tokens):
            return False
    return True


class ListClassesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListClassesQuery) -> ListClassesResult:
        assert_valid_list_classes_query(query)

        classes = self._repository.find_by_type(ObjectType.COURSE)

        if query.object_id is not None:
            target = str(query.object_id)
            target_obj = self._repository.get_by_id(query.object_id)
            # Student dashboard lens: follow the student's OWN ENROLLED_IN
            # edges (edge lives on the student). Faculty dashboard lens: the
            # TAUGHT_BY edge ON the class (class -> faculty). Both resolve
            # through the frozen interface.
            enrolled_class_ids: set[str] = set()
            if target_obj is not None and target_obj.object_type is ObjectType.STUDENT:
                enrolled_class_ids = {
                    str(oid) for oid in target_obj.related_ids(RelationshipKind.ENROLLED_IN)
                }
            classes = [
                cls
                for cls in classes
                if target in {str(r.target) for r in cls.relationships}
                or str(cls.id) in enrolled_class_ids
            ]

        outputs = [ClassOutput.from_domain(c, []) for c in classes]
        outputs = [out for out in outputs if _matches(out, query)]
        total_count = len(outputs)

        outputs.sort(key=lambda out: ((out.session or "￿"), out.title.casefold(), out.id))
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        all_ids = []
        for out in page_items:
            raw = next(c for c in classes if str(c.id) == out.id)
            all_ids.extend(r.target for r in raw.relationships)
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}

        items = []
        for out in page_items:
            items.append(
                ClassOutput.from_domain(
                    next(c for c in classes if str(c.id) == out.id),
                    [],
                    linked_by_id=linked_by_id,
                    student_count=len(enrolled_students(self._repository, out.id)),
                )
            )

        return ListClassesResult(
            items=items,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
