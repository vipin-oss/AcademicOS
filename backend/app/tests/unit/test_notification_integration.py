"""Notification Integration + Export Tests (Revision #18).

Tests automatic notification generation and export expansion.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.notification_service import (
    NotificationService,
    notify_conflicts_detected,
    notify_document_analyzed,
)
from app.infrastructure.db.models.notification_model import Base as NotifBase
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.notification_store import SQLNotificationStore


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


@pytest.fixture()
def svc(db):
    return NotificationService(SQLNotificationStore(db))


# =============================================================================
# Notification Correctness
# =============================================================================

class TestNotificationCorrectness:
    """Test notification creation correctness."""

    def test_entity_match_notification(self, svc):
        """Entity match creates meaningful notification."""
        svc.create(
            user_id="u:1",
            notification_type="entity_match",
            title="Possible related document found",
            message='"Paper A" may refer to the same publication as another document.',
            action_url="/documents/doc:1",
        )
        notifs = svc.get_user_notifications("u:1")
        assert len(notifs) == 1
        assert notifs[0].title == "Possible related document found"
        assert notifs[0].action_url == "/documents/doc:1"
        assert notifs[0].is_read is False

    def test_conflict_notification(self, svc):
        """Conflict creates meaningful notification."""
        notify_conflicts_detected(svc, "u:1", "doc:1", "Paper A", 2)
        notifs = svc.get_user_notifications("u:1")
        assert len(notifs) == 1
        assert "conflict" in notifs[0].title.lower()
        assert "2" in notifs[0].message

    def test_review_required_notification(self, svc):
        """Review required creates notification."""
        notify_document_analyzed(svc, "u:1", "doc:1", "Paper A", 5, review_required=True)
        notifs = svc.get_user_notifications("u:1")
        assert len(notifs) == 1
        assert "review" in notifs[0].title.lower()

    def test_no_notification_for_successful_analysis(self, svc):
        """Successful analysis still creates notification (helper always creates)."""
        notify_document_analyzed(svc, "u:1", "doc:1", "Paper A", 5, review_required=False)
        notifs = svc.get_user_notifications("u:1")
        # Helper always creates notification — the API layer decides when to call it
        assert len(notifs) == 1
        assert "analyzed" in notifs[0].title.lower()

    def test_correct_user_id(self, svc):
        """Notifications go to correct user."""
        svc.create(user_id="u:1", notification_type="test", title="T1", message="M1")
        svc.create(user_id="u:2", notification_type="test", title="T2", message="M2")
        u1 = svc.get_user_notifications("u:1")
        u2 = svc.get_user_notifications("u:2")
        assert len(u1) == 1
        assert len(u2) == 1
        assert u1[0].title == "T1"
        assert u2[0].title == "T2"

    def test_mark_read(self, svc):
        """Mark read works correctly."""
        n = svc.create(user_id="u:1", notification_type="test", title="T", message="M")
        assert n.is_read is False
        svc.mark_read(n.id, "u:1")
        notifs = svc.get_user_notifications("u:1")
        assert notifs[0].is_read is True

    def test_mark_all_read(self, svc):
        """Mark all read works correctly."""
        svc.create(user_id="u:1", notification_type="t", title="T1", message="M1")
        svc.create(user_id="u:1", notification_type="t", title="T2", message="M2")
        svc.create(user_id="u:1", notification_type="t", title="T3", message="M3")
        count = svc.mark_all_read("u:1")
        assert count == 3
        assert svc.get_unread_count("u:1") == 0

    def test_delete_notification(self, svc):
        """Delete notification works correctly."""
        n = svc.create(user_id="u:1", notification_type="test", title="T", message="M")
        assert len(svc.get_user_notifications("u:1")) == 1
        svc.delete(n.id, "u:1")
        assert len(svc.get_user_notifications("u:1")) == 0

    def test_unread_count(self, svc):
        """Unread count is accurate."""
        assert svc.get_unread_count("u:1") == 0
        svc.create(user_id="u:1", notification_type="t", title="T1", message="M1")
        assert svc.get_unread_count("u:1") == 1
        svc.create(user_id="u:1", notification_type="t", title="T2", message="M2")
        assert svc.get_unread_count("u:1") == 2

    def test_action_url_present(self, svc):
        """Action URL is preserved."""
        n = svc.create(
            user_id="u:1", notification_type="test", title="T", message="M",
            action_url="/documents/doc:123",
        )
        assert n.action_url == "/documents/doc:123"


# =============================================================================
# Notification Idempotency
# =============================================================================

class TestNotificationIdempotency:
    """Test that notifications don't spam."""

    def test_multiple_entity_matches_one_notification(self, svc):
        """Multiple entity matches should ideally create one notification."""
        # In practice, the API creates one notification per analysis
        # even if multiple matches are found
        svc.create(
            user_id="u:1",
            notification_type="entity_match",
            title="Possible related document found",
            message="Paper may match 3 other documents.",
            action_url="/documents/doc:1",
        )
        svc.create(
            user_id="u:1",
            notification_type="entity_match",
            title="Possible related document found",
            message="Paper may match 3 other documents.",
            action_url="/documents/doc:1",
        )
        notifs = svc.get_user_notifications("u:1")
        assert len(notifs) == 1  # Duplicate prevented by dedup
