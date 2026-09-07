"""Query-count regression tests for the Phase 2B N+1 completion sweep.

2026-09 performance hardening, second pass. Timing-based assertions are
fragile across machines (per the audit's own instruction to prefer
"query count, bounded complexity, database-level behavior, generous
environment-independent thresholds" over wall-clock budgets) — these
tests instead count actual SQL SELECT statements issued against the
``objects`` table via a SQLAlchemy event hook, proving the fix is
structural (bounded, not scaling with the number of items in the loop),
not just fast today on this machine.

Covers the two nested N+1 chains the Phase 2B sweep found and fixed:
  - list_classes / enrolled_students (one STUDENT scan per class)
  - list_budget_lines / project_budget (one GRANT scan per project, and
    one GRANT_INSTALLMENT + GRANT_EXPENDITURE scan per grant within that)
  - get_committees_dashboard (one MEETING scan per committee, and one
    TASK scan per meeting within that)
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.application.queries.get_committees_dashboard import GetCommitteesDashboardQuery
from app.application.queries.list_budget_lines import ListBudgetLinesQuery
from app.application.queries.list_classes import ListClassesQuery
from app.application.use_cases.committees.get_committees_dashboard import (
    GetCommitteesDashboardUseCase,
)
from app.application.use_cases.finance.list_budget_lines import ListBudgetLinesUseCase
from app.application.use_cases.teaching.list_classes import ListClassesUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

USER = "obj:user:n1-regression-0001"


def _make_repo_with_query_log():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    query_log: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _log(conn, cursor, statement, parameters, context, executemany):
        if "SELECT" in statement.upper() and "objects" in statement:
            query_log.append(statement)

    return SQLAlchemyObjectRepository(session), session, query_log


def _seed(session, repo, kind: ObjectType, n: int, prefix: str, owner: str = USER) -> None:
    for i in range(n):
        obj = UniversalObject.create(kind, f"{prefix} {i}", created_by=owner, status=ObjectStatus.ACTIVE)
        obj.pop_domain_events()
        repo.save(obj)
    session.commit()


def test_list_classes_query_count_does_not_scale_with_page_size():
    """One STUDENT scan for the whole page, not one per class — the exact
    N+1 the sweep found in both list_classes fast and slow paths."""
    repo, session, query_log = _make_repo_with_query_log()
    _seed(session, repo, ObjectType.COURSE, 20, "Class")
    _seed(session, repo, ObjectType.STUDENT, 50, "Student")

    query_log.clear()
    result = ListClassesUseCase(repo).execute(
        ListClassesQuery(page=1, page_size=20, owner_user_id=USER)
    )
    assert len(result.items) == 20
    # 1 count + 1 find (classes) + 1 find_by_ids (links) + 1 find (students)
    # = 4, regardless of how many classes are on the page. The pre-fix
    # shape was 3 + 20 (one STUDENT scan per class).
    assert len(query_log) <= 5, (
        f"list_classes issued {len(query_log)} SELECTs for a 20-class page "
        "— expected a small, page-size-independent count; the per-class "
        "enrolled_students() N+1 may have regressed."
    )


def test_list_budget_lines_query_count_does_not_scale_with_project_count():
    """One scan each of PROJECT/PURCHASE/GRANT/GRANT_INSTALLMENT/
    GRANT_EXPENDITURE, not one GRANT(+children) scan per project — the
    doubly nested N+1 the sweep found inside project_budget()."""
    repo, session, query_log = _make_repo_with_query_log()
    _seed(session, repo, ObjectType.RESEARCH_PROJECT, 15, "Project")
    _seed(session, repo, ObjectType.PURCHASE, 30, "Proposal")
    _seed(session, repo, ObjectType.GRANT, 10, "Grant")

    query_log.clear()
    result = ListBudgetLinesUseCase(repo).execute(
        ListBudgetLinesQuery(owner_user_id=USER)
    )
    assert len(result.items) == 15
    # 1 (projects) + 1 (proposals) + 1 (grants) + 1 (installments) +
    # 1 (expenditures) = 5, regardless of project count. The pre-fix
    # shape was 2 + 15 (one GRANT scan per project, before installments/
    # expenditures were even reached).
    assert len(query_log) <= 6, (
        f"list_budget_lines issued {len(query_log)} SELECTs for 15 projects "
        "— expected a small, project-count-independent count; the nested "
        "grants/installments/expenditures N+1 may have regressed."
    )


def test_committees_dashboard_query_count_does_not_scale_with_committee_count():
    """One scan each of COMMITTEE/MEETING/TASK, not one MEETING scan per
    committee (and one TASK scan per meeting within that) — the triply
    nested N+1 the sweep found here."""
    repo, session, query_log = _make_repo_with_query_log()
    _seed(session, repo, ObjectType.COMMITTEE, 20, "Committee")

    query_log.clear()
    result = GetCommitteesDashboardUseCase(repo).execute(
        GetCommitteesDashboardQuery(owner_user_id=USER)
    )
    assert result.total_committees == 20
    # 1 (committees) + 1 (meetings) + 1 (tasks) = 3, regardless of
    # committee count. The pre-fix shape was 1 + 20 (one MEETING scan per
    # committee), before any per-meeting TASK scan was even reached.
    assert len(query_log) <= 4, (
        f"committees dashboard issued {len(query_log)} SELECTs for 20 "
        "committees — expected a small, committee-count-independent "
        "count; the nested meetings/tasks N+1 may have regressed."
    )
