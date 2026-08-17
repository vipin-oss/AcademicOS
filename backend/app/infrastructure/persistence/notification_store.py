"""SQL adapter for the notification store port."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.application.ports.notification_store import NotificationRecord, NotificationStore
from app.infrastructure.db.models.notification_model import NotificationModel


def _to_record(model: NotificationModel) -> NotificationRecord:
    """Convert ORM model to domain record."""
    return NotificationRecord(
        id=model.id,
        user_id=model.user_id,
        notification_type=model.notification_type,
        title=model.title,
        message=model.message,
        action_url=model.action_url,
        is_read=model.is_read,
        created_at=model.created_at,
        read_at=model.read_at,
    )


class SQLNotificationStore(NotificationStore):
    """SQLAlchemy-backed notification store."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def put(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> NotificationRecord:
        model = NotificationModel(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            metadata_json=metadata_json,
        )
        self._db.add(model)
        self._db.flush()
        return _to_record(model)

    def by_user(
        self,
        user_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[NotificationRecord]:
        query = self._db.query(NotificationModel).filter(
            NotificationModel.user_id == user_id
        )
        if unread_only:
            query = query.filter(NotificationModel.is_read == False)
        models = (
            query.order_by(NotificationModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_to_record(m) for m in models]

    def unread_count(self, user_id: str) -> int:
        return (
            self._db.query(NotificationModel)
            .filter(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read == False,
            )
            .count()
        )

    def mark_read(self, notification_id: str, user_id: str) -> bool:
        model = (
            self._db.query(NotificationModel)
            .filter(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
            .first()
        )
        if model is None:
            return False
        model.is_read = True
        model.read_at = datetime.now(timezone.utc)
        self._db.flush()
        return True

    def mark_all_read(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        count = (
            self._db.query(NotificationModel)
            .filter(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read == False,
            )
            .update({"is_read": True, "read_at": now})
        )
        self._db.flush()
        return count

    def delete(self, notification_id: str, user_id: str) -> bool:
        model = (
            self._db.query(NotificationModel)
            .filter(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
            .first()
        )
        if model is None:
            return False
        self._db.delete(model)
        self._db.flush()
        return True

    def find_matching(
        self,
        user_id: str,
        notification_type: str,
        action_url: Optional[str] = None,
        unread_only: bool = True,
    ) -> Optional[NotificationRecord]:
        """Find an existing notification matching the criteria."""
        query = self._db.query(NotificationModel).filter(
            NotificationModel.user_id == user_id,
            NotificationModel.notification_type == notification_type,
        )
        if action_url is not None:
            query = query.filter(NotificationModel.action_url == action_url)
        if unread_only:
            query = query.filter(NotificationModel.is_read == False)
        model = query.order_by(NotificationModel.created_at.desc()).first()
        return _to_record(model) if model else None
