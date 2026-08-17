"""Application port: notification store.

The seam between the notification lifecycle (application) and durable storage
(infrastructure). Carries domain Notification objects, never ORM models.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class NotificationRecord:
    """Domain notification record."""

    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    action_url: Optional[str]
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]


class NotificationStore(abc.ABC):
    """Abstract notification store port."""

    @abc.abstractmethod
    def put(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> NotificationRecord:
        """Insert a new notification."""

    @abc.abstractmethod
    def by_user(
        self,
        user_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> list[NotificationRecord]:
        """Return notifications for a user, newest first."""

    @abc.abstractmethod
    def unread_count(self, user_id: str) -> int:
        """Count unread notifications for a user."""

    @abc.abstractmethod
    def mark_read(self, notification_id: str, user_id: str) -> bool:
        """Mark one notification as read. Returns True if found."""

    @abc.abstractmethod
    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read. Returns count updated."""

    @abc.abstractmethod
    def delete(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification. Returns True if found."""

    @abc.abstractmethod
    def find_matching(
        self,
        user_id: str,
        notification_type: str,
        action_url: Optional[str] = None,
        unread_only: bool = True,
    ) -> Optional[NotificationRecord]:
        """Find an existing notification matching the criteria. Returns None if not found."""
