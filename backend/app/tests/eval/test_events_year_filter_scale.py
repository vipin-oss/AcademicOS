"""Scale budget for the P1 fix: year-filtered event listing must stay a
real SQL predicate (the indexed ``search_year`` column), not a full-table
load-then-filter in Python.

2026-09 audit follow-up. The pre-fix behaviour was measured at 6,000 rows:
~180ms and a full deserialization of every row, growing linearly with the
number of events regardless of how many match the filter — the exact
"will break at 10,000+ documents" failure mode the product vision calls
out. This test pins the fixed behaviour with a generous, CI-safe budget
(not a throughput claim — see ADR-049's SCALE_LAW convention) and, more
importantly, asserts the SQL predicate is actually narrowing the row set
returned by the database, not just filtering after the fact.
"""
from __future__ import annotations

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.metadata import Metadata, MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

#: CI-safe scale point (larger points are CI-optional per ADR-049's SCALE_LAW).
N_EVENTS = 6_000
#: Generous budget for the year-filtered query (find + count), measured
#: independently to run well under 50ms even on slow CI — the pre-fix
#: Python-filter path measured ~180ms at this same scale.
YEAR_FILTER_BUDGET_MS = 100.0


def _seed(session, repo, n: int) -> None:
    for i in range(n):
        year = str(2010 + (i % 16))
        ev = UniversalObject.create(
            ObjectType.EVENT, f"Event {i}", created_by="obj:user:scale-0001",
            status=ObjectStatus.ACTIVE, object_id=ObjectId(f"obj:event:scale{i:06d}"),
            metadata=Metadata(entries=(
                MetadataEntry("start_date", f"{year}-01-15", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
            )),
        )
        ev.pop_domain_events()
        repo.save(ev)
        if i % 1000 == 0:
            session.commit()
    session.commit()


def test_year_filtered_event_listing_is_sql_pushed_down_at_scale():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyObjectRepository(session)
    _seed(session, repo, N_EVENTS)

    t0 = time.time()
    total = repo.count(
        object_type=ObjectType.EVENT, owner_user_id="obj:user:scale-0001", search_year=2024,
    )
    page = repo.find(
        object_type=ObjectType.EVENT, owner_user_id="obj:user:scale-0001", search_year=2024,
        page=1, page_size=20, sort_by="title_ci", order="asc",
    )
    elapsed_ms = (time.time() - t0) * 1000

    # Correctness: 1 in 16 years matches, so ~375 of 6,000 events.
    assert total == N_EVENTS // 16
    assert len(page) == 20
    assert all(
        entry.value.startswith("2024")
        for obj in page
        for entry in obj.metadata.entries
        if entry.key == "start_date"
    )

    # Performance: the whole point of the fix. A regression back to the
    # full-load-then-filter path would blow this budget by ~2x at this
    # scale (measured ~180ms pre-fix vs ~7ms post-fix in the audit).
    assert elapsed_ms < YEAR_FILTER_BUDGET_MS, (
        f"year-filtered event listing took {elapsed_ms:.1f}ms at {N_EVENTS} rows "
        f"(budget {YEAR_FILTER_BUDGET_MS}ms) — likely regressed to the pre-fix "
        "full-table Python-filter path."
    )


def test_year_filtered_listing_never_loads_unmatched_rows():
    """A more direct proof than timing: the ORM query itself must carry a
    WHERE on search_year, so the database — not Python — does the
    narrowing. Verified by counting rows the raw SQL layer returns."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyObjectRepository(session)
    _seed(session, repo, 500)

    from sqlalchemy import select

    from app.infrastructure.db.models.object_model import ObjectModel

    stmt = repo._apply_object_filters(
        select(ObjectModel),
        object_type=ObjectType.EVENT,
        status=None,
        metadata_key=None,
        metadata_value=None,
        owner_user_id="obj:user:scale-0001",
        search_year=2024,
    )
    rows = session.execute(stmt).scalars().all()
    # 500 events across 16 years -> ~31 in 2024, never all 500.
    assert 0 < len(rows) < 500
    assert all(row.search_year == 2024 for row in rows)


def test_search_year_extraction_covers_publications_and_projects_too():
    """2026-09 audit follow-up (P1, extension): the same materialized
    search_year fast path now also covers Publications (year, a plain
    integer metadata value rather than a date string) and Research
    Projects (start_date, same shape as Events) — proving the column
    isn't event-specific plumbing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyObjectRepository(session)

    pub = UniversalObject.create(
        ObjectType.PUBLICATION, "A 2024 Paper", created_by="obj:user:scale-0001",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:publication:scale-y1"),
        metadata=Metadata(entries=(
            MetadataEntry("year", "2024", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        )),
    )
    pub.pop_domain_events()
    repo.save(pub)

    project = UniversalObject.create(
        ObjectType.RESEARCH_PROJECT, "A 2024 Project", created_by="obj:user:scale-0001",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:research_project:scale-y1"),
        metadata=Metadata(entries=(
            MetadataEntry("start_date", "2024-03-01", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        )),
    )
    project.pop_domain_events()
    repo.save(project)
    session.commit()

    pubs_2024 = repo.find(
        object_type=ObjectType.PUBLICATION, owner_user_id="obj:user:scale-0001", search_year=2024,
    )
    assert [str(o.id) for o in pubs_2024] == ["obj:publication:scale-y1"]
    pubs_2023 = repo.find(
        object_type=ObjectType.PUBLICATION, owner_user_id="obj:user:scale-0001", search_year=2023,
    )
    assert pubs_2023 == []

    projects_2024 = repo.find(
        object_type=ObjectType.RESEARCH_PROJECT, owner_user_id="obj:user:scale-0001", search_year=2024,
    )
    assert [str(o.id) for o in projects_2024] == ["obj:research_project:scale-y1"]
