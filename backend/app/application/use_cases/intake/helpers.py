"""Shared loaders and view builders for the intake use cases."""
from __future__ import annotations

from app.application.dtos.intake import (
    INTAKE_ACTOR,
    KEY_RELATIVE_PATH,
    KEY_SESSION_ID,
    IntakeItemOutput,
    IntakeProgressOutput,
    IntakeSessionOutput,
    intake_item_output,
    intake_progress_output,
    intake_session_output,
)
from app.application.exceptions import ObjectNotFoundError
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def set_system_metadata(obj: UniversalObject, key: str, value: str) -> None:
    """All intake writes are system facts (L1 / SYSTEM, actor ``intake``)."""

    obj.set_metadata(
        MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor=INTAKE_ACTOR,
    )


def get_intake_session_or_404(
    repository: ObjectRepository, session_id: str
) -> UniversalObject:
    obj = repository.get_by_id(ObjectId(session_id))
    if obj is None or obj.object_type is not ObjectType.INTAKE_SESSION:
        raise ObjectNotFoundError(f"Intake session {session_id} not found.")
    return obj


def items_of_session(
    repository: ObjectRepository, session_id: str
) -> list[UniversalObject]:
    """Every item of one session, deterministically ordered by relative path."""

    items = repository.find(object_type=ObjectType.INTAKE_ITEM)
    mine = [
        item
        for item in items
        if (item.metadata.get_value(KEY_SESSION_ID) or "") == session_id
    ]
    mine.sort(key=lambda i: (i.metadata.get_value(KEY_RELATIVE_PATH) or i.title).lower())
    return mine


def items_grouped_by_session(
    repository: ObjectRepository,
) -> dict[str, list[UniversalObject]]:
    """One ``find`` pass grouped per session (session-list cards)."""

    grouped: dict[str, list[UniversalObject]] = {}
    for item in repository.find(object_type=ObjectType.INTAKE_ITEM):
        grouped.setdefault(item.metadata.get_value(KEY_SESSION_ID) or "", []).append(item)
    return grouped


def session_view(obj: UniversalObject, items: list[UniversalObject]) -> IntakeSessionOutput:
    return intake_session_output(obj, items)


def item_view(obj: UniversalObject) -> IntakeItemOutput:
    return intake_item_output(obj)


def progress_view(obj: UniversalObject, items: list[UniversalObject]) -> IntakeProgressOutput:
    return intake_progress_output(obj, items)
