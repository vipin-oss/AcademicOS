"""V3 ADR-068 prose extraction + conversational-guard tests.

Proves the pipeline extracts structured facts from NATURAL PROSE (not just
"Label: value"), and that pure conversational questions do not trigger broad
document retrieval while domain-noun questions still do.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.assistant_retrieval import retrieval_plan
from app.application.services.claim_service import ClaimService
from app.application.services.document_intake import DocumentIntakeService
from app.application.services.prose_extractor import prose_fields
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore

# A REALISTIC conference certificate in natural prose (no "Label: value").
PROSE_CERTIFICATE = (
    "This is to certify that Dr. Vipin Gupta presented a paper entitled "
    "Topological Insulators for Energy Storage at the International Conference "
    "on Quantum Materials organized by the Indian Physics Association held at "
    "Vigyan Bhawan, New Delhi from 6 December 2022 to 11 December 2022."
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


def test_prose_fields_extracts_from_natural_prose():
    fields = prose_fields(PROSE_CERTIFICATE)
    assert fields["recipient"][0] == "Dr. Vipin Gupta"
    assert "Topological Insulators" in fields["presentation_title"][0]
    assert "Quantum Materials" in fields["conference_name"][0]
    assert "Vigyan Bhawan" in fields["venue"][0]
    assert "Indian Physics Association" in fields["conference_organizer"][0]
    assert fields["start_date"][0] == "2022-12-06"
    assert fields["end_date"][0] == "2022-12-11"


def test_document_intake_extracts_prose_fields(db):
    store = SQLClaimStore(db)
    svc = DocumentIntakeService(ClaimService(store), store)
    analysis = svc.analyze(
        text=PROSE_CERTIFICATE, filename="certificate.pdf",
        document_id="obj:document:1", version=1,
        acl_scope='{"owner":"u:1"}',
    )
    preds = {f.predicate_id: f.value for f in analysis.fields}
    assert preds.get("recipient") == "Dr. Vipin Gupta"
    assert preds.get("conference_name", "").find("Quantum Materials") != -1
    assert preds.get("start_date") == "2022-12-06"
    assert preds.get("end_date") == "2022-12-11"
    assert preds.get("venue", "").find("Vigyan Bhawan") != -1
    # prose fields are flagged as prose-extracted
    assert any(f.extractor == "prose" for f in analysis.fields)


def test_conversational_question_does_not_retrieve():
    plan = retrieval_plan("are you working?")
    assert plan.terms == ()


def test_conversational_liveness_question_does_not_retrieve():
    assert retrieval_plan("how are you?").terms == ()


def test_domain_noun_question_still_retrieves():
    plan = retrieval_plan("are you working on my research project?")
    assert plan.terms != ()
    assert plan.object_type == "research_project"


def test_personal_data_question_scopes_to_type():
    plan = retrieval_plan("what conferences have I attended?")
    assert plan.object_type == "event"
