"""Intake Foundations (v2) — boundary DTOs for sessions and items.

One intake *session* represents one import operation (folder import, multi-file
drop, ZIP import later); one intake *item* represents one discovered file.
Both are plain Universal Objects — new ``ObjectType`` members appended to the
frozen enum, richer state held as JSON-encoded metadata entries written with
``L1_SYSTEM`` / ``Provenance.SYSTEM`` so a human-asserted value can never be
silently overwritten by the pipeline (FR-MET-009).

Structural information plus the M2 extraction summary: path, name, extension,
size, detected MIME, SHA-256 hash, stage cursor and — since M2 landed — the
extraction descriptor (text itself lives in separate ``intake-extracted/``
storage blobs). Still no classification, no relationships.

No framework imports here — pure boundary shapes mirroring ``dtos/document.py``.
"""
from __future__ import annotations

import datetime as dt
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
    # M2 Part 3: visible while a worker actively processes the item.
    # ``EXTRACTING`` is the first attempt; ``RETRYING`` every later one.
    EXTRACTING = "extracting"
    RETRYING = "retrying"
    AWAITING_REVIEW = "awaiting_review"
    ERROR = "error"
    # M9 review workflow: the item was rejected by a human reviewer.
    # Terminal — a rejected item can never be committed.
    REJECTED = "rejected"
    # Sprint-3 M1 (commit engine): the item was promoted to a Document.
    # Terminal and idempotent — a committed item is never committed twice.
    COMMITTED = "committed"


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


#: Stages every item walks in M1. EXTRACT became real in M2 (deterministic
#: engine); everything past EXTRACT is executed by the structurally-real
#: *deferred* handler: the transition, timing and stage record are production
#: code; the domain work arrives in later milestones.
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
#: (EXTRACT left this map when the M2 deterministic engine landed; OCR for
#: scans/images of it remains M10.)
DEFERRED_STAGE_MILESTONES: dict[IntakeStage, str] = {
    IntakeStage.CLASSIFY: "M5 (classification)",
    IntakeStage.MATCH: "M7 (record matching)",
    IntakeStage.PROPOSE: "M8 (proposal engine)",
}

