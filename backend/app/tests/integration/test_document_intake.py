"""V3 ADR-067 document-intake pipeline tests (upload -> understand -> records).

Covers the acceptance criteria: conference/publication/award/sanction/committee
classification + extraction, duplicate + conflict handling, low-confidence
honesty, value normalization, deterministic-no-AI, and permission-scoped
acl_scope propagation. All deterministic (no LLM, no network).
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.value_normalizer import (
    normalize_amount,
    normalize_date,
    normalize_doi,
)
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore

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

AWARD_TEXT = """Certificate of Award
Award: Best Paper Award
Awarding Body: Indian Physics Association
Recipient: Dr. Anita Sharma
Date: 8 December 2024
Category: Best Oral Presentation
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


def _analyze(db, text, filename="doc.pdf", document_id="obj:document:1"):
    return _svc(db).analyze(
        text=text, filename=filename, document_id=document_id, version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )


def _claims_by_predicate(db, predicate_id):
    return SQLClaimStore(db).confirmed_by_predicate(predicate_id)


# ---------------------------------------------------------------------------
# A. Conference
# ---------------------------------------------------------------------------

def test_conference_classify_and_extract(db):
    a = _analyze(db, CONFERENCE_TEXT, filename="conference.pdf")
    assert a.document_type_id == "conference"
    assert a.confidence > 0.5
    assert a.target_module == "research"
    field_preds = {f.predicate_id for f in a.fields}
    assert "conference_name" in field_preds
    assert "start_date" in field_preds and "end_date" in field_preds
    assert "certificate_number" in field_preds

    db.commit()
    # structured records are claims bound to the source document
    by_source = SQLClaimStore(db).by_source("obj:document:1")
    assert any(c.predicate_id == "conference_name" for c in by_source)
    # start/end dates normalized to ISO
    start = next(c for c in by_source if c.predicate_id == "start_date")
    assert start.value.get("value") == "2024-12-06"


def test_conference_certificate_has_multiple_types(db):
    a = _analyze(db, CONFERENCE_TEXT, filename="certificate.pdf")
    # A certificate of participation matches several types; "conference" must
    # be among the matched types (primary or secondary).
    all_types = a.all_types()
    assert "conference" in all_types
    assert len(all_types) > 1  # genuinely multi-type


# ---------------------------------------------------------------------------
# B. Publication
# ---------------------------------------------------------------------------

def test_publication_extracts_doi(db):
    a = _analyze(db, PUBLICATION_TEXT, filename="article.pdf")
    assert a.document_type_id in ("publication", "journal_article")
    assert a.target_module == "publications"
    preds = {f.predicate_id: f.value for f in a.fields}
    assert preds.get("publication_title") == "A Study of Quantum Dots"
    assert preds.get("doi") == "10.1000/xyz123"


# ---------------------------------------------------------------------------
# C. Award
# ---------------------------------------------------------------------------

def test_award_extracts(db):
    a = _analyze(db, AWARD_TEXT, filename="award.pdf")
    assert a.document_type_id == "award"
    assert a.target_module == "faculty"
    preds = {f.predicate_id: f.value for f in a.fields}
    assert preds.get("award_title") == "Best Paper Award"


# ---------------------------------------------------------------------------
# D. Sanction letter -> project/grant
# ---------------------------------------------------------------------------

def test_sanction_letter_extracts_amount(db):
    a = _analyze(db, SANCTION_TEXT, filename="sanction_letter.pdf")
    assert a.document_type_id == "grant_sanction_letter"
    preds = {f.predicate_id: f.value for f in a.fields}
    assert preds.get("funding_agency") == "SERB"
    assert preds.get("sanctioned_amount") == 5000000.0
    assert preds.get("project_title") == "Energy Storage Materials"


# ---------------------------------------------------------------------------
# E. Committee
# ---------------------------------------------------------------------------

def test_committee_extracts(db):
    a = _analyze(db, COMMITTEE_TEXT, filename="order.pdf")
    # An office order constituting a committee: office_order is primary, but
    # the committee fields must still be extracted via the secondary type.
    assert "committee" in a.all_types()
    preds = {f.predicate_id: f.value for f in a.fields}
    assert preds.get("committee_name") == "Departmental Research Committee"
    assert preds.get("order_number") == "OO/2024/DRC/05"


# ---------------------------------------------------------------------------
# F/K. Duplicate / re-upload -> no duplicate record
# ---------------------------------------------------------------------------

def test_duplicate_does_not_create_new_record(db):
    # First analysis proposes + confirm (simulate existing confirmed fact).
    a = _analyze(db, CONFERENCE_TEXT, filename="conference.pdf", document_id="obj:document:1")
    store = SQLClaimStore(db)
    for r in a.records:
        if r.claim_id:
            store.set_status(r.claim_id, ClaimStatus.CONFIRMED)
    db.commit()

    # Re-upload the SAME content as a new document -> duplicate detection.
    a2 = _analyze(db, CONFERENCE_TEXT, filename="conference.pdf", document_id="obj:document:2")
    assert a2.duplicates, "re-upload must detect the existing confirmed facts"
    # No new claims written for duplicated facts
    new = [r for r in a2.records if r.status != "skipped"]
    assert not new, new


