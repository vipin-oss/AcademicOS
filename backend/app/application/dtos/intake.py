"""Intake Foundations (v2) — boundary DTOs for sessions and items.

One intake *session* represents one import operation (folder import, multi-file
drop, ZIP import later); one intake *item* represents one discovered file.
Both are plain Universal Objects — new ``ObjectType`` members appended to the
frozen enum, richer state held as JSON-encoded metadata entries written with
``L1_SYSTEM`` / ``Provenance.SYSTEM`` so a human-asserted value can never be
silently overwritten by the pipeline (FR-MET-009).

Structural information only: path, name, extension, size, detected MIME,
SHA-256 hash and stage cursor. NO extracted content metadata (that lands in
milestones M3+), no classification, no relationships.

No framework imports here — pure boundary shapes mirroring ``dtos/document.py``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# --------------------------------------------------------------------------
# Vocabulary (stored as plain metadata strings — never domain enums)
# --------------------------------------------------------------------------

INTAKE_ACTOR = "intake"
"""Audit actor recorded for every pipeline-driven write."""


class IntakeSourceKind(str, Enum):
    """Where the files of a session come from."""

    FOLDER = "folder"
    FILES = "files"


class IntakeSessionStatus(str, Enum):
    """Lifecycle of one import operation (metadata-only state machine)."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class IntakeItemStatus(str, Enum):
    """Lifecycle of one discovered file."""

    PENDING = "pending"
    STAGED = "staged"
    AWAITING_REVIEW = "awaiting_review"
    ERROR = "error"


class IntakeStage(str, Enum):
    """Pipeline stages in canonical order (Blueprint: V2 intake pipeline)."""

    ENUMERATE = "enumerate"
    STAGE = "stage"
    HASH = "hash"
    EXTRACT = "extract"
    CLASSIFY = "classify"
    MATCH = "match"
    PROPOSE = "propose"
    REVIEW = "review"
    COMMIT = "commit"


#: Stages every item walks in M1. Everything past HASH is executed by the
#: structurally-real *deferred* handler: the transition, timing and stage
#: record are production code; the domain work arrives in later milestones.
ITEM_STAGE_SEQUENCE: tuple[IntakeStage, ...] = (
    IntakeStage.STAGE,
    IntakeStage.HASH,
    IntakeStage.EXTRACT,
    IntakeStage.CLASSIFY,
    IntakeStage.MATCH,
    IntakeStage.PROPOSE,
    IntakeStage.REVIEW,
)

#: Which milestone will replace each deferred stage with real logic. Surfaced
#: in stage records so the roadmap is readable from data, not comments.
DEFERRED_STAGE_MILESTONES: dict[IntakeStage, str] = {
    IntakeStage.EXTRACT: "M3 (extraction) / M10 (OCR)",
    IntakeStage.CLASSIFY: "M5 (classification)",
    IntakeStage.MATCH: "M7 (record matching)",
    IntakeStage.PROPOSE: "M8 (proposal engine)",
}

#: Terminal item statuses for M1 (commit arrives with the proposal engine).
TERMINAL_ITEM_STATUSES: frozenset[IntakeItemStatus] = frozenset(
    {IntakeItemStatus.AWAITING_REVIEW, IntakeItemStatus.ERROR}
)

# Control transition guards — everything else is a 422 at the boundary.
PAUSABLE: frozenset[IntakeSessionStatus] = frozenset(
    {IntakeSessionStatus.QUEUED, IntakeSessionStatus.RUNNING}
)
RESUMABLE: frozenset[IntakeSessionStatus] = frozenset(
    {IntakeSessionStatus.PAUSED, IntakeSessionStatus.FAILED}
)
CANCELLABLE: frozenset[IntakeSessionStatus] = frozenset(
    {IntakeSessionStatus.QUEUED, IntakeSessionStatus.RUNNING, IntakeSessionStatus.PAUSED}
)

# --------------------------------------------------------------------------
# Limits & hygiene rules (deterministic, documented)
# --------------------------------------------------------------------------

MAX_FILE_BYTES = 512 * 1024 * 1024
"""Per-file intake cap. Oversized files become item errors, never crashes."""

