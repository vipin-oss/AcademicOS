"""Date-aware event deduplication tests.

Tests the four cases from the forensic audit:
1. Same user, same title, same year → DUPLICATE
2. Same user, same title, different year → NEW EVENT
3. Same user, same title, no date → DUPLICATE (title-only)
4. Different user, same title, same year → SEPARATE EVENTS
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.domain_record_router import DomainRecordRouter
from app.domain.value_objects.enums import ObjectType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import SQLAlchemyObjectRepository


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


def _create_event(repo, title, created_by, start_date=None):
    """Helper to create an event."""
    from app.application.commands.create_event import CreateEventCommand
    from app.application.dtos.events import CreateEventInput
    from app.application.use_cases.events.create_event import CreateEventUseCase

    out = CreateEventUseCase(repo).execute(
        CreateEventCommand(input=CreateEventInput(
            title=title,
            created_by=created_by,
            event_type="conference",
            start_date=start_date,
        ))
    )
    return out.id


def _route(db, fields, created_by, doc_id):
    """Helper to route a document."""
    repo = SQLAlchemyObjectRepository(db)
    router = DomainRecordRouter(repo)
    outcomes = router.route(
        type_ids=("conference_certificate", "conference"),
        fields={**fields, "__types__": ("conference_certificate", "conference")},
        created_by=created_by,
        source_document_id=doc_id,
        confidence=0.9,
    )
    return outcomes[0] if outcomes else None


class TestCase1_SameTitleSameYear:
    """Same user, same title, same year → DUPLICATE."""

    def test_same_title_same_year_is_duplicate(self, db):
        repo = SQLAlchemyObjectRepository(db)
        user = "user:alice"

        # Create first event
        _create_event(repo, "ICRA 2025", user, "2025-05-15")

        # Route second certificate with same title and year
        outcome = _route(db, {
            "conference_name": "ICRA 2025",
            "start_date": "2025-05-20",
        }, user, "doc:2")

        assert outcome.kind == "duplicate"
        assert outcome.existing_id != ""


class TestCase2_SameTitleDifferentYear:
    """Same user, same title, different year → NEW EVENT."""

    def test_same_title_different_year_creates_new(self, db):
        repo = SQLAlchemyObjectRepository(db)
        user = "user:alice"

        # Create 2024 event
        _create_event(repo, "International Conference on Mathematics", user, "2024-03-15")

        # Route 2025 certificate with same title
        outcome = _route(db, {
            "conference_name": "International Conference on Mathematics",
            "start_date": "2025-03-15",
        }, user, "doc:2")

        assert outcome.kind == "created"
        assert outcome.object_id != ""


class TestCase3_SameTitleNoDate:
    """Same user, same title, no date → DUPLICATE (title-only)."""

    def test_same_title_no_date_is_duplicate(self, db):
        repo = SQLAlchemyObjectRepository(db)
        user = "user:alice"

        # Create event without date
        _create_event(repo, "Workshop on AI", user)

        # Route certificate with same title but no date
        outcome = _route(db, {
            "conference_name": "Workshop on AI",
        }, user, "doc:2")

        assert outcome.kind == "duplicate"


class TestCase4_DifferentUser:
    """Different user, same title, same year → SEPARATE EVENTS."""

    def test_different_user_same_conference_creates_separate(self, db):
        repo = SQLAlchemyObjectRepository(db)

        # User A creates event
        _create_event(repo, "ICRA 2025", "user:alice", "2025-05-15")

        # User B routes same conference
        outcome = _route(db, {
            "conference_name": "ICRA 2025",
            "start_date": "2025-05-15",
        }, "user:bob", "doc:bob-1")

        assert outcome.kind == "created"
        assert outcome.object_id != ""
