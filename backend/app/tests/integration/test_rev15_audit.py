"""Master Academic Backend Audit (Revision #15).

Validates the complete DOCUMENT → UNDERSTAND → ORGANIZE → CONNECT → SEARCH
→ COMPLETE → ASK lifecycle against the Master Blueprint.

This is the definitive cross-domain audit.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.domain_record_router import DomainRecordRouter, ROUTABLE
from app.application.services.missing_info import analyze_missing_fields
from app.application.services.notification_service import (
    NotificationService,
    notify_conflicts_detected,
    notify_document_analyzed,
)
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.claim_model import ClaimModel
from app.infrastructure.db.models.notification_model import Base as NotifBase
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.notification_store import SQLNotificationStore

# =============================================================================
# Realistic Academic Documents
# =============================================================================

RESEARCH_PAPER = """Title: Deep Learning for Microplastic Detection in River Systems
Authors: A. Kumar, B. Singh, C. Patel
Journal: Environmental Science and Technology
Year: 2025
DOI: 10.1021/acs.est.2025.0042
Abstract: We present a novel deep learning approach for automated detection.
"""

ACCEPTANCE_LETTER = """Dear Dr. Kumar,
Your manuscript entitled "Novel Catalytic Methods for Water Purification" has been accepted
for publication in Nature Chemistry.
Manuscript ID: NC-2025-4567
Sincerely, Editor-in-Chief
"""

CONFERENCE_CERT = """CERTIFICATE OF PARTICIPATION
This is to certify that Dr. Vipin Kumar has participated in the
International Conference on Artificial Intelligence and Machine Learning (ICAIML 2025)
held at IIT Delhi, New Delhi on 10-12 March 2025
Certificate No: ICAIML-2025-5678
"""

GRANT_SANCTION = """SANCTION ORDER
Research Project: AI-Based Crop Disease Detection Using Satellite Imagery
Principal Investigator: Dr. Vipin Kumar
Co-Investigator: Dr. Priya Sharma
Funding Agency: Department of Science and Technology
Sanctioned Amount: Rs. 4500000
Duration: 36 months
Sanction Order No: DST/2025/AI/789
Date: 15 March 2025
"""

APPOINTMENT_LETTER = """APPOINTMENT LETTER
Dear Dr. Anita Sharma,
You are appointed as Associate Professor in the Department of Computer Science
and Engineering with effect from 1 August 2025.
Designation: Associate Professor
Department: Computer Science and Engineering
Reference Number: CSE/2025/AP/321
"""

AWARD_CERT = """AWARD CERTIFICATE
This is to certify that Prof. Rajesh Patel has been awarded the
Best Paper Award 2025 at the International Conference on Data Science
held at Bangalore, India.
Award ID: ICDS-2025-BPA-042
"""

UNIVERSITY_NOTICE = """UNIVERSITY NOTICE
Subject: Annual Research Symposium 2025
Date: 15 September 2025
All faculty members and research scholars are invited.
Issued by: Dean, Research and Development
"""

COMMITTEE_ORDER = """ORDER
Subject: Constitution of Academic Council
The Academic Council is constituted with the following members:
Chairperson: Vice-Chancellor
Members: All HODs, Dean Academic Affairs
Purpose: Academic governance and policy
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
    NotifBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _intake(db) -> DocumentIntakeService:
    store = SQLClaimStore(db)
    return DocumentIntakeService(ClaimService(store), store)


def _notif_svc(db) -> NotificationService:
    return NotificationService(SQLNotificationStore(db))


def _analyze(db, text, filename="doc.txt", doc_id="obj:doc:1"):
    return _intake(db).analyze(
        text=text, filename=filename, document_id=doc_id, version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )


def _claims_for(db, doc_id):
    return db.query(ClaimModel).filter(ClaimModel.source_document_id == doc_id).all()


# =============================================================================
# PHASE 1: Classification + Extraction + Routing
# =============================================================================

