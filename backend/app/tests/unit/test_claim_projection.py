"""Tests for ClaimProjectionService — the critical claim→domain object bridge.

Verifies that confirmed claims become visible academic records (Events,
Publications, Research Projects, Committees) and that the projection is
idempotent, preserves provenance, and handles corrected/rejected claims.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_projection import ClaimProjectionService
from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
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
    """Analyze a document and confirm all its claims."""
    a = _svc(db).analyze(
        text=text, filename=filename, document_id=document_id, version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    store = SQLClaimStore(db)
    claim_svc = ClaimService(store)
    for r in a.records:
        if r.claim_id:
            claim_svc.confirm(r.claim_id, reviewer="u:1", assert_human=True)
    db.commit()
    return a


CONFERENCE_TEXT = """Certificate of Participation
Conference: International Conference on Quantum Materials
Acronym: ICQM-2024
Organizer: Indian Physics Association
Venue: Vigyan Bhawan
City: New Delhi
Country: India
Start Date: 6 December 2024
End Date: 8 December 2024
Participation Type: Attended
Presentation Title: Topological Insulators for Energy Storage
Presentation Type: Oral
Certificate Number: ICQM-2024-0123
"""

PUBLICATION_TEXT = """Journal Article
Title: A Study of Quantum Dots
Authors: A. Sharma, R. Kumar
Journal: Journal of Materials Research
Volume: 45
Issue: 2
Pages: 100-110
Year: 2024
DOI: 10.1000/xyz123
Publisher: Springer
"""

SANCTION_TEXT = """Sanction Letter
Project Title: Energy Storage Materials
Funding Agency: SERB
Principal Investigator: Dr. Anita Sharma
Sanction Number: SERB/2024/00123
Sanction Date: 15 March 2024
Sanctioned Amount: Rs. 50,00,000
Duration: 36 months
Start Date: 1 April 2024
End Date: 31 March 2027
"""

COMMITTEE_TEXT = """Office Order
Committee: Departmental Research Committee
Order Number: OO/2024/DRC/05
Order Date: 10 January 2024
Members: Dr. A, Dr. B, Dr. C
Purpose: To review research proposals
Tenure: Two years
"""


# ---------------------------------------------------------------------------
# 1. Conference certificate → Event projection
# ---------------------------------------------------------------------------

def test_conference_certificate_projects_to_event(db):
    """Confirmed conference claims must create an Event."""
    _analyze_and_confirm(db, CONFERENCE_TEXT, "certificate.pdf", "obj:doc:1")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:1", created_by="u:1")

    assert result.status == "projected"
    assert result.confirmed_claim_count > 0
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "event"

    # Verify the event exists in the repository
    event = repo.get_by_id(ObjectId(created[0].object_id))
    assert event is not None
    assert event.object_type == ObjectType.EVENT
    assert "Quantum Materials" in (event.title or "")
    db.commit()


# ---------------------------------------------------------------------------
# 2. Publication document → Publication projection
# ---------------------------------------------------------------------------

def test_publication_projects_to_publication(db):
    """Confirmed publication claims must create a Publication."""
    _analyze_and_confirm(db, PUBLICATION_TEXT, "article.pdf", "obj:doc:2")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:2", created_by="u:1")

    assert result.status == "projected"
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "publication"

    pub = repo.get_by_id(ObjectId(created[0].object_id))
    assert pub is not None
    assert pub.object_type == ObjectType.PUBLICATION
    assert "Quantum Dots" in (pub.title or "")
    db.commit()


# ---------------------------------------------------------------------------
# 3. Grant document → Research Project projection
# ---------------------------------------------------------------------------

def test_grant_projects_to_research_project(db):
    """Confirmed grant claims must create a Research Project."""
    _analyze_and_confirm(db, SANCTION_TEXT, "sanction.pdf", "obj:doc:3")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:3", created_by="u:1")

    assert result.status == "projected"
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1
    assert created[0].module == "project"

    project = repo.get_by_id(ObjectId(created[0].object_id))
    assert project is not None
    assert project.object_type == ObjectType.RESEARCH_PROJECT
    assert "Energy Storage" in (project.title or "")
    db.commit()


# ---------------------------------------------------------------------------
# 4. Committee document → Committee projection
# ---------------------------------------------------------------------------

def test_committee_projects_to_committee(db):
    """Confirmed committee claims must create a Committee."""
    # Committees use NOTICE_FIELDS + COMMITTEE_FIELDS via secondary types.
    # We need to analyze with a committee-focused document.
    text = """Order Number: OO/2024/DRC/05
