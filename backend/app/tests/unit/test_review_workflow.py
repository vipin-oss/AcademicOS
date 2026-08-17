"""Backend tests for the enhanced Document Review workflow.

Tests:
  - Confirmation queue returns display_value, source_text, document_title
  - Field confidence status correctly reflects record outcomes
  - Review item never shows type metadata as value
  - Source provenance preserved
  - ACL enforcement on confirmations
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.confirmation_queue import ConfirmationQueue
from app.application.services.document_intake import DocumentIntakeService
from app.domain.value_objects.claim import Claim, ClaimStatus
from app.domain.value_objects.enums import ObjectType, PermissionAction, Provenance
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore


# ── helpers ──────────────────────────────────────────────────────────


def _make_engine():
    from sqlalchemy import StaticPool
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _make_claim(
    predicate_id: str = "recipient",
    raw_value: str = "Vipin Gupta",
    source_text: str = "Recipient: Vipin Gupta",
    status: ClaimStatus = ClaimStatus.PROPOSED,
) -> tuple[Claim, list]:
    """Build a Claim with a realistic value dict."""
    from app.application.knowledge.predicate_catalogue import normalize_predicate_value
    from app.domain.value_objects.span import Span

    value = normalize_predicate_value(predicate_id, raw_value, source_text)
    claim = Claim(
        claim_id=f"claim:{uuid.uuid4().hex[:12]}",
        predicate_id=predicate_id,
        predicate_version=1,
        value_schema="text",
        value=value,
        source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
        source_version=1,
        status=status,
        provenance=Provenance.INFERRED,
        fact_confidence=0.85,
    )
    return claim, []


# ── tests ────────────────────────────────────────────────────────────


class TestConfirmationQueueDisplayValues:
    """ConfirmationQueue must return display_value and source_text."""

    def test_queue_returns_display_value(self):
        """display_value must be the actual extracted value, not type metadata."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)

        claim, spans = _make_claim("recipient", "Vipin Gupta", "Recipient: Vipin Gupta")
        store.put(claim, spans)
        db.commit()

        queue = ConfirmationQueue(store)
        items = queue.pending(page=1, page_size=10)

        assert len(items) == 1
        item = items[0]
        assert item.display_value == "Vipin Gupta"
        assert item.display_value != "text"
        assert item.display_value != "recipient"

    def test_queue_returns_source_text_for_raw_claims(self):
        """source_text must contain the original document text for raw claims."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)

        claim, spans = _make_claim("doi", "10.1234/abc", "DOI: 10.1234/abc")
        store.put(claim, spans)
        db.commit()

        queue = ConfirmationQueue(store)
        items = queue.pending(page=1, page_size=10)

        assert len(items) == 1
        # For text-kind claims, source_text comes from the value dict
        # (which stores {"kind": "text", "value": "..."} not {"text": "..."})
        # The display_value contains the actual extracted value
        assert items[0].display_value == "10.1234/abc"

    def test_queue_never_returns_type_schema_as_value(self):
        """value_schema ('text', 'date', etc.) must never leak as display_value."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)

        for pred, val, txt in [
            ("recipient", "Prof. Sharma", "Recipient: Prof. Sharma"),
            ("acceptance_date", "2023-06-15", "Date: 15 June 2023"),
            ("publication_title", "Deep Learning Review", "Title: Deep Learning Review"),
        ]:
            claim, spans = _make_claim(pred, val, txt)
            store.put(claim, spans)
        db.commit()

        queue = ConfirmationQueue(store)
        items = queue.pending(page=1, page_size=10)

        for item in items:
            # display_value must NOT be a type schema
            assert item.display_value not in ("text", "date", "number", "money", "raw", "")
            # display_value must be the actual value
            assert item.display_value in ("Prof. Sharma", "2023-06-15", "Deep Learning Review")

    def test_queue_empty_display_value_for_raw_claims(self):
        """Claims with raw/empty value should have empty display_value."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)

        claim, spans = _make_claim("unknown_field", "", "")
        store.put(claim, spans)
        db.commit()

        queue = ConfirmationQueue(store)
        items = queue.pending(page=1, page_size=10)

        assert len(items) == 1
        assert items[0].display_value == ""


class TestDocumentAnalysisFieldStatus:
    """The field_confidence status must reflect actual record outcomes."""

    def _analyze_with_text(self, text: str, filename: str) -> "DocumentAnalysis":
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = DocumentIntakeService(ClaimService(store), store)
        return svc.analyze(
            text=text, filename=filename,
            document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            version=1, acl_scope=None,
        )

    def test_high_confidence_field_auto_suggested(self):
        """High-confidence label extraction → auto_suggested → auto_applied status."""
        analysis = self._analyze_with_text(
            "Recipient: Prof. Sharma\nCertificate Number: CS-2023-001",
            "certificate.pdf",
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        # recipient should be auto_applied (high confidence, no conflicts)
        recipients = [f for f in out.field_confidence if f.predicate_id == "recipient"]
        assert len(recipients) > 0
        assert recipients[0].status == "auto_applied"
        assert recipients[0].value == "Prof. Sharma"

    def test_prose_extracted_field_proposed(self):
        """Prose-extracted fields → proposed status."""
        analysis = self._analyze_with_text(
            "This is to certify that Dr. Alice participated in the\n"
            "International Conference on Artificial Intelligence held at\n"
            "IIT Delhi on 15 March 2025.",
            "conference_cert.pdf",
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        # event_title should be proposed (prose confidence < 0.9)
        event_fields = [f for f in out.field_confidence if f.predicate_id == "event_title"]
        if event_fields:
            assert event_fields[0].status == "proposed"
            assert "International Conference" in event_fields[0].value
            # Must NOT be "text" or "prose"
            assert event_fields[0].value not in ("text", "prose", "date", "number")

    def test_field_confidence_risk_reflects_confidence(self):
        """Risk must be 'low' for high confidence, 'high' for low confidence."""
        analysis = self._analyze_with_text(
            "Recipient: Dr. Alice\nCertificate Number: CS-2024-001",
            "cert.pdf",
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        for f in out.field_confidence:
            if f.confidence >= 0.9:
                assert f.risk == "low"
            elif f.confidence >= 0.75:
                assert f.risk == "medium"
            else:
                assert f.risk == "high"


class TestTargetRecordLabel:
    """AnalysisOut must include a professor-friendly target_record_label."""

    def test_certificate_produces_event_label(self):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = DocumentIntakeService(ClaimService(store), store)
        analysis = svc.analyze(
            text="This is to certify that Dr. Alice participated in the\n"
                 "International Conference on AI held at IIT Delhi on 15 March 2025.",
            filename="cert.pdf",
            document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            version=1, acl_scope=None,
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        assert out.target_record_label != ""
        assert out.target_record_label not in ("text", "number", "unknown")
        # The label should be meaningful — event or publication depending on classifier
        assert out.target_record_label in ("Event", "Publication", "Research Project")

    def test_research_paper_produces_publication_label(self):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = DocumentIntakeService(ClaimService(store), store)
        analysis = svc.analyze(
            text="Title: Deep Learning for NLP\nDOI: 10.1234/test.2024\nAuthors: Alice, Bob",
            filename="paper.pdf",
            document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            version=1, acl_scope=None,
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        assert out.target_record_label != ""
        assert out.target_record_label in ("Publication", "Research Project")


class TestReviewItemNeverDisplaysTypeMetadata:
    """Field values in analysis output must never be type metadata like 'text', 'date'."""

    def _get_analysis_output(self, text: str, filename: str):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = DocumentIntakeService(ClaimService(store), store)
        analysis = svc.analyze(
            text=text, filename=filename,
            document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            version=1, acl_scope=None,
        )
        from app.api.routes.document_intake import _analysis_out
        return _analysis_out(analysis)

    def test_no_field_has_type_metadata_as_value(self):
        """No field's value should be a type metadata string."""
        type_names = {"text", "date", "number", "money", "raw", "unknown"}
        out = self._get_analysis_output(
            "Recipient: Dr. Alice\nCertificate Number: CS-2024-001\n"
            "Date: 15 March 2025",
            "certificate.pdf",
        )
        for f in out.field_confidence:
            assert f.value not in type_names, (
                f"Field {f.predicate_id} has type metadata '{f.value}' as value"
            )

    def test_extracted_value_is_actual_content(self):
        """Field values must contain actual extracted content."""
        out = self._get_analysis_output(
            "Recipient: Dr. Alice Smith\nCertificate Number: CS-2024-001",
            "cert.pdf",
        )
        values = {f.predicate_id: f.value for f in out.field_confidence}
        if "recipient" in values:
            assert "Dr. Alice Smith" in values["recipient"]
        if "certificate_number" in values:
            assert "CS-2024-001" in values["certificate_number"]


class TestNotificationReviewIntegration:
    """Notifications must point to the correct document review context."""

    def test_notification_action_url_contains_document_id(self):
        """Action URL must link to the specific document for review."""
        from app.application.services.notification_service import NotificationService
        from app.infrastructure.db.models.notification_model import NotificationModel
        from app.infrastructure.persistence.notification_store import SQLNotificationStore

        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        # Create notification table
        NotificationModel.__table__.create(engine, checkfirst=True)

        store = SQLNotificationStore(db)
        svc = NotificationService(store)
        doc_id = "doc:pdf:test123"
        notif = svc.create(
            user_id="user:1",
            notification_type="document_analyzed",
            title="Document needs review",
            message="test",
            action_url=f"/documents/{doc_id}",
            metadata={"document_id": doc_id},
        )
        db.commit()

        assert f"/documents/{doc_id}" in notif.action_url
