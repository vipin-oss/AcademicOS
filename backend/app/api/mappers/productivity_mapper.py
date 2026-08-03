"""Presentation mapper for the Productivity Hub (mirrors events_mapper).

Body dicts (extra keys forbidden by the pydantic models) become module
inputs verbatim; outputs become plain dicts for the response models. No
business logic here — shaping lives in the use-case helpers.
"""
from __future__ import annotations

from dataclasses import asdict

from app.application.dtos.productivity import (
    CreateEntryInput,
    CreateNotificationInput,
    CreateTaskInput,
    UpdateEntryInput,
    UpdateNotificationInput,
    UpdateTaskInput,
)


def to_create_task_input(body: dict) -> CreateTaskInput:
    return CreateTaskInput(
        title=body.get("title") or "",
        uploaded_by=body.get("uploaded_by") or "",
        description=body.get("description"),
        priority=body.get("priority"),
        category=body.get("category"),
        start_date=body.get("start_date"),
        due_date=body.get("due_date"),
        completed=bool(body.get("completed", False)),
        pinned=bool(body.get("pinned", False)),
        reminder=body.get("reminder"),
        tags=body.get("tags"),
        remarks=body.get("remarks"),
    )


def to_update_task_input(body: dict) -> UpdateTaskInput:
    return UpdateTaskInput(
        uploaded_by=body.get("uploaded_by") or "system",
        title=body.get("title"),
        description=body.get("description"),
        priority=body.get("priority"),
        category=body.get("category"),
        start_date=body.get("start_date"),
        due_date=body.get("due_date"),
        completed=body.get("completed"),
        pinned=body.get("pinned"),
        reminder=body.get("reminder"),
        tags=body.get("tags"),
        remarks=body.get("remarks"),
    )


def to_create_entry_input(body: dict) -> CreateEntryInput:
    return CreateEntryInput(
        title=body.get("title") or "",
        uploaded_by=body.get("uploaded_by") or "",
        start_date=body.get("start_date") or "",
        description=body.get("description"),
        end_date=body.get("end_date"),
        start_time=body.get("start_time"),
        end_time=body.get("end_time"),
        location=body.get("location"),
        category=body.get("category"),
        tags=body.get("tags"),
    )


def to_update_entry_input(body: dict) -> UpdateEntryInput:
    return UpdateEntryInput(
        uploaded_by=body.get("uploaded_by") or "system",
        title=body.get("title"),
        start_date=body.get("start_date"),
        description=body.get("description"),
        end_date=body.get("end_date"),
        start_time=body.get("start_time"),
        end_time=body.get("end_time"),
        location=body.get("location"),
        category=body.get("category"),
        tags=body.get("tags"),
    )


def to_create_notification_input(body: dict) -> CreateNotificationInput:
    return CreateNotificationInput(
        title=body.get("title") or "",
        uploaded_by=body.get("uploaded_by") or "",
        body=body.get("body"),
        category=body.get("category"),
        priority=body.get("priority"),
        link=body.get("link"),
        source_module=body.get("source_module"),
        source_ref=body.get("source_ref"),
    )


def to_update_notification_input(body: dict) -> UpdateNotificationInput:
    return UpdateNotificationInput(
        uploaded_by=body.get("uploaded_by") or "system",
        is_read=body.get("is_read"),
        pinned=body.get("pinned"),
        archived=body.get("archived"),
        snoozed_until=body.get("snoozed_until"),
        title=body.get("title"),
        body=body.get("body"),
    )


def output_dict(output) -> dict:
    """Dataclass output -> response dict (events_mapper asdict precedent)."""
    return asdict(output)
