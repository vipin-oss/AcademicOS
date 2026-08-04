"""Intake pipeline vocabulary and pure helpers (M1).

Everything here is deterministic, side-effect-free and unit-tested on its
own: stage sequencing, junk-file hygiene, staging-key hygiene, MIME sniffing
and small formatters. The runner composes these with repository/storage
ports; nothing here knows about either.

Design notes
------------
- Stage history records are *data*: ``{"stage", "entered_at", "exited_at",
  "result"}`` — later milestones read them for provenance ("why is this file
  here, how long did each step take").
- Deferred stages are a first-class, honest mechanism, not a TODO: the
  transition/timing/record machinery is production code; the domain work per
  stage arrives exactly where ``DEFERRED_STAGE_MILESTONES`` says it will.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import mimetypes
import posixpath
from dataclasses import dataclass, field

from app.application.dtos.intake import (
    DEFERRED_STAGE_MILESTONES,
    JUNK_FILE_NAMES,
    JUNK_FILE_PREFIXES,
    JUNK_FILE_SUFFIXES,
    STAGING_PREFIX,
    IntakeStage,
)

_CHUNK = 1024 * 1024  # 1 MiB streaming chunk for copy/hash pipelines


def utcnow_iso() -> str:
    """UTC timestamp string used across intake metadata."""

    return dt.datetime.now(dt.UTC).isoformat()


# --------------------------------------------------------------------------
# Junk-file hygiene (deterministic; skipped files never become items)
# --------------------------------------------------------------------------


def should_skip_file(filename: str) -> bool:
    """True for OS noise / partial-download files inside a folder walk."""

    name = filename.strip().lower()
    if not name:
        return True
    if name in JUNK_FILE_NAMES:
        return True
    if name.startswith("."):
        return True
    if any(name.startswith(prefix.lower()) for prefix in JUNK_FILE_PREFIXES):
        return True
    return any(name.endswith(suffix) for suffix in JUNK_FILE_SUFFIXES)


def should_skip_dir(dirname: str) -> bool:
    """True for directories pruned from a folder walk (hidden VCS/OS dirs)."""

    return dirname.startswith(".")


# --------------------------------------------------------------------------
# Storage-key hygiene
# --------------------------------------------------------------------------

_SAFE_SEGMENT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
_MAX_SEGMENT = 120


def sanitize_segment(segment: str) -> str:
    """Make one staging-key segment safe on every filesystem (mirrors the
    documents module doctrine but keeps spaces for human-readable keys)."""

    cleaned = "".join(ch if ch in _SAFE_SEGMENT_CHARS else "_" for ch in segment)
    cleaned = cleaned.strip(" ._")
    return (cleaned or "unnamed")[:_MAX_SEGMENT]


def sanitize_relative_path(rel: str) -> str:
    """Normalise a walk-relative path into a safe posix key fragment.

    Any traversal (``..``, absolute roots, backslashes, duplicate slashes) is
    collapsed away — staging keys can therefore never escape the session
    prefix, even for hostile ZIP entries later.
    """

    rel = rel.replace("\\", "/")
    parts: list[str] = []
    for raw in posixpath.normpath(rel).split("/"):
        if raw in ("", ".", ".."):
            continue
        parts.append(sanitize_segment(raw))
    return "/".join(parts) or "unnamed"


def staging_key_for(session_id: str, relative_path: str) -> str:
    """``intake/<session>/<sanitised relative path>`` — deterministic, so a
    resumed drain rewrites the same key instead of duplicating blobs."""

    return f"{STAGING_PREFIX}/{sanitize_segment(session_id)}/{sanitize_relative_path(relative_path)}"


# --------------------------------------------------------------------------
# MIME sniffing (magic bytes first; extension refines container formats)
# --------------------------------------------------------------------------

# (signature bytes, offset, base mime)
_SIGNATURES: tuple[tuple[bytes, int, str], ...] = (
    (b"%PDF-", 0, "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"PK\x03\x04", 0, "application/zip"),
    (b"PK\x05\x06", 0, "application/zip"),  # empty archive
    (b"\x1f\x8b", 0, "application/gzip"),
    (b"RIFF", 0, "application/riff"),
    (b"{\n", 0, "application/json"),
    (b"[pdf]", 0, "application/pdf"),
)

#: Extension refinement when the magic bytes say "zip container"
#: (keys match ``detect_extension`` output — no leading dot).
_ZIP_CONTAINER_MIMES: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_OCTET_STREAM = "application/octet-stream"


def detect_extension(filename: str) -> str:
    """Lower-case extension without the dot (``""`` when absent)."""

    base = filename.rsplit("/", 1)[-1]
    if "." not in base or base.endswith("."):
        return ""
    return base.rsplit(".", 1)[-1].lower()


def sniff_mime(head: bytes, filename: str) -> str:
    """Deterministic MIME detection: magic bytes, with extension refinement
    for OOXML zip containers; stdlib ``mimetypes`` as the fallback table."""

    for signature, offset, mime in _SIGNATURES:
        if head[offset : offset + len(signature)] == signature:
            if mime == "application/zip":
                refined = _ZIP_CONTAINER_MIMES.get(detect_extension(filename))
                return refined or mime
            return mime
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or _OCTET_STREAM


# --------------------------------------------------------------------------
# Hashing / sizing
# --------------------------------------------------------------------------


def new_hasher() -> hashlib._Hash:
    """The canonical content hash for intake (documented in V2 §7)."""

    return hashlib.sha256()


def digest_of(data: bytes) -> str:
    """SHA-256 hex digest for an in-memory payload."""

    return hashlib.sha256(data).hexdigest()


def human_bytes(num: int) -> str:
    """Compact human size for summaries and the dashboard."""

    value = float(max(num, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


# --------------------------------------------------------------------------
# Stage records (append-only provenance per item)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StageRecord:
    """One executed stage step: timings + structured outcome."""

    stage: str
    entered_at: str
    exited_at: str
    result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "entered_at": self.entered_at,
            "exited_at": self.exited_at,
            "result": self.result,
        }


def begin_record(stage: IntakeStage) -> tuple[IntakeStage, str]:
    """Start-of-step marker used by the runner around each handler."""

    return stage, utcnow_iso()


def finish_record(stage: IntakeStage, entered_at: str, result: dict) -> StageRecord:
    return StageRecord(stage=stage.value, entered_at=entered_at, exited_at=utcnow_iso(), result=result)


def deferred_stage_result(stage: IntakeStage) -> dict:
    """The honest outcome of a placeholder stage: executed, recorded, and the
    exact milestone that will own its real logic."""

    milestone = DEFERRED_STAGE_MILESTONES.get(stage, "a later milestone")
    return {"deferred": True, "milestone": milestone}


# --------------------------------------------------------------------------
# Walk helper (shared by runner + tests; deterministic ordering)
# --------------------------------------------------------------------------


def normalize_walk_relpath(normalized_rel: str) -> str:
    """POSIX-normalise a relative path produced during a folder walk."""

    return posixpath.normpath(normalized_rel.replace("\\", "/"))


class ItemStageError(Exception):
    """Per-item, per-stage failure: captured on the item (never fails the run).

    The message is user-facing (surfaced verbatim in the dashboard), so it
    must stay factual and actionable.
    """
