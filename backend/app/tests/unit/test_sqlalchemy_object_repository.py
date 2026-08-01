"""Unit tests for the SQLAlchemyObjectRepository adapter.

Uses PostgreSQL-compatible models (the ``objects`` table emits JSONB on
PostgreSQL). The engine is configurable via ``TEST_DATABASE_URL``; when unset, an
in-memory SQLite database is used so the tests run offline (JSONB degrades to JSON
via ``JSONBType``). JSONB-containment queries are only asserted against
PostgreSQL.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import StaticPool, create_engine
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

from app.infrastructure.db.models.object_model import Base, ObjectModel
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