#: Terminal item statuses for M1 (commit arrives with the proposal engine).
TERMINAL_ITEM_STATUSES: frozenset[IntakeItemStatus] = frozenset(
    {IntakeItemStatus.AWAITING_REVIEW, IntakeItemStatus.ERROR, IntakeItemStatus.REJECTED}
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
# M2 Part 3 (queue & recovery):
# - durable single-worker lease on the session (crash witness + cross-instance
#   guard): JSON {"owner", "acquired_at", "heartbeat_at"}
KEY_LEASE = "intake.worker"
# - the item currently being processed (live progress: current filename)
KEY_CURRENT_ITEM = "intake.current_item"
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
# M2 extraction keys (descriptor JSON + text-blob key — text itself is a
# separate storage blob under the intake-extracted/ prefix, never staged data)
KEY_EXTRACTION = "intake.extraction"
KEY_EXTRACTED_KEY = "intake.extracted_key"
# Sprint-3 M1: the Document Object id the item was committed to (set once,
# read for idempotency).
KEY_COMMITTED_DOCUMENT = "intake.committed_document"
# M9: the human review decision for one item (approved | rejected), kept
# as a durable audit fact next to the committed-document pointer.
KEY_REVIEW_DECISION = "intake.review_decision"


# Sprint-3 M2 (proposal engine): the generated reviewable proposal for an
# item, stored as JSON metadata. Persisted once per item; the review
# workflow edits it in place before commit.
KEY_PROPOSAL = "intake.proposal"


@dataclass
class ItemProposal:
    """A reviewable proposal for one intake item (Sprint-3 M2).

    Generated deterministically from the item's real facts; human-editable
    through the review workflow before the item is committed.
    """

    title: str
    document_type: str
    description: str
    confidence: float


@dataclass
class CommitItemOutput:
    """Result of committing one intake item to a Document (Sprint-3 M1)."""

    item_id: str
    document_id: str
    document_title: str


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
    extraction_status: str | None  # M2: "extracted" / "unsupported" / None
    attempts: int = 0  # M2.3: retry mechanics (terminal at RETRY_LIMIT)
    needs_ocr: bool = False  # M2.3: pdf + extracted + zero characters (real)
    extract_seconds: float | None = None  # M2.3: last extract-step duration


def summarize_items(facts: list[IntakeItemFacts], *, enumerated: bool) -> dict[str, Any]:
    """Compute the progress + statistics view from live item facts."""

    total = len(facts)
    counts = {
        IntakeItemStatus.PENDING.value: 0,
        IntakeItemStatus.STAGED.value: 0,
        IntakeItemStatus.EXTRACTING.value: 0,
        IntakeItemStatus.RETRYING.value: 0,
        IntakeItemStatus.AWAITING_REVIEW.value: 0,
        IntakeItemStatus.ERROR.value: 0,
        IntakeItemStatus.REJECTED.value: 0,  # M9 terminal
        IntakeItemStatus.COMMITTED.value: 0,  # M9 terminal
    }
    hashed = 0
    staged = 0
    extracted = 0
    unsupported = 0
    needs_ocr = 0
    retryable = 0
    total_bytes = 0
    by_extension: dict[str, int] = {}
    by_mime: dict[str, int] = {}
    for fact in facts:
        counts[fact.status.value] = counts.get(fact.status.value, 0) + 1
        total_bytes += max(fact.size_bytes, 0)
        if fact.extension:
            by_extension[fact.extension] = by_extension.get(fact.extension, 0) + 1
        if fact.mime_type:
            by_mime[fact.mime_type] = by_mime.get(fact.mime_type, 0) + 1
        if fact.has_hash:
            hashed += 1
        if fact.has_staged_key:
            staged += 1
        if fact.extraction_status == "extracted":
            extracted += 1
        elif fact.extraction_status == "unsupported":
            unsupported += 1
        if fact.needs_ocr:
            needs_ocr += 1
        if fact.status is IntakeItemStatus.ERROR and fact.attempts < RETRY_LIMIT:
            retryable += 1
    processed = (
        counts[IntakeItemStatus.AWAITING_REVIEW.value]
        + counts[IntakeItemStatus.COMMITTED.value]
        + counts[IntakeItemStatus.ERROR.value]
    )
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
        "committed_items": counts[IntakeItemStatus.COMMITTED.value],
        "errors": counts[IntakeItemStatus.ERROR.value],
        "total_bytes": total_bytes,
        "by_extension": dict(sorted(by_extension.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_mime": dict(sorted(by_mime.items(), key=lambda kv: (-kv[1], kv[0]))),
        # M2 extraction rollups (live like everything else — no checkpoints)
        "extracted_items": extracted,
        "unsupported_items": unsupported,
        # M2.3 queue counters (live while a worker drains)
        "extracting": counts[IntakeItemStatus.EXTRACTING.value],
        "retrying": counts[IntakeItemStatus.RETRYING.value],
        "needs_ocr_items": needs_ocr,
        "retryable_items": retryable,
    }


def extraction_timing(facts: list[IntakeItemFacts]) -> dict[str, Any]:
    """Measured extraction speed over the items that honestly produced a
    duration — never estimated from wall clocks or fabricated when empty.

    Averages come from real ``extract`` stage-history durations; the ETA is
    ``remaining unfinished items × average`` and stays ``None`` until at
    least one finished extraction exists to measure.
    """

    durations = [f.extract_seconds for f in facts if f.extract_seconds is not None]
    if not durations:
        return {
            "avg_seconds_per_item": None,
            "items_per_minute": None,
        }
    avg = sum(durations) / len(durations)
    return {
        "avg_seconds_per_item": round(avg, 3),
        "items_per_minute": round(60.0 / avg, 1) if avg > 0 else None,
    }


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IntakeProgressOutput:
    """Full polling payload for one session (M2.3: live queue + speed/ETA)."""

    session_id: str
    status: str
    current_stage: str
    total_items: int
    processed_items: int
    percent: float
    counts: dict[str, int]
    updated_at: str | None
    # M2.3 additive fields (None until honestly measurable)
    current_item: str | None = None
    remaining_items: int = 0
    avg_seconds_per_item: float | None = None
    items_per_minute: float | None = None
    eta_seconds: int | None = None


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
    extraction: dict[str, Any] | None  # M2 descriptor (None until EXTRACT runs)
    created_at: str | None
    updated_at: str | None
    review_decision: str | None = None  # M9: approved | rejected | None
    document_id: str | None = None  # M9: the committed document, once committed


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

    descriptor = _extraction_dict_of(obj)
    return IntakeItemFacts(
        status=IntakeItemStatus(obj.metadata.get_value(KEY_INTAKE_STATUS) or "pending"),
        stage=IntakeStage(obj.metadata.get_value(KEY_ITEM_STAGE) or "enumerate"),
        size_bytes=_meta_int(obj, KEY_SIZE_BYTES),
        extension=obj.metadata.get_value(KEY_EXTENSION) or "",
        mime_type=obj.metadata.get_value(KEY_MIME_TYPE),
        has_hash=bool(obj.metadata.get_value(KEY_SHA256)),
        has_staged_key=bool(obj.metadata.get_value(KEY_STAGED_KEY)),
        extraction_status=str(descriptor["status"]) if descriptor else None,
        attempts=_meta_int(obj, KEY_ATTEMPTS),
        needs_ocr=_needs_ocr_of(descriptor),
        extract_seconds=_extract_seconds_of(obj),
    )


def _extraction_dict_of(obj: UniversalObject) -> dict[str, Any] | None:
    """The decoded M2 descriptor dict, or ``None`` when absent/malformed."""

    data = json_decode(obj.metadata.get_value(KEY_EXTRACTION), None)
    if isinstance(data, dict) and data.get("status") in ("extracted", "unsupported"):
        return data
    return None


def _needs_ocr_of(descriptor: dict[str, Any] | None) -> bool:
    """Honest needs-OCR signal: a PDF whose extraction yielded zero characters
    (no text layer). The discriminator is ``format``, not the engine name."""

    if not isinstance(descriptor, dict):
        return False
    return (
        descriptor.get("status") == "extracted"
        and descriptor.get("format") == "pdf"
        and (descriptor.get("character_count") or 0) == 0
    )


def _extract_seconds_of(obj: UniversalObject) -> float | None:
    """Duration of the *last* recorded extract step (real wall time), or None."""

    history = json_decode(obj.metadata.get_value(KEY_STAGE_HISTORY), [])
    if not isinstance(history, list):
        return None
    for record in reversed(history):
        if not isinstance(record, dict) or record.get("stage") != IntakeStage.EXTRACT.value:
            continue
        try:
            entered = dt.datetime.fromisoformat(str(record.get("entered_at") or ""))
            exited = dt.datetime.fromisoformat(str(record.get("exited_at") or ""))
        except ValueError:
            return None
        return max(0.0, (exited - entered).total_seconds())
    return None


def intake_item_extraction(obj: UniversalObject) -> dict[str, Any] | None:
    """The full M2 descriptor as an API-ready dict (None before EXTRACT)."""

    data = json_decode(obj.metadata.get_value(KEY_EXTRACTION), None)
    if not isinstance(data, dict) or data.get("status") not in ("extracted", "unsupported"):
        return None
    return data


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
        extraction=intake_item_extraction(obj),
        created_at=obj.audit.created_at.isoformat() if obj.audit else None,
        updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
        review_decision=obj.metadata.get_value(KEY_REVIEW_DECISION),
        document_id=obj.metadata.get_value(KEY_COMMITTED_DOCUMENT),
    )


def intake_session_status_of(obj: UniversalObject) -> IntakeSessionStatus:
    raw = obj.metadata.get_value(KEY_INTAKE_STATUS) or IntakeSessionStatus.QUEUED.value
    return IntakeSessionStatus(raw)


def intake_session_progress_of(
    obj: UniversalObject, items: list[UniversalObject]
) -> dict[str, Any]:
    """Progress payload recomputed from live items (never from checkpoints).

    M2.3 additions (all live, all additive): queue counters, the currently
    processed filename, measured extraction speed and a data-driven ETA —
    every number derived from recorded stage history, nothing simulated.
    """

    checkpoint = json_decode(obj.metadata.get_value(KEY_PROGRESS), {})
    enumerated = bool(checkpoint.get("enumerated"))
    facts = [intake_item_facts(i) for i in items]
    summary = summarize_items(facts, enumerated=enumerated)
    timing = extraction_timing(facts)
    # Work the queue still HONESTLY owes: everything not in a final resting
    # state — pending/staged/active attempts PLUS failed items that still own
    # retry attempts. A permanently-failed item (attempts exhausted) is at
    # rest and stays out; a completed-with-errors session keeps its retryable
    # remainder visible until someone acts on it.
    remaining = (
        summary["total_items"]
        - summary["awaiting_review"]
        - summary["committed_items"]
        - (summary["errors"] - summary["retryable_items"])
    )
    avg = timing["avg_seconds_per_item"]
    return {
        "total": summary["total_items"],
        "processed": summary["processed_items"],
        "percent": summary["percent"],
        "pending": summary["pending"],
        "staged": summary["staged"],
        "hashed": summary["hashed"],
        "awaiting_review": summary["awaiting_review"],
        "committed_items": summary["committed_items"],
        "errors": summary["errors"],
        # M2.3 — queue counters
        "extracting": summary["extracting"],
        "retrying": summary["retrying"],
        "retryable_items": summary["retryable_items"],
        "remaining_items": remaining,
        "extracted_items": summary["extracted_items"],
        "unsupported_items": summary["unsupported_items"],
        "needs_ocr_items": summary["needs_ocr_items"],
        # M2.3 — live foreground (current filename + measured speed + ETA)
        "current_item": json_decode(obj.metadata.get_value(KEY_CURRENT_ITEM), None),
        "current_stage": obj.metadata.get_value(KEY_CURRENT_STAGE)
        or IntakeStage.ENUMERATE.value,
        "avg_seconds_per_item": avg,
        "items_per_minute": timing["items_per_minute"],
        "eta_seconds": round(remaining * avg) if avg is not None else None,
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
    """Full polling payload (queue counters + current item + speed/ETA)."""

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
            "committed": progress["committed_items"],
            "errors": progress["errors"],
            "extracting": progress["extracting"],
            "retrying": progress["retrying"],
            "retryable": progress["retryable_items"],
            "extracted": progress["extracted_items"],
            "unsupported": progress["unsupported_items"],
            "needs_ocr": progress["needs_ocr_items"],
        },
        updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
        current_item=progress["current_item"],
        remaining_items=progress["remaining_items"],
        avg_seconds_per_item=progress["avg_seconds_per_item"],
        items_per_minute=progress["items_per_minute"],
        eta_seconds=progress["eta_seconds"],
    )
