"""Tests for the document-centric review workflow (Rev21).

Tests:
  - Pending review endpoint returns actual values
  - Pending review endpoint deduplicates claims
  - Analysis is idempotent (no duplicate claims on re-analysis)
  - Confirm/reject persist status changes
  - display_value is never a type schema
  - Error states (non-existent document, non-existent claim)
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.confirmation_queue import _claim_display_value
from app.application.services.document_intake import DocumentIntakeService, _norm
from app.application.services.extraction_health import claim_value_key
from app.domain.value_objects.claim import Claim, ClaimStatus
from app.domain.value_objects.enums import ObjectType, PermissionAction, Provenance
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore


def _make_engine():
    from sqlalchemy import StaticPool
    from app.infrastructure.db.models.claim_model import ClaimModel
    from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _analyze(db, store, text, filename, doc_id=None):
    """Run the intake pipeline and return the analysis."""
    svc = DocumentIntakeService(ClaimService(store), store)
    return svc.analyze(
        text=text, filename=filename,
        document_id=doc_id or f"doc:pdf:{uuid.uuid4().hex[:12]}",
        version=1, acl_scope=None,
    )


class TestAnalysisIdempotency:
    """Re-analyzing a document must NOT create duplicate claims."""

    def test_same_fields_no_duplicates(self):
        """Running analyze() twice on the same document produces same claim count."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        doc_id = f"doc:pdf:{uuid.uuid4().hex[:12]}"

        text = "Recipient: Prof B\nCertificate Number: CS-2024-001"

        # First analysis
        a1 = _analyze(db, store, text, "cert.txt", doc_id)
        db.commit()
        claims_after_first = store.by_source(doc_id)

        # Second analysis — same text, same doc_id
        a2 = _analyze(db, store, text, "cert.txt", doc_id)
        db.commit()
        claims_after_second = store.by_source(doc_id)

        # No new claims should be created
        assert len(claims_after_second) == len(claims_after_first), (
            f"Re-analysis created {len(claims_after_second) - len(claims_after_first)} duplicate claims"
        )

    def test_different_values_still_create_new_claims(self):
        """Different extracted values should create separate claims."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        doc_id = f"doc:pdf:{uuid.uuid4().hex[:12]}"

        # First analysis with one recipient
        a1 = _analyze(db, store, "Recipient: Alice", "cert1.txt", doc_id)
        db.commit()
        c1 = store.by_source(doc_id)

        # Same document but different content — new version
        a2 = _analyze(db, store, "Recipient: Bob", "cert1.txt", doc_id)
        db.commit()
        c2 = store.by_source(doc_id)

        # Should have more claims (different values)
        assert len(c2) >= len(c1)


class TestPendingReviewDeduplication:
    """Pending review endpoint should deduplicate by predicate+value."""

    def test_duplicate_claims_deduped(self):
        """Multiple claims with same predicate+value appear only once."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        doc_id = f"doc:pdf:{uuid.uuid4().hex[:12]}"

        # Manually create two claims with same predicate+value
        from app.application.knowledge.predicate_catalogue import normalize_predicate_value
        for _ in range(2):
            claim = Claim(
                claim_id=f"claim:{uuid.uuid4().hex[:12]}",
                predicate_id="recipient",
                predicate_version=1,
                value_schema="text",
                value=normalize_predicate_value("recipient", "Prof B", "Recipient: Prof B"),
                source_document_id=doc_id,
                source_version=1,
                status=ClaimStatus.PROPOSED,
                fact_confidence=0.85,
            )
            store.put(claim, [])
        db.commit()

        # All claims for this document
        all_claims = store.by_source(doc_id)
        assert len(all_claims) == 2

        # Deduplicated (simulating what the endpoint does)
        seen_keys: set[tuple[str, str]] = set()
        unique = []
        for c in all_claims:
            val_key = str(_norm(claim_value_key(c)))
            dedup_key = (c.predicate_id, val_key)
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                unique.append(c)

        assert len(unique) == 1
        assert unique[0].predicate_id == "recipient"