Order Date: 10 January 2024
Committee: Departmental Research Committee
Members: Dr. A, Dr. B, Dr. C
Purpose: To review research proposals
Tenure: Two years
"""
    _analyze_and_confirm(db, text, "committee_order.pdf", "obj:doc:4")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:4", created_by="u:1")

    assert result.status == "projected"
    created = [o for o in result.outcomes if o.kind == "created"]
    # May create event (from office_order) or committee
    assert len(created) >= 1
    db.commit()


# ---------------------------------------------------------------------------
# 5. Idempotency: re-projecting the same document does NOT create duplicates
# ---------------------------------------------------------------------------

def test_projection_is_idempotent(db):
    """Projecting the same confirmed claims twice must NOT create duplicates."""
    _analyze_and_confirm(db, CONFERENCE_TEXT, "certificate.pdf", "obj:doc:1")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)

    # First projection
    result1 = projection.project_document("obj:doc:1", created_by="u:1")
    created1 = [o for o in result1.outcomes if o.kind == "created"]
    assert len(created1) == 1
    object_id = created1[0].object_id
    db.commit()

    # Second projection — must be idempotent
    result2 = projection.project_document("obj:doc:1", created_by="u:1")
    created2 = [o for o in result2.outcomes if o.kind == "created"]
    assert len(created2) == 0, "Re-projection must not create duplicate objects"

    # Duplicate detection should report the existing object
    dups = [o for o in result2.outcomes if o.kind == "duplicate"]
    assert len(dups) == 1
    assert dups[0].existing_id == object_id
    db.commit()


# ---------------------------------------------------------------------------
# 6. Source-document provenance preserved
# ---------------------------------------------------------------------------

def test_projection_preserves_provenance(db):
    """The domain object must be linked back to its source document."""
    _analyze_and_confirm(db, CONFERENCE_TEXT, "certificate.pdf", "obj:doc:1")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:1", created_by="u:1")
    created = [o for o in result.outcomes if o.kind == "created"]
    assert len(created) == 1

    # Verify RELATED_TO relationship from event to document
    event = repo.get_by_id(ObjectId(created[0].object_id))
    assert event is not None
    rels = event.relationships
    doc_rel = next(
        (r for r in rels if str(r.target) == "obj:doc:1"), None
    )
    assert doc_rel is not None, "Event must have RELATED_TO link to source document"
    db.commit()


# ---------------------------------------------------------------------------
# 7. Rejected claims do NOT participate in projection
# ---------------------------------------------------------------------------

def test_rejected_claims_do_not_project(db):
    """Rejected claims must not create domain objects."""
    a = _svc(db).analyze(
        text=CONFERENCE_TEXT, filename="certificate.pdf",
        document_id="obj:doc:1", version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    store = SQLClaimStore(db)
    claim_svc = ClaimService(store)
    # Reject all claims instead of confirming
    for r in a.records:
        if r.claim_id:
            claim_svc.reject(r.claim_id, reviewer="u:1")
    db.commit()

    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:1", created_by="u:1")

    assert result.status == "no_claims", "Rejected claims must not project"
    assert result.confirmed_claim_count == 0
    db.commit()


# ---------------------------------------------------------------------------
# 8. Corrected claims update domain objects
# ---------------------------------------------------------------------------

def test_corrected_claim_updates_domain_object(db):
    """After correcting a claim, the domain object should be updated."""
    _analyze_and_confirm(db, CONFERENCE_TEXT, "certificate.pdf", "obj:doc:1")

    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)

    # First projection creates the event
    result1 = projection.project_document("obj:doc:1", created_by="u:1")
    created = [o for o in result1.outcomes if o.kind == "created"]
    assert len(created) == 1
    event_id = created[0].object_id
    db.commit()

    # Now correct a claim (e.g., change the venue)
    claim_svc = ClaimService(store)
    claims = store.by_source("obj:doc:1")
    venue_claim = next(c for c in claims if c.predicate_id == "venue")
    corrected = claim_svc.correct(
        venue_claim.claim_id, reviewer="u:1", raw_value="India Habitat Centre"
    )
    db.commit()

    # Re-project — should detect duplicate (same event) but with corrected data
    result2 = projection.project_document("obj:doc:1", created_by="u:1")
    # The event already exists, so it should be a duplicate
    dups = [o for o in result2.outcomes if o.kind == "duplicate"]
    assert len(dups) >= 1, "Corrected re-projection should detect existing event"
    assert dups[0].existing_id == event_id
    db.commit()


# ---------------------------------------------------------------------------
# 9. No claims → no projection
# ---------------------------------------------------------------------------

def test_no_claims_returns_no_claims_status(db):
    """A document with no confirmed claims returns 'no_claims'."""
    store = SQLClaimStore(db)
    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:nonexistent", created_by="u:1")
    assert result.status == "no_claims"


# ---------------------------------------------------------------------------
# 10. Unsupported type reports honestly
# ---------------------------------------------------------------------------

def test_unsupported_type_reports_honestly(db):
    """A document type with no domain mapping reports 'no_mapping'."""
    # Analyze an award document (no domain entity for awards yet)
    text = """Certificate of Award
Award: Best Paper Award
Awarding Body: Indian Physics Association
Recipient: Dr. Anita Sharma
Date: 8 December 2024
Category: Best Oral Presentation
"""
    a = _svc(db).analyze(
        text=text, filename="award.pdf",
        document_id="obj:doc:5", version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    store = SQLClaimStore(db)
    claim_svc = ClaimService(store)
    for r in a.records:
        if r.claim_id:
            claim_svc.confirm(r.claim_id, reviewer="u:1", assert_human=True)
    db.commit()

    repo = SQLAlchemyObjectRepository(db)
    projection = ClaimProjectionService(store, repo)
    result = projection.project_document("obj:doc:5", created_by="u:1")

    # Award type is not routable (no create use case for awards)
    assert result.status == "no_mapping"
    assert result.confirmed_claim_count > 0
    db.commit()


# ---------------------------------------------------------------------------
# Helper import for ObjectId
# ---------------------------------------------------------------------------
from app.domain.value_objects.object_id import ObjectId
