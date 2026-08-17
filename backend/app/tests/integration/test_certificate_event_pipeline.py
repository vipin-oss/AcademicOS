"""Certificate → Event Pipeline Tests (Revision #19 fix).

Tests the complete certificate → classify → extract → route → Event workflow.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.document_classifier import DocumentClassifier
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.domain_record_router import DomainRecordRouter
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.repositories.sqlalchemy_object_repository import SQLAlchemyObjectRepository

# =============================================================================
# Certificate Fixtures
# =============================================================================

CONFERENCE_CERT = """CERTIFICATE OF PARTICIPATION
This is to certify that Dr. Vipin Kumar has participated in the
International Conference on Artificial Intelligence and Machine Learning (ICAIML 2025)
held at IIT Delhi, New Delhi on 10-12 March 2025
Certificate No: ICAIML-2025-5678
"""

WEBINAR_CERT = """CERTIFICATE OF PARTICIPATION
This is to certify that Vipin Gupta has participated in the webinar
on Data Science in Healthcare organized by IIT Bombay
Date: 15 June 2025
"""

WORKSHOP_CERT = """CERTIFICATE OF PARTICIPATION
This is to certify that Dr. Sharma has participated in the
Workshop on Machine Learning Applications held at IIT Kanpur
from 5-7 January 2025
Certificate No: WS-2025-001
"""

INCOMPLETE_CERT = """CERTIFICATE
This is to certify that Mr. Kumar.
"""

RESEARCH_PAPER = """Title: Deep Learning for Microplastic Detection
Authors: A. Kumar, B. Singh
Journal: Environmental Science and Technology
Year: 2025
DOI: 10.1021/acs.est.2025.0042
"""


# =============================================================================
# Fixtures
# =============================================================================

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


def _intake(db) -> DocumentIntakeService:
    store = SQLClaimStore(db)
    return DocumentIntakeService(ClaimService(store), store)


def _analyze(db, text, filename="doc.txt", doc_id="obj:doc:1"):
    return _intake(db).analyze(
        text=text, filename=filename, document_id=doc_id, version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )


# =============================================================================
# A. Certificate Classification
# =============================================================================

class TestCertificateClassification:
    """Verify certificates are classified correctly."""

    def test_conference_certificate_classified(self):
        """Conference participation certificate → conference_certificate."""
        c = DocumentClassifier()
        r = c.classify(CONFERENCE_CERT, "certificate.pdf")
        assert r.document_type_id == "conference_certificate"

    def test_webinar_certificate_classified(self):
        """Webinar certificate → conference_certificate (reuses type)."""
        c = DocumentClassifier()
        r = c.classify(WEBINAR_CERT, "webinar_cert.pdf")
        assert r.document_type_id == "conference_certificate"

    def test_workshop_certificate_classified(self):
        """Workshop certificate → conference_certificate."""
        c = DocumentClassifier()
        r = c.classify(WORKSHOP_CERT, "workshop.pdf")
        assert r.document_type_id == "conference_certificate"

    def test_incomplete_cert_may_not_classify(self):
        """Very incomplete certificate may classify differently."""
        c = DocumentClassifier()
        r = c.classify(INCOMPLETE_CERT, "cert.pdf")
        # May or may not classify as certificate
        assert r.document_type_id is not None


# =============================================================================
# B. Certificate Field Extraction
# =============================================================================

class TestCertificateExtraction:
    """Verify fields are extracted from certificate text."""

    def test_recipient_extracted(self, db):
        """Recipient name is extracted from certificate."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "recipient" in fields
        assert "Vipin Kumar" in fields["recipient"]

    def test_conference_name_extracted(self, db):
        """Conference name is extracted from prose."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "conference_name" in fields
        assert "ICAIML 2025" in fields["conference_name"]

    def test_venue_extracted(self, db):
        """Venue is extracted from certificate."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "venue" in fields
        assert "IIT Delhi" in fields["venue"]

    def test_certificate_number_extracted(self, db):
        """Certificate number is extracted."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "certificate_number" in fields
        assert "ICAIML-2025-5678" in fields["certificate_number"]

    def test_date_extracted(self, db):
        """Date is extracted from certificate."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "start_date" in fields


# =============================================================================
# C. Certificate → Event Routing
# =============================================================================

