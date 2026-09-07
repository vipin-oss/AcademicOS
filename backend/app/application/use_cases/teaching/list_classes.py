"""Use case: List Classes (paginated, dashboard filters + object lens).

Mirrors ``ListStudentsUseCase``. The ``object_id`` lens serves both
dashboards: classes a STUDENT is enrolled in (edge on the student), and
classes a FACULTY member teaches (TAUGHT_BY edge on the class) — both
resolved through the frozen interface.
"""
from __future__ import annotations

from app.application.dtos.teaching import ClassOutput, ListClassesResult
from app.application.queries.list_classes import ListClassesQuery
from app.application.use_cases.teaching.helpers import enrolled_students, students_by_class
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

        # Perf hardening (Phase 2 audit follow-up): an unfiltered listing
        # pages directly in SQL instead of loading every COURSE row. The
        # slow path below is preserved for semester/session/status/q and
        # the student/faculty dashboard object_id lens. Ordering note:
        # session isn't a first-class SQL column, so this fast path orders
        # by title (title_ci) instead of (session, title, id).
        plain = (
            query.semester is None
            and query.session is None
            and query.status is None
            and not (query.q or "").strip()
            and query.object_id is None
        )
        if plain:
            total_count = self._repository.count(
                object_type=ObjectType.COURSE, owner_user_id=query.owner_user_id
            )
            page = self._repository.find(
                object_type=ObjectType.COURSE,
                owner_user_id=query.owner_user_id,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            all_ids = []
            for cls in page:
                all_ids.extend(r.target for r in cls.relationships)
            linked_by_id = {
                str(o.id): o
                for o in self._repository.find_by_ids(all_ids, owner_user_id=query.owner_user_id)
            }
            # Perf hardening (Phase 2B audit follow-up): one STUDENT scan
            # grouped by class, instead of one full unscoped STUDENT-table
            # scan per class on the page (enrolled_students() called once
            # per item — the N+1 the sweep found in this exact file).
            roster_by_class = students_by_class(
                self._repository, [str(cls.id) for cls in page], owner_user_id=query.owner_user_id
            )
            items = [
                ClassOutput.from_domain(
                    cls, [], linked_by_id=linked_by_id,
                    student_count=len(roster_by_class.get(str(cls.id), [])),
                )
                for cls in page
            ]
            return ListClassesResult(
                items=items, total_count=total_count, page=query.page, page_size=query.page_size
            )

        classes = self._repository.find_by_type(
            ObjectType.COURSE, owner_user_id=query.owner_user_id
        )

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
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids, owner_user_id=query.owner_user_id)}
        # Perf hardening (Phase 2B audit follow-up): same fix as the plain
        # path above — one grouped STUDENT scan instead of one per class.
        roster_by_class = students_by_class(
            self._repository, [out.id for out in page_items], owner_user_id=query.owner_user_id
        )

        items = []
        for out in page_items:
            items.append(
                ClassOutput.from_domain(
                    next(c for c in classes if str(c.id) == out.id),
                    [],
                    linked_by_id=linked_by_id,
                    student_count=len(roster_by_class.get(out.id, [])),
                )
            )

        return ListClassesResult(
            items=items,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
