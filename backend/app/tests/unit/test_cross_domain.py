"""L8 unit tests — cross-domain multi-hop, absence, compare, temporal (ADR-043)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cross_domain import CrossDomainService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.temporal import resolve_time_range, within_range
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


class _DenyAll:
    def can(self, *, principal, scope, action):
        return False


@pytest.fixture()
def world():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    user = UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l8-owner"),
    )
    repo.save(user)

    grant = UniversalObject.create(
        ObjectType.GRANT, "HSRF Grant", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:grant:l8-1"),
    )
    pub = UniversalObject.create(
        ObjectType.PUBLICATION, "Catalyst Paper", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:publication:l8-1"),
    )
    repo.save(grant)
    repo.save(pub)
    grant.add_relationship(pub.id, RelationshipKind.PRODUCES, actor="system")
    repo.save(grant)
    try:
        yield {
            "repo": repo, "user": user, "grant": grant, "pub": pub,
            "svc": CrossDomainService(repo, GraphRuntimeService(repo, ObjectPermissionEvaluator()), ObjectPermissionEvaluator()),
        }
    finally:
        session.close()
        engine.dispose()


def test_multi_hop_entity_anchored(world):
    res = world["svc"].multi_hop([str(world["grant"].id)], world["user"], max_depth=2)
    ids = [n.object_id for n in res.nodes]
    assert str(world["grant"].id) in ids
    assert str(world["pub"].id) in ids  # grant -> produces -> pub (cross-domain)


def test_multi_hop_deterministic_order(world):
    a = world["svc"].multi_hop([str(world["grant"].id)], world["user"], max_depth=2)
    b = world["svc"].multi_hop([str(world["grant"].id)], world["user"], max_depth=2)
    assert [n.object_id for n in a.nodes] == [n.object_id for n in b.nodes]


def test_multi_hop_bounded_depth(world):
    # depth clamped to MAX_MULTIHOP_DEPTH; traversal never exceeds it.
    res = world["svc"].multi_hop([str(world["grant"].id)], world["user"], max_depth=999)
    assert max((n.level for n in res.nodes), default=0) <= 5


def test_absence_confirmed_within_authorized_scope(world):
    res = world["svc"].absence(target_type="course", user=world["user"])
    assert res.outcome == "confirmed_absence"


def test_absence_present_when_match(world):
    res = world["svc"].absence(target_type="grant", user=world["user"])
    assert res.outcome == "present"


def test_absence_insufficient_evidence_unknown_type(world):
    res = world["svc"].absence(target_type="not_a_type", user=world["user"])
    assert res.outcome == "insufficient_evidence"


def test_absence_deny_all_never_leaks(world):
    deny = CrossDomainService(world["repo"], GraphRuntimeService(world["repo"], ObjectPermissionEvaluator()), _DenyAll())
    res = deny.absence(target_type="grant", user=world["user"])
    # no authorized match visible to a denied principal
    assert res.outcome in ("confirmed_absence", "insufficient_evidence")
    assert res.authorized_count == 0


def test_compare_preserves_source_and_missing(world):
    res = world["svc"].compare(
        labels=[str(world["grant"].id), "does-not-exist"],
        user=world["user"],
        target_type="grant",
    )
    rows = {r.label: r for r in res.rows}
    assert rows[str(world["grant"].id)].missing is False
    assert str(world["grant"].id) in rows[str(world["grant"].id)].source_ids
    assert rows["does-not-exist"].missing is True


def test_compare_deterministic_ordering(world):
    a = world["svc"].compare(labels=["b", "a"], user=world["user"], target_type="grant")
    assert [r.label for r in a.rows] == sorted(["b", "a"])


def test_temporal_resolution_this_year():
    now = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
    start, end = resolve_time_range("this year", now=now)
    assert start.year == 2026 and end.year == 2027


def test_temporal_resolution_year_bounds():
    now = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
    start, end = resolve_time_range("2024", now=now)
    assert start.year == 2024 and end.year == 2025


def test_temporal_within_range():
    now = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
    start, end = resolve_time_range("2025", now=now)
    assert within_range(dt.datetime(2025, 5, 1, tzinfo=dt.timezone.utc), start, end) is True
    assert within_range(dt.datetime(2024, 5, 1, tzinfo=dt.timezone.utc), start, end) is False


def test_temporal_unknown_returns_unbounded():
    now = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
    start, end = resolve_time_range("sometime", now=now)
    assert start is None and end is None
