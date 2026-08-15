"""V3 ADR-068 domain-record routing tests (actual records vs claim-only).

Proves the pipeline creates ACTUAL AcademicOS domain records for supported
types (Event/Publication/Project/Committee) — with duplicate detection and
provenance linking — and reports claim-only for types with no entity.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.domain_record_router import DomainRecordRouter
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _doc(repo, oid="obj:document:1") -> UniversalObject:
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "src.pdf", created_by="u:1", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(oid),
    )
    repo.save(doc)
    return doc


def test_conference_routes_to_event_record(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("conference",),
        fields={
            "conference_name": "International Conference on Quantum Materials",
            "start_date": "2024-12-06",
            "end_date": "2024-12-08",
            "venue": "Vigyan Bhawan",
            "conference_organizer": "IPA",
            "__types__": ("conference",),
        },
        created_by="u:1", source_document_id="obj:document:1", confidence=0.95,
    )
    assert len(outcomes) == 1
    assert outcomes[0].module == "event"
    assert outcomes[0].kind == "created"
    # the record is a real EVENT object with provenance edge to the document
    event = repo.get_by_id(ObjectId(outcomes[0].object_id))
    assert event is not None and event.object_type is ObjectType.EVENT
    assert event.title == "International Conference on Quantum Materials"
    related = repo.find_related(ObjectId(outcomes[0].object_id))
    assert ObjectId("obj:document:1") in related


def test_publication_routes_to_publication_record(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("publication",),
        fields={
            "publication_title": "A Study of Quantum Dots",
            "doi": "10.1000/xyz123",
            "journal_name": "J. Mater.",
            "publication_year": "2024",
        },
        created_by="u:1", source_document_id="obj:document:1", confidence=0.95,
    )
    assert outcomes[0].module == "publication" and outcomes[0].kind == "created"
    pub = repo.get_by_id(ObjectId(outcomes[0].object_id))
    assert pub is not None and pub.object_type is ObjectType.PUBLICATION


def test_sanction_routes_to_project_record(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("grant_sanction_letter",),
        fields={
            "project_title": "Energy Storage Materials",
            "sanction_order_number": "SERB/2024/00123",
            "start_date": "2024-04-01",
            "end_date": "2027-03-31",
            "sanctioned_amount": 5000000.0,
        },
        created_by="u:1", source_document_id="obj:document:1", confidence=0.95,
    )
    assert outcomes[0].module == "project" and outcomes[0].kind == "created"
    proj = repo.get_by_id(ObjectId(outcomes[0].object_id))
    assert proj is not None and proj.object_type is ObjectType.RESEARCH_PROJECT


def test_committee_routes_to_committee_record(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("committee",),
        fields={"committee_name": "Departmental Research Committee",
                "order_date": "2024-01-10"},
        created_by="u:1", source_document_id="obj:document:1", confidence=0.95,
    )
    assert outcomes[0].module == "committee" and outcomes[0].kind == "created"
    comm = repo.get_by_id(ObjectId(outcomes[0].object_id))
    assert comm is not None and comm.object_type is ObjectType.COMMITTEE


def test_duplicate_conference_is_not_recreated(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    fields = {"conference_name": "ICQM 2024", "start_date": "2024-12-06",
              "__types__": ("conference",)}
    first = router.route(type_ids=("conference",), fields=fields,
                         created_by="u:1", source_document_id="obj:document:1",
                         confidence=0.95)
    assert first[0].kind == "created"
    # second upload of the same conference -> duplicate, no new record
    second = router.route(type_ids=("conference",), fields=fields,
                          created_by="u:1", source_document_id="obj:document:2",
                          confidence=0.95)
    assert second[0].kind == "duplicate"
    assert second[0].existing_id == first[0].object_id
    # exactly one EVENT object exists
    events = repo.find_by_type(ObjectType.EVENT)
    assert len(events) == 1


def test_award_is_claim_only(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("award",),
        fields={"award_title": "Best Paper Award"},
        created_by="u:1", source_document_id="obj:document:1", confidence=0.95,
    )
    assert outcomes[0].module == "claim_only"
    assert outcomes[0].kind == "claim_only"


def test_missing_title_skips(db):
    repo = _repo(db)
    _doc(repo)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("conference",), fields={},
        created_by="u:1", source_document_id="obj:document:1", confidence=0.9,
    )
    assert outcomes[0].kind == "skipped"