# ---------------------------------------------------------------------------
# G. Conflict
# ---------------------------------------------------------------------------

def test_conflict_does_not_overwrite(db):
    a = _analyze(db, CONFERENCE_TEXT, filename="conference.pdf", document_id="obj:document:1")
    store = SQLClaimStore(db)
    # Confirm the start_date, then a DIFFERENT document claims another date.
    for r in a.records:
        if r.predicate_id == "start_date" and r.claim_id:
            store.set_status(r.claim_id, ClaimStatus.CONFIRMED)
    db.commit()

    conflicting = CONFERENCE_TEXT.replace("6 December 2024", "7 December 2024")
    a2 = _analyze(db, conflicting, filename="conference2.pdf", document_id="obj:document:2")
    # Cross-document conflicts are intentionally NOT flagged (different documents
    # naturally have different dates/venues/recipients). Only same-document value
    # changes are conflicts (handled by the claim lifecycle via supersede).
    assert not a2.conflicts, "cross-document differences are normal, not conflicts"
    # review_required is False because all claims are auto_suggested (high confidence)
    # and cross-document differences are not conflicts
    assert a2.review_required is False
    # The new date IS written as a new claim (different document = different fact)
    new_start = [r for r in a2.records if r.predicate_id == "start_date" and r.status != "skipped"]
    assert new_start, "new document's date should be written as a new claim"


# ---------------------------------------------------------------------------
# H. Low-confidence / unknown
# ---------------------------------------------------------------------------

def test_unknown_document_writes_nothing(db):
    a = _analyze(db, "The quick brown fox jumps over the lazy dog.", filename="notes.txt")
    assert a.document_type_id is None or a.status == "unknown"
    assert SQLClaimStore(db).by_source("obj:document:1") == []


# ---------------------------------------------------------------------------
# I. Unreadable / empty text
# ---------------------------------------------------------------------------

def test_empty_text_is_honest(db):
    a = _analyze(db, "", filename="blank.pdf")
    assert a.status == "unknown"
    assert a.fields == () and a.records == ()


# ---------------------------------------------------------------------------
# Value normalization (deterministic)
# ---------------------------------------------------------------------------

def test_value_normalizers():
    assert normalize_date("6 December 2024") == "2024-12-06"
    assert normalize_date("2024-12-06") == "2024-12-06"
    assert normalize_date("31 February 2024") is None  # impossible date
    assert normalize_doi("see https://doi.org/10.1000/xyz123 ref") == "10.1000/xyz123"
    assert normalize_amount("Rs. 50,00,000") == 5000000.0


# ---------------------------------------------------------------------------
# J. Permission isolation: acl_scope propagated to every claim
# ---------------------------------------------------------------------------

def test_acl_scope_propagated(db):
    _analyze(db, CONFERENCE_TEXT, filename="conference.pdf", document_id="obj:document:1")
    db.commit()
    scope = '{"owner":"u:1","readers":[],"writers":[],"managers":[]}'
    for claim in SQLClaimStore(db).by_source("obj:document:1"):
        assert claim.acl_scope == scope


# ---------------------------------------------------------------------------
# L. Deterministic (no AI dependency): extraction runs with no AI core wired
# ---------------------------------------------------------------------------

def test_no_ai_dependency(db):
    # The service takes only a claim service + store — no AI core, no gateway.
    import inspect

    import app.application.services.document_intake as mod

    src = inspect.getsource(mod)
    for forbidden in ("ai_core", "gateway", "openai", "ollama", "httpx"):
        assert forbidden not in src.lower()


# ---------------------------------------------------------------------------
# M. Structured records are retrievable + source-linked (grounded-AI contract)
# ---------------------------------------------------------------------------

def test_structured_record_retrievable_and_source_linked(db):
    a = _analyze(db, CONFERENCE_TEXT, filename="conference.pdf", document_id="obj:document:1")
    store = SQLClaimStore(db)
    for r in a.records:
        if r.claim_id and r.predicate_id == "conference_name":
            store.set_status(r.claim_id, ClaimStatus.CONFIRMED)
    db.commit()

    # A structured query ("what conferences have I attended") reads the
    # confirmed conference_name claim — bound to the source document.
    confirmed = store.confirmed_by_predicate("conference_name")
    assert confirmed, "confirmed conference record must be retrievable"
    claim, spans = confirmed[0]
    assert "Quantum Materials" in (claim.value.get("value") or "")
    assert claim.source_document_id == "obj:document:1"
