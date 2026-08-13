"""L5 deterministic data-tool tests (ADR-037) over a real ObjectRepository."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.tools.data_tools import (
    CountTool,
    InventoryTool,
    ListTool,
    LookupTool,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def repo(db):
    r = SQLAlchemyObjectRepository(db)
    for i in range(3):
        obj = UniversalObject.create(
            ObjectType.PUBLICATION, f"Pub {i}", created_by="u:1",
            status=ObjectStatus.ACTIVE, object_id=ObjectId(f"obj:publication:l5-{i}"),
        )
        r.save(obj)
    obj = UniversalObject.create(
        ObjectType.GRANT, "Grant A", created_by="u:1", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:grant:l5-0"),
    )
    r.save(obj)
    return r


def test_count_tool(repo):
    r = CountTool(repo).execute(principal="u:1", args={"object_type": "publication"})
    assert r.ok is True
    assert r.value["count"] == 3


def test_count_tool_unknown_type(repo):
    r = CountTool(repo).execute(principal="u:1", args={"object_type": "banana"})
    assert r.ok is True
    assert r.value["count"] == 0


def test_list_tool(repo):
    r = ListTool(repo).execute(principal="u:1", args={"object_type": "publication"})
    assert r.ok is True
    assert len(r.value["items"]) == 3


def test_lookup_tool_found(repo):
    r = LookupTool(repo).execute(
        principal="u:1", args={"object_id": "obj:grant:l5-0"}
    )
    assert r.ok is True
    assert r.value["object"]["object_type"] == "grant"


def test_lookup_tool_not_found(repo):
    r = LookupTool(repo).execute(principal="u:1", args={"object_id": "obj:grant:zzz"})
    assert r.ok is False


def test_inventory_tool(repo):
    r = InventoryTool(repo).execute(principal="u:1", args={})
    assert r.ok is True
    kinds = {k["type"]: k["count"] for k in r.value["kinds"]}
    assert kinds.get("publication") == 3
    assert kinds.get("grant") == 1