MAX_FILES_PER_DROP = 5000
"""Boundary cap for explicit file-list drops (ZIP/folder imports walk freely)."""

MAX_FILE_PATHS_REQUEST = 5000
"""Same cap, enforced on the request payload itself."""

HISTORY_LIMIT = 32
"""Cap on per-item stage-history entries (32 × 9 stages is unreachable here)."""

RETRY_LIMIT = 3
"""An errored item is retried on resume until this attempt count."""

JUNK_FILE_NAMES: frozenset[str] = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
JUNK_FILE_PREFIXES: tuple[str, ...] = ("~$", "._")
JUNK_FILE_SUFFIXES: tuple[str, ...] = (
    ".part",
    ".partial",
    ".crdownload",
    ".download",
    ".tmp",
    ".swp",
)

STAGING_PREFIX = "intake"
"""Root storage-key prefix for every staged blob: ``intake/<session>/<rel>``."""

# --------------------------------------------------------------------------
# Metadata keys (single JSON-string-per-key doctrine)
# --------------------------------------------------------------------------

KEY_SESSION_ID = "intake.session_id"
KEY_INTAKE_STATUS = "intake.status"
KEY_SOURCE = "intake.source"
KEY_PROGRESS = "intake.progress"
KEY_STATISTICS = "intake.statistics"
KEY_SUMMARY = "intake.summary"
KEY_ERROR = "intake.error"
KEY_CONTROL = "intake.control"
KEY_CURRENT_STAGE = "intake.current_stage"
KEY_ENDED_AT = "intake.ended_at"
# Item-only keys
KEY_RELATIVE_PATH = "intake.relative_path"
KEY_ORIGINAL_PATH = "intake.original_path"
KEY_EXTENSION = "intake.extension"
KEY_SIZE_BYTES = "intake.size_bytes"
KEY_MIME_TYPE = "intake.mime_type"
KEY_SHA256 = "intake.sha256"
KEY_STAGED_KEY = "intake.staged_key"
KEY_ITEM_STAGE = "intake.stage"
KEY_STAGE_HISTORY = "intake.stage_history"
KEY_ATTEMPTS = "intake.attempts"


# --------------------------------------------------------------------------
# JSON helpers (metadata values are strings; complex state is encoded)
# --------------------------------------------------------------------------


def json_encode(value: Any) -> str:
    """Stable, compact encoding for metadata payloads."""

    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def json_decode(raw: str | None, fallback: Any) -> Any:
    """Decode a metadata JSON string, tolerating absence/corruption."""

    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return fallback


# --------------------------------------------------------------------------
# Inputs / commands-side shapes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CreateIntakeSessionInput:
    """Boundary input for creating one import session."""

    source_kind: IntakeSourceKind
    path: str | None = None  # FOLDER import: the directory to walk
    paths: tuple[str, ...] = ()  # FILES drop: explicit file paths
    actor: str = INTAKE_ACTOR
    title: str | None = None  # optional display override


# --------------------------------------------------------------------------
# Live aggregation (views are ALWAYS recomputed from items — never trusted
# from checkpoints, so progress can never drift)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IntakeItemFacts:
    """The structural facts one item contributes to live aggregation."""

    status: IntakeItemStatus
    stage: IntakeStage
    size_bytes: int
    extension: str
    mime_type: str | None
    has_hash: bool
    has_staged_key: bool


