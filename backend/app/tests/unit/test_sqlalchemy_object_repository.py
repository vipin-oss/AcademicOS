"""Unit tests for the SQLAlchemyObjectRepository adapter.

Uses PostgreSQL-compatible models (the ``objects`` table emits JSONB on
PostgreSQL). The engine is configurable via ``TEST_DATABASE_URL``; when unset, an
in-memory SQLite database is used so the tests run offline (JSONB degrades to JSON
via ``JSONBType``). JSONB-containment queries are only asserted against
PostgreSQL.
"""
from __future__ import annotations

import os
import sqlite3
import time

import pytest
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (
    ObjectRelationshipModel,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


def _make_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return create_engine(url, future=True)
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def session():
    engine = _make_engine()
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    s = maker()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)


def _sample() -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.COURSE,
        "Intro to CS",
        created_by="faculty:1",
        status=ObjectStatus.ACTIVE,
    )
    obj.set_metadata(
        MetadataEntry("code", "CS101", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        actor="faculty:1",
    )
    obj.add_relationship(
        ObjectId.generate(ObjectType.FACULTY),
        RelationshipKind.TAUGHT_BY,
        Provenance.ASSERTED,
    )
    obj.pop_domain_events()
    return obj


def test_save_and_get_roundtrip(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    repo.save(obj)

    got = repo.get(obj.id)
    assert got is not None
    assert got.id == obj.id
    assert got.title == "Intro to CS"
    assert got.object_type == ObjectType.COURSE
    assert got.metadata.get_value("code") == "CS101"
    assert len(got.relationships) == 1
    assert got.relationships[0].kind == RelationshipKind.TAUGHT_BY


def test_exists_and_delete(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    repo.save(obj)
    assert repo.exists(obj.id) is True
    repo.delete(obj.id)
    assert repo.exists(obj.id) is False
    assert repo.get(obj.id) is None


def test_list_and_find_by_type_status(session):
    repo = SQLAlchemyObjectRepository(session)
    repo.save(_sample())  # COURSE, ACTIVE
    repo.save(
        UniversalObject.create(
            ObjectType.PUBLICATION, "A Paper", created_by="faculty:2", status=ObjectStatus.DRAFT
        )
    )

    assert len(repo.list()) == 2
    assert len(repo.find_by_type(ObjectType.COURSE)) == 1
    assert len(repo.find_by_status(ObjectStatus.DRAFT)) == 1


def test_find_related(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    repo.save(obj)

    related = repo.find_related(obj.id)
    assert len(related) == 1
    assert related[0] == obj.relationships[0].target


def test_find_by_metadata_requires_postgres(session):
    repo = SQLAlchemyObjectRepository(session)
    repo.save(_sample())

    if session.bind.dialect.name != "postgresql":
        pytest.skip("JSONB containment is asserted against PostgreSQL")

    found = repo.find_by_metadata("code", "CS101")
    assert len(found) == 1
    assert found[0].metadata.get_value("code") == "CS101"


# ------------------------------------------------- lock-contention persistence
# SQLite is single-writer: readers (live progress polling) overlap the drain's
# per-item commits, and a loaded machine (AV scanning, full-suite churn, slow
# disks) stretches that overlap past the driver's busy timeout. The driver then
# hands back a TRANSIENT "database is locked". These pins lock the adapter's
# contract: absorb the transient deterministically, never retry real errors,
# and never stall without bound. Injection is a shadowed session.commit — the
# exact failure site, zero wall-clock dependence.


def _locked() -> OperationalError:
    """The exact transient the pysqlite driver hands back under contention."""

    return OperationalError(
        "UPDATE objects", (), sqlite3.OperationalError("database is locked")
    )


def test_save_retries_transient_lock_contention_and_lands(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    calls = {"n": 0}
    real_commit = session.commit

    def flaky_commit() -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _locked()
        real_commit()

    session.commit = flaky_commit  # instance shadow — deterministic injection
    repo.save(obj)  # must heal, must not raise
    assert calls["n"] == 3  # two transient failures absorbed, third lands

    session.commit = real_commit
    landed = repo.get(obj.id)
    assert landed is not None and landed.title == "Intro to CS"


def test_save_fails_fast_on_non_lock_errors(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    calls = {"n": 0}

    def broken_commit() -> None:
        calls["n"] += 1
        raise OperationalError(
            "UPDATE objects", (), sqlite3.OperationalError("disk I/O error")
        )

    session.commit = broken_commit
    with pytest.raises(OperationalError):
        repo.save(obj)
    assert calls["n"] == 1  # real errors are never retried, never hidden


def test_lock_retry_is_bounded_and_deterministic(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = _sample()
    calls = {"n": 0}

    def locked_forever() -> None:
        calls["n"] += 1
        raise _locked()

    session.commit = locked_forever
    started = time.monotonic()
    with pytest.raises(OperationalError):
        repo.save(obj)
    elapsed = time.monotonic() - started
    assert calls["n"] == 5  # hard bound — a wedge surfaces, never a stall
    assert elapsed < 2.0, elapsed  # fixed backoff schedule, no jitter


# ------------------------------------------------- R1 — object graph physical
# model (object_relationships edge table). These pin the physical contract:
# full-fidelity round-trip, replace-on-save semantics, cascade on delete,
# kind-filtered traversal, bulk reads carrying edges, and the physical
# uniqueness mirror of the domain's Relationship.identity key.


def test_relationships_roundtrip_full_fidelity(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "Graphs", created_by="faculty:1")
    target_a = ObjectId.generate(ObjectType.FACULTY)
    target_b = ObjectId.generate(ObjectType.COURSE)
    obj.add_relationship(
        target_a,
        RelationshipKind.TAUGHT_BY,
        Provenance.ASSERTED,
        confidence=0.95,
        evidence=("syllabus.pdf", "page 3"),
        acl_scope="dept:cs",
    )
    obj.add_relationship(
        target_b,
        RelationshipKind.PREREQUISITE_OF,
        Provenance.INFERRED,
        confidence=None,
        evidence=(),
        acl_scope=None,
    )
    obj.pop_domain_events()
    repo.save(obj)

    got = repo.get(obj.id)
    assert got is not None
    assert len(got.relationships) == 2
    first, second = got.relationships
    assert first.target == target_a
    assert first.kind == RelationshipKind.TAUGHT_BY
    assert first.provenance == Provenance.ASSERTED
    assert first.confidence == 0.95
    assert first.evidence == ("syllabus.pdf", "page 3")
    assert first.acl_scope == "dept:cs"
    assert second.target == target_b
    assert second.kind == RelationshipKind.PREREQUISITE_OF
    assert second.provenance == Provenance.INFERRED
    assert second.confidence is None
    assert second.evidence == ()
    assert second.acl_scope is None
    # Aggregate list order is preserved.
    assert [r.target for r in got.relationships] == [target_a, target_b]


def test_save_replaces_whole_edge_set(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "Replaced", created_by="faculty:1")
    obj.add_relationship(
        ObjectId.generate(ObjectType.FACULTY), RelationshipKind.TAUGHT_BY
    )
    obj.pop_domain_events()
    repo.save(obj)

    # Re-save with a completely different edge set: old edges must vanish.
    other = ObjectId.generate(ObjectType.COURSE)
    obj.relationships.clear()
    obj.add_relationship(other, RelationshipKind.PREREQUISITE_OF)
    obj.pop_domain_events()
    repo.save(obj)

    got = repo.get(obj.id)
    assert got is not None
    assert len(got.relationships) == 1
    assert got.relationships[0].target == other
    assert got.relationships[0].kind == RelationshipKind.PREREQUISITE_OF


def test_delete_removes_edges(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "Doomed", created_by="faculty:1")
    obj.add_relationship(
        ObjectId.generate(ObjectType.FACULTY), RelationshipKind.TAUGHT_BY
    )
    obj.pop_domain_events()
    repo.save(obj)

    repo.delete(obj.id)
    assert repo.get(obj.id) is None
    remaining = session.execute(
        select(ObjectRelationshipModel).where(
            ObjectRelationshipModel.source_id == str(obj.id)
        )
    ).scalars().all()
    assert remaining == []


def test_find_related_is_a_direct_edge_query(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "Traversal", created_by="faculty:1")
    teacher = ObjectId.generate(ObjectType.FACULTY)
    successor = ObjectId.generate(ObjectType.COURSE)
    obj.add_relationship(teacher, RelationshipKind.TAUGHT_BY)
    obj.add_relationship(successor, RelationshipKind.PREREQUISITE_OF)
    obj.pop_domain_events()
    repo.save(obj)

    assert repo.find_related(obj.id) == [teacher, successor]
    assert repo.find_related(obj.id, RelationshipKind.TAUGHT_BY) == [teacher]
    assert repo.find_related(obj.id, RelationshipKind.PREREQUISITE_OF) == [successor]
    # Missing source behaves as before: empty, never an error.
    assert repo.find_related(ObjectId.generate(ObjectType.COURSE)) == []


def test_bulk_reads_carry_relationships(session):
    repo = SQLAlchemyObjectRepository(session)
    objs = []
    for i in range(3):
        obj = UniversalObject.create(
            ObjectType.COURSE, f"Bulk {i}", created_by="faculty:1"
        )
        obj.add_relationship(
            ObjectId.generate(ObjectType.FACULTY), RelationshipKind.TAUGHT_BY
        )
        obj.pop_domain_events()
        objs.append(obj)
        repo.save(obj)

    listed = repo.list()
    assert len(listed) == 3
    assert all(len(o.relationships) == 1 for o in listed)

    by_ids = repo.find_by_ids([o.id for o in objs])
    assert len(by_ids) == 3
    assert all(len(o.relationships) == 1 for o in by_ids)

    by_type = repo.find_by_type(ObjectType.COURSE)
    assert len(by_type) == 3
    assert all(len(o.relationships) == 1 for o in by_type)


def test_edge_table_enforces_domain_identity_uniqueness(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "Unique", created_by="faculty:1")
    target = ObjectId.generate(ObjectType.FACULTY)
    obj.add_relationship(target, RelationshipKind.TAUGHT_BY)
    obj.pop_domain_events()
    repo.save(obj)

    # The physical UNIQUE (source_id, target_id, kind, provenance) mirrors the
    # aggregate's Relationship.identity de-dup key.
    session.add(
        ObjectRelationshipModel(
            source_id=str(obj.id),
            target_id=str(target),
            kind=RelationshipKind.TAUGHT_BY.value,
            provenance=Provenance.ASSERTED.value,
            confidence=None,
            evidence=[],
            acl_scope=None,
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ------------------------------------------------- R2 — repository projections
# (SQL pagination + count on find()). These pin the physical read contract:
# page_size=0 preserves the historical load-all behaviour, page_size>0
# returns a deterministic page ordered by the requested column (id as
# tie-break), and count() answers total_count for the same filters.


def _save_n_courses(session, n: int) -> SQLAlchemyObjectRepository:
    repo = SQLAlchemyObjectRepository(session)
    for i in range(n):
        obj = UniversalObject.create(
            ObjectType.COURSE, f"Course {i}", created_by="faculty:1"
        )
        obj.pop_domain_events()
        repo.save(obj)
    return repo


def test_find_pagination_and_count(session):
    repo = _save_n_courses(session, 5)

    assert repo.count() == 5
    # page_size=0 (default) preserves load-all behaviour.
    assert len(repo.find()) == 5
    assert len(repo.find(page=2)) == 5  # page ignored when unpaginated

    sorted_ids = sorted(str(o.id) for o in repo.find())
    page1 = repo.find(page=1, page_size=2)
    assert [str(o.id) for o in page1] == sorted_ids[:2]
    page2 = repo.find(page=2, page_size=2)
    assert [str(o.id) for o in page2] == sorted_ids[2:4]
    page3 = repo.find(page=3, page_size=2)
    assert [str(o.id) for o in page3] == sorted_ids[4:]
    # Past the end: empty page, never an error.
    assert repo.find(page=4, page_size=2) == []


def test_find_pagination_with_filters(session):
    repo = SQLAlchemyObjectRepository(session)
    for i in range(3):
        obj = UniversalObject.create(
            ObjectType.COURSE, f"C{i}", created_by="faculty:1"
        )
        obj.pop_domain_events()
        repo.save(obj)
    for i in range(4):
        obj = UniversalObject.create(
            ObjectType.PUBLICATION, f"P{i}", created_by="faculty:1"
        )
        obj.pop_domain_events()
        repo.save(obj)

    assert repo.count(object_type=ObjectType.COURSE) == 3
    assert repo.count(object_type=ObjectType.PUBLICATION) == 4

    page = repo.find(object_type=ObjectType.PUBLICATION, page=1, page_size=2)
    assert len(page) == 2
    assert all(o.object_type == ObjectType.PUBLICATION for o in page)
    assert len(repo.find(object_type=ObjectType.COURSE, page=2, page_size=2)) == 1
    # Count and page filters must agree.
    total = repo.count(object_type=ObjectType.PUBLICATION)
    pages = []
    collected = []
    for p in range(1, total + 1):
        items = repo.find(object_type=ObjectType.PUBLICATION, page=p, page_size=2)
        if not items:
            break
        pages.append(items)
        collected.extend(items)
    assert sum(len(p) for p in pages) == total
    assert len({str(o.id) for o in collected}) == total  # no overlap, no loss


def test_count_metadata_filter(session):
    repo = SQLAlchemyObjectRepository(session)
    obj = UniversalObject.create(ObjectType.COURSE, "With Code", created_by="faculty:1")
    obj.set_metadata(
        MetadataEntry("code", "CS101", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        actor="faculty:1",
    )
    obj.pop_domain_events()
    repo.save(obj)
    other = UniversalObject.create(ObjectType.COURSE, "No Code", created_by="faculty:1")
    other.pop_domain_events()
    repo.save(other)

    # A key that exists nowhere matches on every engine (exercises the
    # count() SQL path without JSONB containment).
    assert repo.count(metadata_key="missing") == 0

    if session.bind.dialect.name != "postgresql":
        pytest.skip("JSONB containment is asserted against PostgreSQL")

    assert repo.count(metadata_key="code") == 1
    assert repo.count(metadata_key="code", metadata_value="CS101") == 1
    assert repo.count(metadata_key="code", metadata_value="PHY101") == 0


def test_find_sort_and_order(session):
    repo = SQLAlchemyObjectRepository(session)
    for i in range(3):
        obj = UniversalObject.create(
            ObjectType.COURSE, f"Title {i}", created_by="faculty:1"
        )
        obj.pop_domain_events()
        repo.save(obj)

    desc = repo.find(page=1, page_size=10, sort_by="title", order="desc")
    assert [o.title for o in desc] == ["Title 2", "Title 1", "Title 0"]
    asc = repo.find(page=1, page_size=10, sort_by="title", order="asc")
    assert [o.title for o in asc] == ["Title 0", "Title 1", "Title 2"]
    # Sorting applies with or without pagination.
    all_desc = repo.find(sort_by="title", order="desc")
    assert [o.title for o in all_desc] == ["Title 2", "Title 1", "Title 0"]
    assert len(all_desc) == 3


def test_find_rejects_invalid_sort_and_order(session):
    repo = _save_n_courses(session, 1)
    with pytest.raises(ValueError):
        repo.find(page=1, page_size=10, sort_by="bogus")
    with pytest.raises(ValueError):
        repo.find(sort_by="bogus")  # rejected even when unpaginated
    with pytest.raises(ValueError):
        repo.find(page=1, page_size=10, order="sideways")
    with pytest.raises(ValueError):
        repo.find(order="sideways")  # rejected even when unpaginated
    with pytest.raises(ValueError):
        repo.find(page=0, page_size=10)
    with pytest.raises(ValueError):
        repo.find(page=1, page_size=-1)
