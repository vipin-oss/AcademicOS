"""Notification API — user-facing notification endpoints.

Surface:
    GET  /notifications          list notifications (newest first)
    GET  /notifications/count    unread count
    PUT  /notifications/{id}/read  mark one as read
    PUT  /notifications/read-all   mark all as read
    DELETE /notifications/{id}    delete one notification
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.notification_service import NotificationService
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.notification_store import SQLNotificationStore

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


class NotificationOut(BaseModel):
    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    action_url: Optional[str] = None
    is_read: bool
    created_at: Optional[str] = None
    read_at: Optional[str] = None


class UnreadCountOut(BaseModel):
    count: int


class MarkReadResult(BaseModel):
    success: bool


class MarkAllReadResult(BaseModel):
    count: int


def _svc(db: Session) -> NotificationService:
    return NotificationService(SQLNotificationStore(db))


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> list[NotificationOut]:
    """List notifications for the current user, newest first."""
    svc = _svc(db)
    notifications = svc.get_user_notifications(
        str(user.id), limit=limit, unread_only=unread_only
    )
    return [
        NotificationOut(
            id=n.id,
            user_id=n.user_id,
            notification_type=n.notification_type,
            title=n.title,
            message=n.message,
            action_url=n.action_url,
            is_read=n.is_read,
            created_at=n.created_at.isoformat() if n.created_at else None,
            read_at=n.read_at.isoformat() if n.read_at else None,
        )
        for n in notifications
    ]


@router.get("/count", response_model=UnreadCountOut)
def get_unread_count(
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> UnreadCountOut:
    """Get count of unread notifications."""
    svc = _svc(db)
    count = svc.get_unread_count(str(user.id))
    return UnreadCountOut(count=count)


@router.put("/{notification_id}/read", response_model=MarkReadResult)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> MarkReadResult:
    """Mark a single notification as read."""
    svc = _svc(db)
    success = svc.mark_read(notification_id, str(user.id))
    return MarkReadResult(success=success)


@router.put("/read-all", response_model=MarkAllReadResult)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> MarkAllReadResult:
    """Mark all notifications as read for the current user."""
    svc = _svc(db)
    count = svc.mark_all_read(str(user.id))
    return MarkAllReadResult(count=count)


@router.delete("/{notification_id}", response_model=MarkReadResult)
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> MarkReadResult:
    """Delete a notification."""
    svc = _svc(db)
    success = svc.delete(notification_id, str(user.id))
    return MarkReadResult(success=success)