def summarize_items(facts: list[IntakeItemFacts], *, enumerated: bool) -> dict[str, Any]:
    """Compute the progress + statistics view from live item facts."""

    total = len(facts)
    counts = {
        IntakeItemStatus.PENDING.value: 0,
        IntakeItemStatus.STAGED.value: 0,
        IntakeItemStatus.AWAITING_REVIEW.value: 0,
        IntakeItemStatus.ERROR.value: 0,
    }
    hashed = 0
    staged = 0
    total_bytes = 0
    by_extension: dict[str, int] = {}
    by_mime: dict[str, int] = {}
    for fact in facts:
        counts[fact.status.value] += 1
        total_bytes += max(fact.size_bytes, 0)
        if fact.extension:
            by_extension[fact.extension] = by_extension.get(fact.extension, 0) + 1
        if fact.mime_type:
            by_mime[fact.mime_type] = by_mime.get(fact.mime_type, 0) + 1
        if fact.has_hash:
            hashed += 1
        if fact.has_staged_key:
            staged += 1
    processed = counts[IntakeItemStatus.AWAITING_REVIEW.value] + counts[IntakeItemStatus.ERROR.value]
    percent = round(100.0 * processed / total, 1) if total else (100.0 if enumerated else 0.0)
    return {
        "total_items": total,
        "processed_items": processed,
        "percent": percent,
        "pending": counts[IntakeItemStatus.PENDING.value],
        "staged": counts[IntakeItemStatus.STAGED.value],
        "hashed": hashed,
        "staged_items": staged,
        "awaiting_review": counts[IntakeItemStatus.AWAITING_REVIEW.value],
        "errors": counts[IntakeItemStatus.ERROR.value],
        "total_bytes": total_bytes,
        "by_extension": dict(sorted(by_extension.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_mime": dict(sorted(by_mime.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IntakeProgressOutput:
    """Lightweight polling payload for one session."""

    session_id: str
    status: str
    current_stage: str
    total_items: int
    processed_items: int
    percent: float
    counts: dict[str, int]
    updated_at: str | None


@dataclass(frozen=True)
class IntakeSessionOutput:
    """Full dashboard payload for one session."""

    id: str
    title: str
    source: dict[str, Any]
    status: str
    current_stage: str
    progress: dict[str, Any]
    statistics: dict[str, Any]
    summary: str | None
    error: dict[str, Any] | None
    created_at: str | None
    updated_at: str | None
    version: int


@dataclass(frozen=True)
class IntakeItemOutput:
    """Structural view of one discovered file (no content metadata yet)."""

    id: str
    session_id: str
    title: str
    original_path: str
    relative_path: str
    extension: str
    size_bytes: int
    mime_type: str | None
    sha256: str | None
    staged_key: str | None
    status: str
    stage: str
    attempts: int
    stage_history: list[dict[str, Any]]
    error: dict[str, Any] | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class ListIntakeSessionsResult:
    """Boundary result for a paginated session listing."""

    items: list[IntakeSessionOutput] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class ListIntakeItemsResult:
    """Boundary result for a paginated item listing."""

    items: list[IntakeItemOutput] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 50


# --------------------------------------------------------------------------
# Object -> boundary builders (mirrors ``dtos/document.py`` from_domain)
# --------------------------------------------------------------------------

from app.domain.entities.object import UniversalObject  # noqa: E402


def _meta_int(obj: UniversalObject, key: str, default: int = 0) -> int:
    raw = obj.metadata.get_value(key)
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def intake_item_facts(obj: UniversalObject) -> IntakeItemFacts:
    """Fold one item object into the facts used by live aggregation."""

    return IntakeItemFacts(
        status=IntakeItemStatus(obj.metadata.get_value(KEY_INTAKE_STATUS) or "pending"),
        stage=IntakeStage(obj.metadata.get_value(KEY_ITEM_STAGE) or "enumerate"),
        size_bytes=_meta_int(obj, KEY_SIZE_BYTES),
        extension=obj.metadata.get_value(KEY_EXTENSION) or "",
        mime_type=obj.metadata.get_value(KEY_MIME_TYPE),
        has_hash=bool(obj.metadata.get_value(KEY_SHA256)),
        has_staged_key=bool(obj.metadata.get_value(KEY_STAGED_KEY)),
    )


def intake_item_output(obj: UniversalObject) -> IntakeItemOutput:
    """Full structural view of one intake item."""

    return IntakeItemOutput(
        id=str(obj.id),
        session_id=obj.metadata.get_value(KEY_SESSION_ID) or "",
        title=obj.title,
        original_path=obj.metadata.get_value(KEY_ORIGINAL_PATH) or "",
        relative_path=obj.metadata.get_value(KEY_RELATIVE_PATH) or obj.title,
        extension=obj.metadata.get_value(KEY_EXTENSION) or "",
        size_bytes=_meta_int(obj, KEY_SIZE_BYTES),
        mime_type=obj.metadata.get_value(KEY_MIME_TYPE),
        sha256=obj.metadata.get_value(KEY_SHA256),
        staged_key=obj.metadata.get_value(KEY_STAGED_KEY),
        status=obj.metadata.get_value(KEY_INTAKE_STATUS) or "pending",
        stage=obj.metadata.get_value(KEY_ITEM_STAGE) or "enumerate",
        attempts=_meta_int(obj, KEY_ATTEMPTS),
        stage_history=json_decode(obj.metadata.get_value(KEY_STAGE_HISTORY), []),
        error=json_decode(obj.metadata.get_value(KEY_ERROR), None),
        created_at=obj.audit.created_at.isoformat() if obj.audit else None,
        updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
    )


def intake_session_status_of(obj: UniversalObject) -> IntakeSessionStatus:
    raw = obj.metadata.get_value(KEY_INTAKE_STATUS) or IntakeSessionStatus.QUEUED.value
    return IntakeSessionStatus(raw)


def intake_session_progress_of(
    obj: UniversalObject, items: list[UniversalObject]
) -> dict[str, Any]:
    """Progress payload recomputed from live items (never from checkpoints)."""

    checkpoint = json_decode(obj.metadata.get_value(KEY_PROGRESS), {})
    enumerated = bool(checkpoint.get("enumerated"))
    summary = summarize_items([intake_item_facts(i) for i in items], enumerated=enumerated)
    return {
        "total": summary["total_items"],
        "processed": summary["processed_items"],
        "percent": summary["percent"],
        "pending": summary["pending"],
        "staged": summary["staged"],
        "hashed": summary["hashed"],
        "awaiting_review": summary["awaiting_review"],
        "errors": summary["errors"],
    }


def intake_session_statistics_of(
    obj: UniversalObject, items: list[UniversalObject]
) -> dict[str, Any]:
    """Statistics payload = live item aggregation + enumeration seed."""

    stored = json_decode(obj.metadata.get_value(KEY_STATISTICS), {})
    checkpoint = json_decode(obj.metadata.get_value(KEY_PROGRESS), {})
    live = summarize_items(
        [intake_item_facts(i) for i in items], enumerated=bool(checkpoint.get("enumerated"))
    )
    return {
        **live,
        "skipped_junk": int(stored.get("skipped_junk") or 0),
        "skipped_junk_samples": list(stored.get("skipped_junk_samples") or []),
    }


def intake_session_output(obj: UniversalObject, items: list[UniversalObject]) -> IntakeSessionOutput:
    """Full dashboard payload for one session."""

    return IntakeSessionOutput(
        id=str(obj.id),
        title=obj.title,
        source=json_decode(obj.metadata.get_value(KEY_SOURCE), {}),
        status=intake_session_status_of(obj).value,
        current_stage=obj.metadata.get_value(KEY_CURRENT_STAGE) or IntakeStage.ENUMERATE.value,
        progress=intake_session_progress_of(obj, items),
        statistics=intake_session_statistics_of(obj, items),
        summary=obj.metadata.get_value(KEY_SUMMARY),
        error=json_decode(obj.metadata.get_value(KEY_ERROR), None),
        created_at=obj.audit.created_at.isoformat() if obj.audit else None,
        updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
        version=obj.version,
    )


def intake_progress_output(obj: UniversalObject, items: list[UniversalObject]) -> IntakeProgressOutput:
    """Lean polling payload."""

    progress = intake_session_progress_of(obj, items)
    return IntakeProgressOutput(
        session_id=str(obj.id),
        status=intake_session_status_of(obj).value,
        current_stage=obj.metadata.get_value(KEY_CURRENT_STAGE) or IntakeStage.ENUMERATE.value,
        total_items=progress["total"],
        processed_items=progress["processed"],
        percent=progress["percent"],
        counts={
            "pending": progress["pending"],
            "staged": progress["staged"],
            "hashed": progress["hashed"],
            "awaiting_review": progress["awaiting_review"],
            "errors": progress["errors"],
        },
        updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
    )
