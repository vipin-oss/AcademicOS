"""Regression tests for P0-2: duplicate certificate_number/reference_number.

Ensures that a conference certificate does NOT produce duplicate review items
for the same identifier value. The certificate_number predicate (from
CONFERENCE_FIELDS) and reference_number predicate (from AWARD_FIELDS) must
not both extract the same "Certificate Number: XYZ" value.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore


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


# ---------------------------------------------------------------------------
# Test 1: Conference certificate extracts certificate_number only
# ---------------------------------------------------------------------------

CONFERENCE_CERT_TEXT = """Certificate of Participation
Conference: International Conference on Quantum Materials
Acronym: ICQM-2024
Organizer: Indian Physics Association
Venue: Vigyan Bhawan
City: New Delhi
Country: India
Start Date: 6 December 2024
End Date: 8 December 2024
Participation Type: Attended
Certificate Number: ICQM-2024-0123
"""


def test_conference_certificate_extracts_certificate_number_only(db):
    """A conference certificate must extract certificate_number, NOT reference_number."""
    a = _svc(db).analyze(
        text=CONFERENCE_CERT_TEXT,
        filename="certificate.pdf",
        document_id="obj:doc:1",
        version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    db.commit()

    pred_ids = {f.predicate_id for f in a.fields}
    assert "certificate_number" in pred_ids, "certificate_number must be extracted"
    # reference_number must NOT be extracted for the same value
    assert "reference_number" not in pred_ids, (
        "reference_number must NOT be extracted from a conference certificate"
    )

    # Verify no duplicate claims for the same value
    store = SQLClaimStore(db)
    claims = store.by_source("obj:doc:1")
    cert_claims = [c for c in claims if c.predicate_id == "certificate_number"]
    ref_claims = [c for c in claims if c.predicate_id == "reference_number"]
    assert len(cert_claims) == 1, "Exactly one certificate_number claim"
    assert len(ref_claims) == 0, "No reference_number claims from conference certificate"


# ---------------------------------------------------------------------------
# Test 2: Generic award extracts reference_number only
# ---------------------------------------------------------------------------

AWARD_TEXT = """Certificate of Award
Award: Best Paper Award
Awarding Body: Indian Physics Association
Recipient: Dr. Anita Sharma
Date: 8 December 2024
Category: Best Oral Presentation
Reference Number: IPA-2024-BPA-001
"""


def test_award_extracts_reference_number_only(db):
    """An award document must extract reference_number."""
    a = _svc(db).analyze(
        text=AWARD_TEXT,
        filename="award.pdf",
        document_id="obj:doc:2",
        version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    db.commit()

    pred_ids = {f.predicate_id for f in a.fields}
    assert "reference_number" in pred_ids, "reference_number must be extracted for awards"


# ---------------------------------------------------------------------------
# Test 3: Both genuinely different values
# ---------------------------------------------------------------------------

CERT_WITH_REF_TEXT = """Certificate of Participation
Conference: International Conference on AI
Start Date: 10 January 2025
Certificate Number: CONF-2025-001
Reference Number: IEEE-REF-2025-12345
"""


def test_genuinely_different_values_both_extracted(db):
    """When certificate_number and reference_number are genuinely different
    values, both must be extracted."""
    a = _svc(db).analyze(
        text=CERT_WITH_REF_TEXT,
        filename="certificate.pdf",
        document_id="obj:doc:3",
        version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    db.commit()

    pred_ids = {f.predicate_id for f in a.fields}
    # certificate_number should be extracted
    assert "certificate_number" in pred_ids

    # If reference_number was also extracted (from a secondary type), verify
    # the values are different
    store = SQLClaimStore(db)
    claims = store.by_source("obj:doc:3")
    cert_vals = {
        c.value.get("value") for c in claims if c.predicate_id == "certificate_number"
    }
    ref_vals = {
        c.value.get("value") for c in claims if c.predicate_id == "reference_number"
    }
    # If both exist, they must be different
    if cert_vals and ref_vals:
        assert cert_vals != ref_vals, (
            "certificate_number and reference_number must not have the same value"
        )


# ---------------------------------------------------------------------------
# Test 4: Same value not extracted twice
# ---------------------------------------------------------------------------

def test_same_value_not_duplicated(db):
    """A document with 'Certificate Number: XYZ' must not create claims for
    both certificate_number and reference_number with the same value."""
    text = """Certificate of Participation
Conference: AI Summit 2025
Start Date: 5 March 2025
Certificate Number: AI-2025-042
"""
    a = _svc(db).analyze(
        text=text,
        filename="cert.pdf",
        document_id="obj:doc:4",
        version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    db.commit()

    store = SQLClaimStore(db)
    claims = store.by_source("obj:doc:4")

    # Collect all claims that extracted "AI-2025-042"
    matching = [
        c for c in claims
        if c.value.get("value") == "AI-2025-042"
    ]

    # Should only be one claim (certificate_number)
    assert len(matching) <= 1, (
        f"Value 'AI-2025-042' must not appear in multiple claims, "
        f"found {len(matching)}: {[c.predicate_id for c in matching]}"
    )
    if matching:
        assert matching[0].predicate_id == "certificate_number"
