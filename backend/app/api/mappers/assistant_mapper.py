"""Presentation mapper for the Academic Intelligence Assistant.

Body dicts (extra keys forbidden by the pydantic models) become module inputs
verbatim; outputs become plain dicts for the responses. No business logic
here — intent parsing lives in the provider, validation in the validators.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.application.dtos.assistant import (
    AskQuestionInput,
    CreateConversationInput,
    DeleteConversationInput,
    UpdateConversationInput,
)

DEFAULT_ACTOR = "faculty:ui"  # the shared web-client actor convention


def to_ask_input(body: dict) -> AskQuestionInput:
    conversation_id = body.get("conversation_id")
    return AskQuestionInput(
        question=str(body.get("question") or ""),
        conversation_id=str(conversation_id) if conversation_id else None,
        asked_by=(body.get("asked_by") or DEFAULT_ACTOR),
        model_id=(str(body.get("model_id")) if body.get("model_id") else None),
    )


def to_create_input(body: dict) -> CreateConversationInput:
    title = body.get("title")
    return CreateConversationInput(
        title=str(title) if title is not None else None,
        created_by=(body.get("created_by") or DEFAULT_ACTOR),
    )


def to_update_input(conversation_id: str, body: dict) -> UpdateConversationInput:
    raw_title = body.get("title")
    return UpdateConversationInput(
        conversation_id=conversation_id,
        title=(str(raw_title) if raw_title is not None else None),
        pinned=(body.get("pinned") if body.get("pinned") is not None else None),
        updated_by=(body.get("updated_by") or DEFAULT_ACTOR),
    )


def to_delete_input(conversation_id: str) -> DeleteConversationInput:
    return DeleteConversationInput(conversation_id=conversation_id)


def output_dict(out: Any) -> dict[str, Any]:
    return asdict(out) if is_dataclass(out) else out
