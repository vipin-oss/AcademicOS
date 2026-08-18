"""Regression tests for claim projection type inference.

Ensures that domain-specific evidence takes precedence over generic predicates,
and that cross-domain collisions (e.g., journal_name from venue synonym) do not
cause incorrect domain object creation.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.claim_projection import ClaimProjectionService
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.enums import ObjectType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore
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


def _svc(db) -> DocumentIntakeService:
    store = SQLClaimStore(db)
    return DocumentIntakeService(ClaimService(store), store)


def _analyze_and_confirm(db, text, filename, document_id):
    """Analyze and confirm all claims."""
    a = _svc(db).analyze(
        text=text, filename=filename, document_id=document_id, version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    store = SQLClaimStore(db)
    claim_svc = ClaimService(store)
    for r in a.records:
        if r.claim_id:
            c = store.get(r.claim_id)
            if c and c[0].status in (ClaimStatus.PROPOSED, ClaimStatus.AUTO_SUGGESTED):
                claim_svc.confirm(r.claim_id, reviewer="u:1", assert_human=True)
    db.commit()
    return a


# --- Test A: Conference cert with Venue → Event, NO journal_name, NO Publication ---

CONFERENCE_CERT = """Certificate of Participation
Conference: International Conference on Quantum Computing
Acronym: ICQC-2025
Organizer: IEEE Computer Society
Venue: Convention Centre, Bangalore
Start Date: 15 March 2025
End Date: 17 March 2025
Participation Type: Paper Presented
Certificate Number: ICQC-2025-P-0847
"""


def test_conference_cert_no_journal_name_extraction(db):
    """Venue: must NOT create journal_name claim in a conference certificate."""
    _analyze_and_confirm(db, CONFERENCE_CERT, "cert.pdf", "obj:doc:1")
    store = SQLClaimStore(db)
    claims = store.by_source("obj:doc:1")
    jn = [c for c in claims if c.predicate_id == "journal_name"]
    assert len(jn) == 0, (
        f"journal_name must not be extracted from conference cert, "
        f"got {len(jn)} claims"
    )


def test_conference_cert_projects_to_event_not_publication(db):
    """Conference certificate must project to Event, never Publication."""
    _analyze_and_confirm(db, CONFERENCE_CERT, "cert.pdf", "obj:doc:1")
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:1", created_by="u:1")
    db.commit()

    assert result.status == "projected"
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "event"
    assert not any(o.module == "publication" for o in result.outcomes)


def test_conference_cert_with_paper_presented_still_routes_to_event(db):
    """'Paper Presented' triggers publication secondary classification but
    conference_name must still win the projection."""
    _analyze_and_confirm(db, CONFERENCE_CERT, "paper_cert.pdf", "obj:doc:1")
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:1", created_by="u:1")
    db.commit()

    created = [o for o in result.outcomes if o.kind == "created"]
    assert any(o.module == "event" for o in created), "Must create Event"
    assert not any(o.module == "publication" for o in result.outcomes), (
        "Must NOT create Publication from conference cert"
    )


# --- Test B: Publication still works ---

PUBLICATION = """Title: A Study of Quantum Dots
Authors: A. Sharma, R. Kumar
Journal: Journal of Materials Research
Volume: 45
Issue: 2
Pages: 100-110
Year: 2024
DOI: 10.1000/xyz123
Publisher: Springer
"""


def test_genuine_publication_still_projects(db):
    """Publication with title/journal/DOI must still create a Publication."""
    _analyze_and_confirm(db, PUBLICATION, "article.pdf", "obj:doc:2")
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:2", created_by="u:1")
    db.commit()

    assert result.status == "projected"
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "publication"


def test_publication_with_published_in_synonym(db):
    """'Published In:' must extract journal_name for publications."""
    text = """Title: Quantum Computing Advances
