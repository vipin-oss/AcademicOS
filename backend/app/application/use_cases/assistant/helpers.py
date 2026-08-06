"""Shared helpers for the Assistant use cases (mirrors productivity/settings).

Conversation objects: ``ObjectType.AI_CONVERSATION`` universal objects whose
messages are embedded as ``msg.<seq>`` JSON metadata entries. One aggregate
per conversation keeps the whole thread versioned by the existing object
audit machinery — no message objects, no extra tables, V1-capped at
:data:`MAX_MESSAGES_PER_CONVERSATION` (oldest pairs trimmed).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from app.application.dtos import assistant as dto
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.assistant_provider import AssistantProvider
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _set(obj: UniversalObject, key: str, value: str) -> None:
    obj.set_metadata(MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED))


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


# ------------------------------------------------------------- conversations
def create_conversation_object(repository: ObjectRepository, title: str,
                               created_by: str, title_auto: bool) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=ObjectType.AI_CONVERSATION,
        title=title,
        created_by=created_by,
        status=ObjectStatus.ACTIVE,
    )
    _set(obj, dto.KEY_PINNED, "false")
    _set(obj, dto.KEY_TITLE_AUTO, "true" if title_auto else "false")
    repository.save(obj)
    return obj


def get_conversation_object(repository: ObjectRepository, conversation_id: str) -> UniversalObject:
    obj = repository.get_by_id(conversation_id)  # the port method (adapters: get == get_by_id)
    if obj is None or obj.object_type is not ObjectType.AI_CONVERSATION:
        raise ObjectNotFoundError(f"Conversation not found: {conversation_id}")
    return obj


def all_conversations(repository: ObjectRepository) -> list[UniversalObject]:
    return repository.find_by_type(ObjectType.AI_CONVERSATION)


def sort_conversations(objs: list[UniversalObject]) -> list[UniversalObject]:
    """Pinned first, then most-recent activity (messages beat empty shells)."""
    def key_fn(obj: UniversalObject):
        meta = _meta(obj)
        stamp = last_message_at(obj) or getattr(getattr(obj, "audit", None), "created_at", None)
        return (
            0 if (meta.get(dto.KEY_PINNED) or "").lower() == "true" else 1,
            stamp.isoformat() if stamp else "",
        )

    pinned_first = sorted(
        objs,
        key=lambda o: key_fn(o)[1],
        reverse=True,
    )
    return sorted(pinned_first, key=lambda o: key_fn(o)[0])


def set_pinned(obj: UniversalObject, pinned: bool) -> None:
    _set(obj, dto.KEY_PINNED, "true" if pinned else "false")


def last_message_at(obj: UniversalObject) -> datetime | None:
    stamps = [
        _parse_ts(payload.get("ts"))
        for _seq, payload in read_messages(obj)
        if payload.get("ts")
    ]
    stamps = [stamp for stamp in stamps if stamp]
    return max(stamps) if stamps else None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ----------------------------------------------------------------- messages
def read_messages(obj: UniversalObject) -> list[tuple[int, dict]]:
    out: list[tuple[int, dict]] = []
    for key, value in _meta(obj).items():
        if not key.startswith(dto.MSG_KEY_PREFIX):
            continue
        try:
            seq = int(key[len(dto.MSG_KEY_PREFIX):])
        except ValueError:
            continue
        try:
            payload = json.loads(value)
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            out.append((seq, payload))
    return sorted(out, key=lambda pair: pair[0])


def next_seq(obj: UniversalObject) -> int:
    messages = read_messages(obj)
    return (messages[-1][0] + 1) if messages else 1


def append_message(obj: UniversalObject, role: str, content: str,
                   answer: dto.AssistantAnswerOutput | None) -> tuple[int, dict]:
    seq = next_seq(obj)
    payload = {"role": role, "content": content, "ts": now_iso()}
    if answer is not None:
        payload["answer"] = asdict(answer)
    _set(obj, f"{dto.MSG_KEY_PREFIX}{seq}", json.dumps(payload, ensure_ascii=False))
    _trim_messages(obj)
    return seq, payload


def _trim_messages(obj: UniversalObject) -> None:
    messages = read_messages(obj)
    overflow = len(messages) - dto.MAX_MESSAGES_PER_CONVERSATION
    if overflow <= 0:
        return
    for seq, _payload in messages[:overflow]:
        _set(obj, f"{dto.MSG_KEY_PREFIX}{seq}", "")


def derive_title(question: str) -> str:
    """Auto title from the first question: word-boundary trim, deterministic."""
    cleaned = " ".join(question.strip().split())
    if len(cleaned) <= 60:
        return cleaned
    trimmed = cleaned[:60].rsplit(" ", 1)[0].rstrip(",.;:!?")
    return (trimmed or cleaned[:60]).strip()


def auto_title_if_needed(obj: UniversalObject, question: str) -> None:
    """Derive the title from the FIRST question only — later asks never
    re-title an auto-titled thread (the E2E tour caught this drift)."""
    meta = _meta(obj)
    if obj.title.strip() and (meta.get(dto.KEY_TITLE_AUTO) or "").lower() != "true":
        return
    if read_messages(obj):  # the thread already has its first question
        return
    obj.title = derive_title(question)
    _set(obj, dto.KEY_TITLE_AUTO, "true")


def rename(obj: UniversalObject, title: str) -> None:
    obj.title = title
    _set(obj, dto.KEY_TITLE_AUTO, "false")


def reset_auto_title(obj: UniversalObject) -> None:
    """Clear an explicit rename: re-derive from the first user message (or the
    placeholder) and hand titling back to the auto rule on the next question."""
    first_user = next(
        (payload for _seq, payload in read_messages(obj) if payload.get("role") == "user"),
        None,
    )
    obj.title = derive_title(str(first_user.get("content") or "")) if first_user else "New conversation"
    _set(obj, dto.KEY_TITLE_AUTO, "true")


# ----------------------------------------------------------------- outputs
def conversation_output(obj: UniversalObject) -> dto.AssistantConversationOutput:
    meta = _meta(obj)
    audit = getattr(obj, "audit", None)
    created = getattr(audit, "created_at", None)
    last = last_message_at(obj)
    return dto.AssistantConversationOutput(
        id=str(obj.id),
        title=obj.title,
        pinned=(meta.get(dto.KEY_PINNED) or "").lower() == "true",
        message_count=len(read_messages(obj)),
        last_message_at=last.isoformat() if last else None,
        created_at=created.isoformat() if created else None,
        version=getattr(obj, "version", 1),
    )


def message_output(seq: int, payload: dict) -> dto.AssistantMessageOutput:
    raw_answer = payload.get("answer")
    answer = None
    if isinstance(raw_answer, dict):
        answer = dto.AssistantAnswerOutput(
            intent=raw_answer.get("intent", ""),
            intent_label=raw_answer.get("intent_label", ""),
            question=raw_answer.get("question", ""),
            summary=raw_answer.get("summary", ""),
            metrics=raw_answer.get("metrics") or {},
            items=raw_answer.get("items") or [],
            cards=[dto.AssistantCardOutput(**card) for card in raw_answer.get("cards") or []],
            actions=[dto.AssistantActionOutput(**action) for action in raw_answer.get("actions") or []],
            sources=raw_answer.get("sources") or [],
        )
    return dto.AssistantMessageOutput(
        seq=seq,
        role=str(payload.get("role") or "user"),
        content=str(payload.get("content") or ""),
        created_at=str(payload.get("ts") or ""),
        answer=answer,
    )


def home_output(repository: ObjectRepository, provider: AssistantProvider) -> dto.AssistantHomeOutput:
    del provider  # suggestions are deterministic in V1; future providers may tailor them
    conversations = sort_conversations(all_conversations(repository))
    pinned = [c for c in conversations if (_meta(c).get(dto.KEY_PINNED) or "").lower() == "true"]
    recent = [c for c in conversations if read_messages(c)]
    return dto.AssistantHomeOutput(
        suggested=[dto.SuggestedPrompt(group=group, question=question, intent=intent)
                   for group, question, intent in dto.SUGGESTED_QUESTIONS],
        recent=[conversation_output(c) for c in recent[: dto.HOME_RECENT_LIMIT]],
        pinned=[conversation_output(c) for c in pinned],
        conversation_count=len(conversations),
    )