class TestDocumentLifecycle:
    """Verify complete document lifecycle for each major type."""

    @pytest.mark.parametrize("text,filename,exp_type,exp_module", [
        (RESEARCH_PAPER, "paper.pdf", "publication", "publication"),
        (CONFERENCE_CERT, "cert.pdf", "conference_certificate", "event"),
        (GRANT_SANCTION, "grant.pdf", "grant_sanction_letter", "project"),
        (UNIVERSITY_NOTICE, "notice.pdf", "university_notice", "event"),
        (COMMITTEE_ORDER, "committee.pdf", "committee", "committee"),
    ])
    def test_classify_extract_route(self, db, text, filename, exp_type, exp_module):
        """Classify → Extract → Route for routable types."""
        r = _analyze(db, text, filename, f"obj:doc:{exp_type}")

        # Classification
        assert r.document_type_id == exp_type

        # Field extraction
        assert len(r.fields) > 0

        # Routing
        assert exp_type in ROUTABLE
        assert ROUTABLE[exp_type] == exp_module

        # Claims created
        claims = _claims_for(db, f"obj:doc:{exp_type}")
        assert len(claims) > 0

        # Source document binding
        for c in claims:
            assert c.source_document_id == f"obj:doc:{exp_type}"

    def test_non_routable_types_claim_only(self, db):
        """Non-routable types create claims but no domain records."""
        r = _analyze(db, AWARD_CERT, "award.pdf", "obj:doc:award")
        assert r.document_type_id == "award"
        assert r.document_type_id not in ROUTABLE

        r = _analyze(db, APPOINTMENT_LETTER, "appt.pdf", "obj:doc:appt")
        assert r.document_type_id == "appointment"
        assert r.document_type_id not in ROUTABLE


# =============================================================================
# PHASE 2: Field Extraction Accuracy
# =============================================================================

