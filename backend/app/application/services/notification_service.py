"""Notification service — creates and manages user notifications.

Notifications are created by system events:
- Document analysis complete
- Conflicts detected
- Missing information found
- Enrichment complete
- AI suggestions ready for review
"""

from __future__ import annotations

from typing import Optional

from app.application.ports.notification_store import NotificationRecord, NotificationStore


class NotificationService:
    """Manages notifications for a user."""

    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    def create(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> NotificationRecord:
        """Create a new notification."""
        import json as json_mod

        metadata_json = json_mod.dumps(metadata) if metadata else None
        return self._store.put(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            metadata_json=metadata_json,
        )

    def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[NotificationRecord]:
        """Get notifications for a user, newest first."""
        return self._store.by_user(user_id, limit=limit, unread_only=unread_only)

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        return self._store.unread_count(user_id)

    def mark_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read. Returns True if found and updated."""
        return self._store.mark_read(notification_id, user_id)

    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read. Returns count updated."""
        return self._store.mark_all_read(user_id)

    def delete(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification. Returns True if found and deleted."""
        return self._store.delete(notification_id, user_id)


def notify_document_analyzed(
    service: NotificationService,
    user_id: str,
    document_id: str,
    document_title: str,
    field_count: int,
    review_required: bool,
) -> NotificationRecord:
    """Create notification when document analysis completes."""
    if review_required:
        title = "Document needs review"
        message = f'"{document_title}" was analyzed but has {field_count} fields that need your review.'
    else:
        title = "Document analyzed"
        message = f'"{document_title}" was analyzed successfully with {field_count} fields extracted.'

    return service.create(
        user_id=user_id,
        notification_type="document_analyzed",
        title=title,
        message=message,
        action_url=f"/documents/{document_id}",
        metadata={"document_id": document_id, "field_count": field_count},
    )


def notify_conflicts_detected(
    service: NotificationService,
    user_id: str,
    document_id: str,
    document_title: str,
    conflict_count: int,
) -> NotificationRecord:
    """Create notification when conflicts are detected."""
    return service.create(
        user_id=user_id,
        notification_type="conflicts_detected",
        title="Conflicts detected",
        message=f'"{document_title}" has {conflict_count} conflicting field(s) that need resolution.',
        action_url=f"/documents/{document_id}",
        metadata={"document_id": document_id, "conflict_count": conflict_count},
    )


def notify_missing_info(
    service: NotificationService,
    user_id: str,
    document_id: str,
    document_title: str,
    missing_count: int,
) -> NotificationRecord:
    """Create notification when missing information is found."""
    return service.create(
        user_id=user_id,
        notification_type="missing_info",
        title="Missing information",
        message=f'"{document_title}" is missing {missing_count} important field(s).',
        action_url=f"/documents/{document_id}",
        metadata={"document_id": document_id, "missing_count": missing_count},
    )


__all__ = [
    "NotificationService",
    "notify_conflicts_detected",
    "notify_document_analyzed",
    "notify_missing_info",
]