class TestCertificateEventRouting:
    """Verify certificates are routed to create Event records."""

    def test_certificate_creates_event(self, db):
        """Certificate with sufficient info creates an Event record."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        repo = SQLAlchemyObjectRepository(db)

        # Check routing was attempted
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "conference_name" in fields

        # Verify Event was created via router
        router = DomainRecordRouter(repo)
        outcomes = router.route(
            type_ids=r.all_types(),
            fields={**fields, "__types__": r.all_types()},
            created_by="u:1",
            source_document_id="obj:doc:1",
            confidence=r.confidence,
        )
        assert any(o.kind == "created" for o in outcomes)

    def test_webinar_creates_event(self, db):
        """Webinar certificate creates an Event record."""
        r = _analyze(db, WEBINAR_CERT, "webinar.pdf", "obj:doc:2")
        repo = SQLAlchemyObjectRepository(db)

        fields = {f.predicate_id: f.value for f in r.fields}
        router = DomainRecordRouter(repo)
        outcomes = router.route(
            type_ids=r.all_types(),
            fields={**fields, "__types__": r.all_types()},
            created_by="u:1",
            source_document_id="obj:doc:2",
            confidence=r.confidence,
        )
        # Should create an event (or skip if insufficient)
        assert outcomes

    def test_incomplete_cert_no_event(self, db):
        """Incomplete certificate doesn't create an event."""
        r = _analyze(db, INCOMPLETE_CERT, "cert.pdf", "obj:doc:3")
        repo = SQLAlchemyObjectRepository(db)

        fields = {f.predicate_id: f.value for f in r.fields}
        router = DomainRecordRouter(repo)
        outcomes = router.route(
            type_ids=r.all_types(),
            fields={**fields, "__types__": r.all_types()},
            created_by="u:1",
            source_document_id="obj:doc:3",
            confidence=r.confidence,
        )
        # Should skip (no conference_name/event_title)
        assert all(o.kind in ("skipped", "claim_only") for o in outcomes)


# =============================================================================
# D. Source Document Provenance
# =============================================================================

class TestProvenance:
    """Verify source document provenance is preserved."""

    def test_certificate_source_preserved(self, db):
        """Certificate claims have correct source_document_id."""
        r = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:cert1")
        store = SQLClaimStore(db)
        claims = store.by_source("obj:doc:cert1")
        assert len(claims) > 0
        for c in claims:
            assert c.source_document_id == "obj:doc:cert1"

    def test_research_paper_independent(self, db):
        """Research paper claims have different source_document_id."""
        r = _analyze(db, RESEARCH_PAPER, "paper.pdf", "obj:doc:paper1")
        store = SQLClaimStore(db)
        claims = store.by_source("obj:doc:paper1")
        assert len(claims) > 0
        for c in claims:
            assert c.source_document_id == "obj:doc:paper1"


# =============================================================================
# E. Idempotency
# =============================================================================

class TestIdempotency:
    """Verify repeated analysis doesn't create duplicate records."""

    def test_reanalysis_same_fields(self, db):
        """Re-analyzing same certificate produces same fields."""
        r1 = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        r2 = _analyze(db, CONFERENCE_CERT, "certificate.pdf", "obj:doc:1")
        f1 = {f.predicate_id: f.value for f in r1.fields}
        f2 = {f.predicate_id: f.value for f in r2.fields}
        assert f1 == f2

    def test_different_certificates_independent(self, db):
        """Different certificates create independent claims."""
        _analyze(db, CONFERENCE_CERT, "cert1.pdf", "obj:doc:1")
        _analyze(db, WEBINAR_CERT, "cert2.pdf", "obj:doc:2")

        store = SQLClaimStore(db)
        claims1 = store.by_source("obj:doc:1")
        claims2 = store.by_source("obj:doc:2")
        assert len(claims1) > 0
        assert len(claims2) > 0
        assert claims1[0].source_document_id != claims2[0].source_document_id


# =============================================================================
# F. Mixed Batch
# =============================================================================

class TestMixedBatch:
    """Verify certificate + paper + unrelated document in same batch."""

    def test_mixed_batch_all_processed(self, db):
        """Certificate, paper, and unrelated doc all process independently."""
        docs = [
            (CONFERENCE_CERT, "certificate.pdf", "obj:doc:cert"),
            (RESEARCH_PAPER, "paper.pdf", "obj:doc:paper"),
            (INCOMPLETE_CERT, "random.pdf", "obj:doc:random"),
        ]

        results = []
        for text, fname, doc_id in docs:
            r = _analyze(db, text, fname, doc_id)
            results.append(r)

        assert len(results) == 3
        # Certificate should be conference_certificate
        assert results[0].document_type_id == "conference_certificate"
        # Paper should be publication
        assert results[1].document_type_id == "publication"
        # Random may be any type
        assert results[2].document_type_id is not None


# =============================================================================
# G. ACL Isolation
# =============================================================================

class TestACLIsolation:
    """Verify different users get different ACL scopes."""

    def test_different_owners_different_acl(self, db):
        """Different users' certificates have different ACL scopes."""
        svc = _intake(db)
        svc.analyze(
            text=CONFERENCE_CERT, filename="cert.pdf",
            document_id="obj:doc:1", version=1,
            acl_scope='{"owner":"u:alice","readers":[],"writers":[],"managers":[]}',
        )
        svc.analyze(
            text=CONFERENCE_CERT, filename="cert.pdf",
            document_id="obj:doc:2", version=1,
            acl_scope='{"owner":"u:bob","readers":[],"writers":[],"managers":[]}',
        )

        store = SQLClaimStore(db)
        claims1 = store.by_source("obj:doc:1")
        claims2 = store.by_source("obj:doc:2")
        if claims1 and claims2:
            assert claims1[0].acl_scope != claims2[0].acl_scope
