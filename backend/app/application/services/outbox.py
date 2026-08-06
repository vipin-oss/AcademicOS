"""Outbox event serialization (Sprint-4 Milestone A).

Turns a ``DomainEvent`` into the durable row payload for the
``outbox_events`` table. The event already carries its idempotency key
(``event_id`` UUID) and timestamp (``occurred_at``) — nothing is invented
here; values are only made JSON-safe (ObjectId -> str, enums -> value,
datetimes -> ISO-8601, UUID -> str).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import uuid
from typing import Any

from app.domain.events import DomainEvent
from app.domain.value_objects.object_id import ObjectId


def _jsonable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return value.value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if getattr(value, field.name) is not None
        }
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def to_outbox_row(event: DomainEvent) -> dict:
    """The durable outbox row for one domain event."""
    return {
        "event_id": str(event.event_id),
        "aggregate_id": str(event.aggregate_id) if event.aggregate_id else "",
        "event_type": type(event).__name__,
        "payload": _jsonable(event),
        "created_at": event.occurred_at.isoformat(),
    }
