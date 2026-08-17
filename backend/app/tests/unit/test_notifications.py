"""Unit tests for the notification service.

Tests CRUD operations and notification creation helpers.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.notification_service import (
    NotificationService,
    notify_conflicts_detected,
    notify_document_analyzed,
    notify_missing_info,
)
from app.infrastructure.db.models.notification_model import Base
from app.infrastructure.persistence.notification_store import SQLNotificationStore


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


@pytest.fixture()
def svc(db):
    return NotificationService(SQLNotificationStore(db))


def test_create_notification(svc):
    n = svc.create(
        user_id="u1",
        notification_type="test",
        title="Test Title",
        message="Test message",
    )
    assert n.id
    assert n.user_id == "u1"
    assert n.notification_type == "test"
    assert n.title == "Test Title"
    assert n.message == "Test message"
    assert n.is_read is False
    assert n.created_at is not None


def test_get_user_notifications(svc):
    svc.create(user_id="u1", notification_type="t1", title="T1", message="M1")
    svc.create(user_id="u1", notification_type="t2", title="T2", message="M2")
    svc.create(user_id="u2", notification_type="t3", title="T3", message="M3")

    u1 = svc.get_user_notifications("u1")
    assert len(u1) == 2
    assert all(n.user_id == "u1" for n in u1)

    u2 = svc.get_user_notifications("u2")
    assert len(u2) == 1
    assert u2[0].user_id == "u2"


def test_get_unread_count(svc):
    svc.create(user_id="u1", notification_type="t", title="T", message="M")
    svc.create(user_id="u1", notification_type="t", title="T", message="M")
    assert svc.get_unread_count("u1") == 2


def test_mark_read(svc):
    n = svc.create(user_id="u1", notification_type="t", title="T", message="M")
    assert n.is_read is False

    success = svc.mark_read(n.id, "u1")
    assert success is True

    notifications = svc.get_user_notifications("u1")
    assert notifications[0].is_read is True
    assert notifications[0].read_at is not None


def test_mark_read_wrong_user(svc):
    n = svc.create(user_id="u1", notification_type="t", title="T", message="M")
    success = svc.mark_read(n.id, "u2")
    assert success is False


def test_mark_all_read(svc):
    svc.create(user_id="u1", notification_type="t", title="T", message="M")
    svc.create(user_id="u1", notification_type="t", title="T", message="M")
    svc.create(user_id="u1", notification_type="t", title="T", message="M")

    count = svc.mark_all_read("u1")
    assert count == 3
    assert svc.get_unread_count("u1") == 0


def test_delete_notification(svc):
    n = svc.create(user_id="u1", notification_type="t", title="T", message="M")
    success = svc.delete(n.id, "u1")
    assert success is True
    assert len(svc.get_user_notifications("u1")) == 0


def test_delete_wrong_user(svc):
    n = svc.create(user_id="u1", notification_type="t", title="T", message="M")
    success = svc.delete(n.id, "u2")
    assert success is False
    assert len(svc.get_user_notifications("u1")) == 1


def test_unread_only_filter(svc):
    n1 = svc.create(user_id="u1", notification_type="t", title="T1", message="M1")
    svc.create(user_id="u1", notification_type="t", title="T2", message="M2")
    svc.mark_read(n1.id, "u1")

    all_n = svc.get_user_notifications("u1", unread_only=False)
    assert len(all_n) == 2

    unread = svc.get_user_notifications("u1", unread_only=True)
    assert len(unread) == 1
    assert unread[0].title == "T2"


def test_notify_document_analyzed_review(svc):
    n = notify_document_analyzed(
        svc, "u1", "doc1", "My Paper", 5, review_required=True
    )
    assert "review" in n.title.lower()
    assert "5" in n.message
    assert n.action_url == "/documents/doc1"


def test_notify_document_analyzed_success(svc):
    n = notify_document_analyzed(
        svc, "u1", "doc1", "My Paper", 3, review_required=False
    )
    assert "analyzed" in n.title.lower()
    assert "3" in n.message


def test_notify_conflicts_detected(svc):
    n = notify_conflicts_detected(svc, "u1", "doc1", "My Paper", 2)
    assert "conflict" in n.title.lower()
    assert "2" in n.message


def test_notify_missing_info(svc):
    n = notify_missing_info(svc, "u1", "doc1", "My Paper", 4)
    assert "missing" in n.title.lower()
    assert "4" in n.message
