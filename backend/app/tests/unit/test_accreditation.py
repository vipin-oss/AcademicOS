"""V3 M18 accreditation workflow tests (ADR-065)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.knowledge.accreditation_frameworks import FRAMEWORKS, get_framework
from app.application.services.accreditation import (
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_REJECTED,
    AccreditationWorkflow,
)
from app.infrastructure.db.models.accreditation_model import (  # noqa: F401
    AccreditationSubmissionModel,
)
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.accreditation_store import SQLAccreditationStore


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


def test_frameworks_are_data():
    ids = {f.framework_id for f in FRAMEWORKS}
    assert {"naac", "nba", "nirf", "iqac"} <= ids
    assert get_framework("naac") is not None
    assert get_framework("unknown") is None


def test_full_lifecycle(db):
    wf = AccreditationWorkflow(SQLAccreditationStore(db))
    sub = wf.submit(
        framework_id="naac", criterion_id="naac-c1", indicator_id="naac-c1-i1",
        evidence=["obj:document:1"], narrative="Syllabus v2", period="2026-27",
    )
    assert sub.status == STATUS_DRAFT
    wf.submit_for_review(sub.id)
    assert wf.approve(sub.id, reviewer="u:admin").status == STATUS_APPROVED
    # period lock requires approved
    locked = wf.lock_period(sub.id, locked_by="u:admin")
    assert locked.period_locked is True
    assert locked.locked_by == "u:admin"


def test_reject_is_terminal_for_this_submission(db):
    wf = AccreditationWorkflow(SQLAccreditationStore(db))
    sub = wf.submit(
        framework_id="nirf", criterion_id="nirf-c1", indicator_id="nirf-c1-i1", evidence=[]
    )
    assert wf.reject(sub.id, reviewer="u:admin").status == STATUS_REJECTED


def test_lock_requires_approval(db):
    wf = AccreditationWorkflow(SQLAccreditationStore(db))
    sub = wf.submit(
        framework_id="nba", criterion_id="nba-c1", indicator_id="nba-c1-i1", evidence=[]
    )
    with pytest.raises(ValueError, match="approved"):
        wf.lock_period(sub.id, locked_by="u:admin")


def test_unknown_framework_rejected(db):
    wf = AccreditationWorkflow(SQLAccreditationStore(db))
    with pytest.raises(ValueError, match="Unknown framework"):
        wf.submit(framework_id="bogus", criterion_id="c", indicator_id="i", evidence=[])


def test_ai_suggestion_never_mutates(db):
    # suggest_evidence is a static, store-free method — it cannot approve/lock.
    suggestion = AccreditationWorkflow.suggest_evidence(
        indicator_id="naac-c1-i1", candidate_document_ids=["obj:document:1", "obj:document:2"]
    )
    assert suggestion.suggested_document_ids == ("obj:document:1", "obj:document:2")
    assert suggestion.draft_narrative