Authors: B. Chen
Published In: Nature Physics
Volume: 20
Year: 2025
DOI: 10.1038/s41567-025-0001
"""
    a = _analyze_and_confirm(db, text, "paper.pdf", "obj:doc:3")
    store = SQLClaimStore(db)
    # Verify journal_name was extracted via "published in" synonym
    claims = store.by_source("obj:doc:3")
    jn = [c for c in claims if c.predicate_id == "journal_name"]
    assert len(jn) == 1, "journal_name must be extracted via 'published in'"
    assert "Nature" in jn[0].value.get("value", "")

    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:3", created_by="u:1")
    db.commit()

    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "publication"


# --- Test C: Conference cert with publication-like text → Event ---

def test_conference_cert_with_publication_keywords_routes_to_event(db):
    """Even when the text contains publication-adjacent keywords,
    conference_name must still win the projection.

    Note: 'Paper Title' is intentionally avoided here because it is a synonym
    for BOTH presentation_title (conference) and publication_title (publication).
    That ambiguity is a known extraction schema overlap, tested separately.
    """
    text = """Certificate of Participation
Conference: International Workshop on Machine Learning
Presentation Title: Deep Learning for NLP
Venue: MIT Press
Start Date: 1 January 2025
Certificate Number: IWML-2025-001
"""
    _analyze_and_confirm(db, text, "cert.pdf", "obj:doc:4")
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:4", created_by="u:1")
    db.commit()

    created = [o for o in result.outcomes if o.kind == "created"]
    assert any(o.module == "event" for o in created), "Must create Event"
    assert not any(o.module == "publication" for o in result.outcomes)


# --- Test D: journal_name alone does NOT create Publication ---

def test_journal_name_alone_insufficient_for_publication(db):
    """A single journal_name predicate without publication_title must NOT
    trigger Publication projection."""
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    claim_svc = ClaimService(store)

    # Manually create a confirmed claim with only journal_name
    claim = claim_svc.propose(
        predicate_id="journal_name", raw_value="Nature Physics",
        source_text="Journal: Nature Physics",
        source_document_id="obj:doc:5", source_version=1,
        spans=[], acl_scope='{"owner":"u:1"}',
    )
    claim_svc.confirm(claim.claim_id, reviewer="u:1", assert_human=True)
    db.commit()

    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:5", created_by="u:1")
    db.commit()

    # journal_name alone should NOT create a Publication
    created = [o for o in result.outcomes if o.kind == "created"]
    assert not any(o.module == "publication" for o in created), (
        "journal_name alone must not create Publication (no publication_title)"
    )


# --- Test E: Re-analysis creates no duplicates ---

def test_reanalysis_creates_no_duplicate_event(db):
    """Re-analyzing the same conference certificate must not create
    a duplicate Event."""
    _analyze_and_confirm(db, CONFERENCE_CERT, "cert.pdf", "obj:doc:6")
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    proj = ClaimProjectionService(store, repo)

    # First projection
    r1 = proj.project_document("obj:doc:6", created_by="u:1")
    db.commit()
    created1 = [o for o in r1.outcomes if o.kind == "created"]
    assert len(created1) == 1
    event_id = created1[0].object_id

    # Re-analyze and re-confirm
    _svc(db).analyze(
        text=CONFERENCE_CERT, filename="cert.pdf",
        document_id="obj:doc:6", version=2,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    db.commit()
    _analyze_and_confirm(db, CONFERENCE_CERT, "cert.pdf", "obj:doc:6")

    # Re-project
    r2 = proj.project_document("obj:doc:6", created_by="u:1")
    db.commit()
    created2 = [o for o in r2.outcomes if o.kind == "created"]
    assert len(created2) == 0, "Must not re-create Event"
    assert not any(o.module == "publication" for o in r2.outcomes)


# --- Test F: Projection safety — insufficient evidence ---

def test_insufficient_evidence_prevents_projection(db):
    """When type inference succeeds but evidence is too weak,
    projection must return 'no_mapping'."""
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    claim_svc = ClaimService(store)

    # Manually create claims with conference-specific but non-defining predicates
    for pred, val in [("conference_acronym", "ICML-2025"), ("venue", "Berlin")]:
        c = claim_svc.propose(
            predicate_id=pred, raw_value=val, source_text=f"{pred}: {val}",
            source_document_id="obj:doc:7", source_version=1,
            spans=[], acl_scope='{"owner":"u:1"}',
        )
        claim_svc.confirm(c.claim_id, reviewer="u:1", assert_human=True)
    db.commit()

    proj = ClaimProjectionService(store, repo)
    result = proj.project_document("obj:doc:7", created_by="u:1")
    db.commit()

    # Without conference_name (defining predicate), Event should NOT be created
    created = [o for o in result.outcomes if o.kind == "created"]
    assert not created, (
        f"conference_acronym alone should not create Event, got {created}"
    )
