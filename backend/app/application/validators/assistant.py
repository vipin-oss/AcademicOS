"""Validators for the Assistant inputs (mirrors validators/settings.py)."""
from __future__ import annotations

from app.application.dtos.assistant import (
    CONVERSATION_TITLE_MAX,
    QUESTION_MAX,
    AskQuestionInput,
    CreateConversationInput,
    DeleteConversationInput,
    UpdateConversationInput,
)
from app.application.exceptions import ValidationError


def _err(message: str) -> None:
    raise ValidationError(message)


def assert_valid_question(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        _err("question must not be empty.")
    cleaned = text.strip()
    if len(cleaned) > QUESTION_MAX:
        _err(f"question must be at most {QUESTION_MAX} characters.")
    return cleaned


def _assert_title(title: str, field_name: str = "title") -> str:
    if not isinstance(title, str):
        _err(f"{field_name} must be a string.")
    cleaned = title.strip()
    if len(cleaned) > CONVERSATION_TITLE_MAX:
        _err(f"{field_name} must be at most {CONVERSATION_TITLE_MAX} characters.")
    return cleaned


def assert_valid_ask_input(data: AskQuestionInput) -> None:
    assert_valid_question(data.question)
    if data.conversation_id is not None and not str(data.conversation_id).strip():
        _err("conversation_id must not be blank (omit it to start a new conversation).")


def assert_valid_create_input(data: CreateConversationInput) -> None:
    if data.title is not None:
        _assert_title(data.title)
        if not data.title.strip():
            _err("title must not be empty (omit it for an untitled conversation).")


def assert_valid_update_input(data: UpdateConversationInput) -> None:
    if data.title is None and data.pinned is None:
        _err("nothing to update — provide title and/or pinned.")
    if data.title is not None and data.title != "":
        _assert_title(data.title)
    if data.pinned is not None and not isinstance(data.pinned, bool):
        _err("pinned must be a boolean.")


def assert_valid_delete_input(data: DeleteConversationInput) -> None:
    if not str(data.conversation_id).strip():
        _err("conversation_id is required.")
