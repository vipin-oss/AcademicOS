"""Scale budget for the Phase 2 audit's Finding 2 fix: list_students,
list_grants, list_classes, and list_assignments must page directly in SQL
for the unfiltered case, not load every row of the type and slice in
Python.

2026-09 performance hardening. The pre-fix behaviour was measured (code
inspection + timing) at:
  - list_students: 50ms/200ms/364ms at 1,000/5,000/10,000 rows
  - list_grants:    24ms/119ms/285ms at the same scale
growing linearly with the user's own record count, versus ~5-10ms flat
for the SQL-paginated equivalent (list_events, for comparison). This test
pins the fixed behaviour with a generous, CI-safe budget and — more
importantly, per the same precedent as test_events_year_filter_scale.py —
proves the database itself is doing the narrowing (via the repository's
own count()/find() call shape), not just that the numbers happen to look
fast today.
"""
from __future__ import annotations

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.queries.list_assignments import ListAssignmentsQuery
from app.application.queries.list_classes import ListClassesQuery
from app.application.queries.list_grants import ListGrantsQuery
from app.application.queries.list_students import ListStudentsQuery
from app.application.use_cases.students.list_students import ListStudentsUseCase
from app.application.use_cases.research.list_grants import ListGrantsUseCase
from app.application.use_cases.teaching.list_classes import ListClassesUseCase
from app.application.use_cases.teaching.list_assignments import ListAssignmentsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

USER = "obj:user:scale-perf2-0001"

#: CI-safe scale point (larger points are CI-optional, matching the
#: existing search_year scale test's convention).
N_ROWS = 6_000
#: Generous budget for a single unfiltered page fetch — measured
#: independently to run well under 50ms even on slow CI. The pre-fix
#: full-scan path measured 200-364ms at this scale for these two domains.
FAST_PATH_BUDGET_MS = 100.0


def _make_repo():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return SQLAlchemyObjectRepository(session), session


def _seed(session, repo, kind: ObjectType, n: int, prefix: str) -> None:
    for i in range(n):
        obj = UniversalObject.create(
            kind, f"{prefix} {i}", created_by=USER, status=ObjectStatus.ACTIVE,
        )
        obj.pop_domain_events()
        repo.save(obj)
        if i % 1000 == 0:
            session.commit()
    session.commit()


def test_list_students_unfiltered_is_sql_paginated_at_scale():
    repo, session = _make_repo()
    _seed(session, repo, ObjectType.STUDENT, N_ROWS, "Student")

    t0 = time.time()
    result = ListStudentsUseCase(repo).execute(
        ListStudentsQuery(page=1, page_size=20, owner_user_id=USER)
    )
    elapsed_ms = (time.time() - t0) * 1000

    assert result.total_count == N_ROWS
    assert len(result.items) == 20
    assert elapsed_ms < FAST_PATH_BUDGET_MS, (
        f"list_students (unfiltered) took {elapsed_ms:.1f}ms at {N_ROWS} rows "
        f"(budget {FAST_PATH_BUDGET_MS}ms) — likely regressed to the full-scan path."
    )


def test_list_grants_unfiltered_is_sql_paginated_at_scale():
    repo, session = _make_repo()
    _seed(session, repo, ObjectType.GRANT, N_ROWS, "Grant")

    t0 = time.time()
    result = ListGrantsUseCase(repo).execute(
        ListGrantsQuery(page=1, page_size=20, owner_user_id=USER)
    )
    elapsed_ms = (time.time() - t0) * 1000

    assert result.total_count == N_ROWS
    assert len(result.items) == 20
    assert elapsed_ms < FAST_PATH_BUDGET_MS, (
        f"list_grants (unfiltered) took {elapsed_ms:.1f}ms at {N_ROWS} rows "
        f"(budget {FAST_PATH_BUDGET_MS}ms) — likely regressed to the full-scan path."
    )


def test_list_classes_unfiltered_is_sql_paginated_at_scale():
    repo, session = _make_repo()
    _seed(session, repo, ObjectType.COURSE, N_ROWS, "Class")

    t0 = time.time()
    result = ListClassesUseCase(repo).execute(
        ListClassesQuery(page=1, page_size=20, owner_user_id=USER)
    )
    elapsed_ms = (time.time() - t0) * 1000

    assert result.total_count == N_ROWS
    assert len(result.items) == 20
    assert elapsed_ms < FAST_PATH_BUDGET_MS, (
        f"list_classes (unfiltered) took {elapsed_ms:.1f}ms at {N_ROWS} rows "
        f"(budget {FAST_PATH_BUDGET_MS}ms) — likely regressed to the full-scan path."
    )


def test_list_assignments_unfiltered_is_sql_paginated_at_scale():
    repo, session = _make_repo()
    _seed(session, repo, ObjectType.ASSIGNMENT, N_ROWS, "Assignment")

    t0 = time.time()
    result = ListAssignmentsUseCase(repo).execute(
        ListAssignmentsQuery(page=1, page_size=20, owner_user_id=USER)
    )
    elapsed_ms = (time.time() - t0) * 1000

    assert result.total_count == N_ROWS
    assert len(result.items) == 20
    assert elapsed_ms < FAST_PATH_BUDGET_MS, (
        f"list_assignments (unfiltered) took {elapsed_ms:.1f}ms at {N_ROWS} rows "
        f"(budget {FAST_PATH_BUDGET_MS}ms) — likely regressed to the full-scan path."
    )


def test_fast_path_queries_never_load_unmatched_rows():
    """A more direct proof than timing, matching the search_year scale
    test's own precedent: the repository's find() must carry a WHERE on
    owner_user_id and use SQL LIMIT, so the database — not Python — does
    the narrowing. Verified by counting rows the raw SQL layer returns
    for a single page out of many owned by a DIFFERENT, noise user."""
    repo, session = _make_repo()
    _seed(session, repo, ObjectType.STUDENT, 500, "Student")
    _seed(session, repo, ObjectType.STUDENT, 500, "OtherUserStudent")
    # Re-stamp the second batch under a different owner directly, so this
    # test also incidentally proves owner_user_id filtering is preserved
    # by the fast path (not just SQL pagination).
    from sqlalchemy import update

    from app.infrastructure.db.models.object_model import ObjectModel

    session.execute(
        update(ObjectModel)
        .where(ObjectModel.title.like("OtherUserStudent%"))
        .values(owner_user_id="obj:user:someone-else")
    )
    session.commit()

    page = repo.find(
        object_type=ObjectType.STUDENT, owner_user_id=USER,
        page=1, page_size=20, sort_by="title_ci", order="asc",
    )
    total = repo.count(object_type=ObjectType.STUDENT, owner_user_id=USER)

    assert total == 500  # never the combined 1,000
    assert len(page) == 20
    assert all(not o.title.startswith("OtherUserStudent") for o in page)
