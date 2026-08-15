"""Unit tests for the AnswerVerifier (Sprint-6 M3 Phase 5).

Every citation must reference an existing, READ-permitted object; deleted
or hidden objects are dropped, malformed ids are dropped, duplicates are
removed, and survivors are renumbered contiguously in order.
"""
from __future__ import annotations

import json

from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.assistant.verifier import AnswerVerifier
from app.application.dtos.assistant import AssistantCitation
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


def _citation(number: int, object_id: str) -> AssistantCitation:
    return AssistantCitation(
        number=number, object_id=object_id, object_type="document",
        title=f"Doc {number}", sources=("search",), version=1, score=0.1,
    )


def _user() -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


def _db_with(*objects: UniversalObject):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    for obj in objects:
        obj.pop_domain_events()
        repo.save(obj)
    return session, repo


def test_valid_citations_survive_in_order():
    a = UniversalObject.create(ObjectType.DOCUMENT, "A", created_by="f:1")
    b = UniversalObject.create(ObjectType.DOCUMENT, "B", created_by="f:1")
    session, repo = _db_with(a, b)
    try:
        verified = AnswerVerifier(ObjectPermissionEvaluator()).verify(
            [_citation(1, str(a.id)), _citation(2, str(b.id))], repo, _user()
        )
        assert [c.object_id for c in verified] == [str(a.id), str(b.id)]
        assert [c.number for c in verified] == [1, 2]
    finally:
        session.close()


def test_deleted_object_citation_is_dropped():
    a = UniversalObject.create(ObjectType.DOCUMENT, "A", created_by="f:1")
    b = UniversalObject.create(ObjectType.DOCUMENT, "B", created_by="f:1")
    session, repo = _db_with(a, b)
    try:
        repo.delete(a.id)  # deleted between retrieval and verification
        verified = AnswerVerifier(ObjectPermissionEvaluator()).verify(
            [_citation(1, str(a.id)), _citation(2, str(b.id))], repo, _user()
        )
        assert [c.object_id for c in verified] == [str(b.id)]
        assert verified[0].number == 1  # renumbered contiguously
    finally:
        session.close()


def test_hidden_object_citation_is_dropped():
    secret = UniversalObject.create(ObjectType.DOCUMENT, "Secret", created_by="f:2")
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    open_doc = UniversalObject.create(ObjectType.DOCUMENT, "Open", created_by="f:1")
    session, repo = _db_with(secret, open_doc)
    try:
        verified = AnswerVerifier(ObjectPermissionEvaluator()).verify(
            [_citation(1, str(secret.id)), _citation(2, str(open_doc.id))], repo, _user()
        )
        assert [c.object_id for c in verified] == [str(open_doc.id)]  # no leak
        assert verified[0].number == 1
    finally:
        session.close()


def test_malformed_id_is_dropped():
    a = UniversalObject.create(ObjectType.DOCUMENT, "A", created_by="f:1")
    session, repo = _db_with(a)
    try:
        verified = AnswerVerifier(ObjectPermissionEvaluator()).verify(
            [_citation(1, "not-an-object-id"), _citation(2, str(a.id))], repo, _user()
        )
        assert [c.object_id for c in verified] == [str(a.id)]
    finally:
        session.close()


def test_duplicates_removed_keeping_first():
    a = UniversalObject.create(ObjectType.DOCUMENT, "A", created_by="f:1")
    session, repo = _db_with(a)
    try:
        verified = AnswerVerifier(ObjectPermissionEvaluator()).verify(
            [_citation(1, str(a.id)), _citation(2, str(a.id))], repo, _user()
        )
        assert len(verified) == 1
        assert verified[0].number == 1
    finally:
        session.close()


def test_deterministic_for_same_state():
    a = UniversalObject.create(ObjectType.DOCUMENT, "A", created_by="f:1")
    b = UniversalObject.create(ObjectType.DOCUMENT, "B", created_by="f:1")
    session, repo = _db_with(a, b)
    try:
        verifier = AnswerVerifier(ObjectPermissionEvaluator())
        first = verifier.verify(
            [_citation(1, str(a.id)), _citation(2, str(b.id))], repo, _user()
        )
        second = verifier.verify(
            [_citation(1, str(a.id)), _citation(2, str(b.id))], repo, _user()
        )
        assert first == second
    finally:
        session.close()