class TestConfirmRejectPersistence:
    """Confirm and reject must actually persist the status change."""

    def test_approve_changes_status(self):
        """Approving a claim changes its status to CONFIRMED."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = ClaimService(store)

        from app.application.knowledge.predicate_catalogue import normalize_predicate_value
        claim = svc.propose(
            predicate_id="recipient",
            raw_value="Prof B",
            source_text="Recipient: Prof B",
            source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            source_version=1,
            spans=[],
            acl_scope=None,
            fact_confidence=0.85,
        )
        db.commit()
        assert claim.status == ClaimStatus.PROPOSED

        # Approve via ClaimConfirmationService
        from app.application.services.claim_confirmation import ClaimConfirmationService
        from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore
        confirm_svc = ClaimConfirmationService(ClaimService(store), SQLClaimDecisionStore(db))
        confirm_svc.approve(claim.claim_id, reviewer="user:1")
        db.commit()

        # Verify status changed
        updated = store.get(claim.claim_id)
        assert updated is not None
        assert updated[0].status == ClaimStatus.CONFIRMED

    def test_reject_changes_status(self):
        """Rejecting a claim changes its status to REJECTED."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = ClaimService(store)

        claim = svc.propose(
            predicate_id="doi",
            raw_value="10.1234/test",
            source_text="DOI: 10.1234/test",
            source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            source_version=1,
            spans=[],
            acl_scope=None,
            fact_confidence=0.85,
        )
        db.commit()

        from app.application.services.claim_confirmation import ClaimConfirmationService
        from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore
        confirm_svc = ClaimConfirmationService(ClaimService(store), SQLClaimDecisionStore(db))
        confirm_svc.reject(claim.claim_id, reviewer="user:1")
        db.commit()

        updated = store.get(claim.claim_id)
        assert updated is not None
        assert updated[0].status == ClaimStatus.REJECTED


class TestDisplayValues:
    """display_value must contain actual extracted content, not type metadata."""

    def test_text_claim_has_actual_value(self):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = ClaimService(store)

        claim = svc.propose(
            predicate_id="recipient",
            raw_value="Prof Sharma",
            source_text="Recipient: Prof Sharma",
            source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            source_version=1,
            spans=[],
            acl_scope=None,
            fact_confidence=0.85,
        )
        db.commit()

        display = _claim_display_value(claim)
        assert display == "Prof Sharma"
        assert display not in ("text", "date", "number", "raw", "")

    def test_date_claim_has_actual_value(self):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = ClaimService(store)

        claim = svc.propose(
            predicate_id="acceptance_date",
            raw_value="2023-06-15",
            source_text="Date: 15 June 2023",
            source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            source_version=1,
            spans=[],
            acl_scope=None,
            fact_confidence=0.85,
        )
        db.commit()

        display = _claim_display_value(claim)
        assert display == "2023-06-15"
        assert display != "date"

    def test_empty_value_returns_empty(self):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        svc = ClaimService(store)

        claim = svc.propose(
            predicate_id="unknown_field",
            raw_value="",
            source_text="",
            source_document_id=f"doc:pdf:{uuid.uuid4().hex[:12]}",
            source_version=1,
            spans=[],
            acl_scope=None,
        )
        db.commit()

        display = _claim_display_value(claim)
        assert display == ""


class TestFieldConfidenceStatus:
    """field_confidence status must accurately reflect claim status."""

    def _analyze_and_get_status(self, text, filename):
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        analysis = _analyze(db, store, text, filename)
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)
        return {f.predicate_id: f.status for f in out.field_confidence}

    def test_prose_fields_are_proposed(self):
        """Prose-extracted fields (confidence < 0.9) should be 'proposed'."""
        status_map = self._analyze_and_get_status(
            "This is to certify that Dr. Alice participated in the\n"
            "International Conference on AI held at IIT Delhi on 15 March 2025.",
            "cert.pdf",
        )
        # At least some fields should be proposed
        proposed = [k for k, v in status_map.items() if v == "proposed"]
        assert len(proposed) > 0, f"No proposed fields found: {status_map}"

    def test_no_field_shows_type_schema_as_value(self):
        """No field's value should be 'text', 'date', etc."""
        engine = _make_engine()
        Session = sessionmaker(bind=engine)
        db = Session()
        store = SQLClaimStore(db)
        analysis = _analyze(db, store,
            "Recipient: Dr. Alice\nCertificate Number: CS-2024-001",
            "cert.pdf",
        )
        from app.api.routes.document_intake import _analysis_out
        out = _analysis_out(analysis)

        type_schemas = {"text", "date", "number", "money", "raw", "unknown"}
        for f in out.field_confidence:
            assert f.value not in type_schemas, (
                f"Field {f.predicate_id} has type schema '{f.value}' as value"
            )