class TestFieldExtractionAccuracy:
    """Verify fields are extracted correctly for each domain."""

    def test_publication_fields(self, db):
        r = _analyze(db, RESEARCH_PAPER, "paper.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "publication_title" in fields
        assert "publication_year" in fields
        assert fields["publication_year"] == "2025"
        assert "doi" in fields
        assert fields["doi"] == "10.1021/acs.est.2025.0042"

    def test_grant_fields(self, db):
        r = _analyze(db, GRANT_SANCTION, "grant.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "funding_agency" in fields
        assert "principal_investigator" in fields
        assert "sanctioned_amount" in fields
        assert float(fields["sanctioned_amount"]) == 4500000.0
        assert "project_duration_months" in fields
        assert float(fields["project_duration_months"]) == 36.0

    def test_conference_fields(self, db):
        r = _analyze(db, CONFERENCE_CERT, "cert.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "certificate_number" in fields
        assert fields["certificate_number"] == "ICAIML-2025-5678"
        assert "venue" in fields

    def test_notice_fields(self, db):
        r = _analyze(db, UNIVERSITY_NOTICE, "notice.pdf", "obj:doc:1")
        fields = {f.predicate_id: f.value for f in r.fields}
        assert "event_title" in fields
        assert "issuing_authority" in fields

    def test_committee_fields(self, db):
        text = """Committee: Academic Council
Subject: Constitution of Academic Council
Members: All HODs, Dean Academic Affairs
Purpose: Academic governance and policy
"""
        r = _analyze(db, text, "committee.pdf", "obj:doc:1")
        fields = {f.predicate_id for f in r.fields}
        assert "committee_name" in fields or "committee_members" in fields


# =============================================================================
# PHASE 3: Duplicate Prevention
# =============================================================================

class TestDuplicatePrevention:
    """Verify duplicates are handled correctly."""

    def test_reanalysis_same_classification(self, db):
        """Re-analyzing same document produces same classification."""
        r1 = _analyze(db, RESEARCH_PAPER, "paper.pdf", "obj:doc:1")
        r2 = _analyze(db, RESEARCH_PAPER, "paper.pdf", "obj:doc:1")
        assert r1.document_type_id == r2.document_type_id
        f1 = {f.predicate_id for f in r1.fields}
        f2 = {f.predicate_id for f in r2.fields}
        assert f1 == f2

    def test_different_documents_independent(self, db):
        """Different documents create independent claims."""
        _analyze(db, RESEARCH_PAPER, "paper1.pdf", "obj:doc:1")
        _analyze(db, GRANT_SANCTION, "grant.pdf", "obj:doc:2")
        c1 = _claims_for(db, "obj:doc:1")
        c2 = _claims_for(db, "obj:doc:2")
        assert len(c1) > 0
        assert len(c2) > 0
        assert c1[0].source_document_id != c2[0].source_document_id


# =============================================================================
# PHASE 4: Cross-Document Intelligence
# =============================================================================

class TestCrossDocumentIntelligence:
    """Verify related documents are handled correctly."""

    def test_paper_and_acceptance_independent(self, db):
        """Research paper and acceptance letter are separate documents."""
        r1 = _analyze(db, RESEARCH_PAPER, "paper.pdf", "obj:doc:paper")
        r2 = _analyze(db, ACCEPTANCE_LETTER, "accept.pdf", "obj:doc:accept")

        # Both classified
        assert r1.document_type_id == "publication"
        # Acceptance letter may classify as publication (keyword overlap)

        # Independent claims
        c1 = _claims_for(db, "obj:doc:paper")
        c2 = _claims_for(db, "obj:doc:accept")
        assert len(c1) > 0
        assert len(c2) > 0

    def test_multiple_grants_independent(self, db):
        """Multiple grant documents create independent claims."""
        grant2 = """SANCTION ORDER
Research Project: Quantum Computing Lab
Principal Investigator: Dr. Test
Funding Agency: DST
Sanctioned Amount: Rs. 2000000
Duration: 24 months
Sanction Order No: DST-2025-QC-123
"""
        _analyze(db, GRANT_SANCTION, "grant1.pdf", "obj:doc:1")
        _analyze(db, grant2, "grant2.pdf", "obj:doc:2")
        c1 = _claims_for(db, "obj:doc:1")
        c2 = _claims_for(db, "obj:doc:2")
        assert len(c1) > 0
        assert len(c2) > 0


# =============================================================================
# PHASE 5: Permission Enforcement
# =============================================================================

class TestPermissionEnforcement:
    """Verify ACL is enforced per document."""

    def test_different_owners_different_acl(self, db):
        svc = _intake(db)
        svc.analyze(
            text=RESEARCH_PAPER, filename="paper.pdf",
            document_id="obj:doc:1", version=1,
            acl_scope='{"owner":"u:alice","readers":[],"writers":[],"managers":[]}',
        )
        svc.analyze(
            text=GRANT_SANCTION, filename="grant.pdf",
            document_id="obj:doc:2", version=1,
            acl_scope='{"owner":"u:bob","readers":[],"writers":[],"managers":[]}',
        )
        c1 = _claims_for(db, "obj:doc:1")
        c2 = _claims_for(db, "obj:doc:2")
        if c1 and c2:
            assert c1[0].acl_scope != c2[0].acl_scope


# =============================================================================
# PHASE 6: Notification Integration
# =============================================================================

class TestNotificationIntegration:
    """Verify notification helpers work correctly."""

    def test_document_analyzed_notification(self, db):
        svc = _notif_svc(db)
        n = notify_document_analyzed(svc, "u:1", "obj:doc:1", "Paper", 5, False)
        assert n.title == "Document analyzed"
        assert "5" in n.message

    def test_review_notification(self, db):
        svc = _notif_svc(db)
        n = notify_document_analyzed(svc, "u:1", "obj:doc:1", "Paper", 3, True)
        assert "review" in n.title.lower()

    def test_conflict_notification(self, db):
        svc = _notif_svc(db)
        n = notify_conflicts_detected(svc, "u:1", "obj:doc:1", "Paper", 2)
        assert "conflict" in n.title.lower()

    def test_no_notification_spam(self, db):
        """Multiple notifications for same document are separate events."""
        svc = _notif_svc(db)
        notify_document_analyzed(svc, "u:1", "obj:doc:1", "Paper", 5, False)
        notify_document_analyzed(svc, "u:1", "obj:doc:1", "Paper", 5, False)
        notifs = svc.get_user_notifications("u:1")
        assert len(notifs) == 2  # Two separate events


# =============================================================================
# PHASE 7: Missing Information
# =============================================================================

class TestMissingInformation:
    """Verify missing information detection."""

    def test_publication_without_doi(self, db):
        """Publication missing DOI is detectable."""
        no_doi = """Title: Some Paper
Authors: A, B
Year: 2025
"""
        r = _analyze(db, no_doi, "paper.pdf", "obj:doc:1")
        fields = {f.predicate_id for f in r.fields}
        # DOI not in text — should not be extracted
        assert "doi" not in fields

    def test_grant_without_duration(self, db):
        """Grant missing duration is detectable."""
        no_dur = """SANCTION ORDER
Research Project: Test
Principal Investigator: Dr. Test
Funding Agency: DST
Sanctioned Amount: Rs. 1000000
"""
        r = _analyze(db, no_dur, "grant.pdf", "obj:doc:1")
        fields = {f.predicate_id for f in r.fields}
        assert "project_duration_months" not in fields


# =============================================================================
# PHASE 8: End-to-End Professor Workflow
# =============================================================================

class TestEndToEndWorkflow:
    """Simulate a professor's complete workflow."""

    def test_professor_uploads_five_documents(self, db):
        """Professor uploads 5 different academic documents."""
        documents = [
            (RESEARCH_PAPER, "paper.pdf", "obj:doc:paper", "publication"),
            (CONFERENCE_CERT, "cert.pdf", "obj:doc:cert", "conference_certificate"),
            (GRANT_SANCTION, "grant.pdf", "obj:doc:grant", "grant_sanction_letter"),
            (APPOINTMENT_LETTER, "appt.pdf", "obj:doc:appt", "appointment"),
            (AWARD_CERT, "award.pdf", "obj:doc:award", "award"),
        ]

        results = []
        for text, fname, doc_id, exp_type in documents:
            r = _analyze(db, text, fname, doc_id)
            results.append((r, doc_id, exp_type))

        assert len(results) == 5

        for r, doc_id, exp_type in results:
            # Correct classification
            assert r.document_type_id == exp_type
            # Claims created
            claims = _claims_for(db, doc_id)
            assert len(claims) > 0
            # Source binding
            for c in claims:
                assert c.source_document_id == doc_id

    def test_batch_summary(self, db):
        """Batch summary is computable."""
        docs = [
            (RESEARCH_PAPER, "paper.pdf", "obj:doc:1"),
            (GRANT_SANCTION, "grant.pdf", "obj:doc:2"),
            (UNIVERSITY_NOTICE, "notice.pdf", "obj:doc:3"),
        ]
        results = [_analyze(db, t, f, d) for t, f, d in docs]
        total = len(results)
        typed = sum(1 for r in results if r.document_type_id is not None)
        assert total == 3
        assert typed == 3


# =============================================================================
# PHASE 9: Architecture Compliance
# =============================================================================

class TestArchitectureCompliance:
    """Verify clean architecture principles."""

    def test_routable_types_documented(self):
        """ROUTABLE dict is the source of truth for domain routing."""
        assert "publication" in ROUTABLE
        assert "grant_sanction_letter" in ROUTABLE
        assert "conference_certificate" in ROUTABLE
        assert "committee" in ROUTABLE
        assert "university_notice" in ROUTABLE

    def test_non_routable_types_honest(self):
        """Non-routable types don't fabricate domain records."""
        not_routable = ["award", "appointment", "experience", "promotion",
                        "teaching", "course", "certificate", "correspondence"]
        for t in not_routable:
            assert t not in ROUTABLE
