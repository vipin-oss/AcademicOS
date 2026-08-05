"""Unit tests for the M2 Part 3 extraction queue & job management.

Deterministic seams only: in-memory repo/storage fakes drive the REAL
runner, REAL extraction service and REAL job manager — no fake queues, no
fake timers. The lease clock is the only injectable clock, and it measures
the same wall time production measures.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import queue
import threading

from sqlalchemy.exc import OperationalError

from app.application.dtos.intake import (
    INTAKE_ACTOR,
    ITEM_STAGE_SEQUENCE,
    KEY_ATTEMPTS,
    KEY_CURRENT_ITEM,
    KEY_ERROR,
    KEY_EXTRACTED_KEY,
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_LEASE,
    KEY_PROGRESS,
    KEY_SESSION_ID,
    KEY_STAGE_HISTORY,
    IntakeItemFacts,
    IntakeItemStatus,
    IntakeStage,
    extraction_timing,
    intake_item_facts,
    intake_session_progress_of,
    json_decode,
    json_encode,
    summarize_items,
)
from app.application.intake.extraction.service import ExtractionService
from app.application.intake.jobs import IntakeJobManager
from app.application.intake.pipeline import extracted_key_for, utcnow_iso
from app.application.intake.runner import IntakeRunner
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.infrastructure.extraction import build_document_parsers
from app.tests.unit.extraction_fixtures import make_pdf_bytes

SID = "obj:intake_session:TESTSID00001"

# ---------------------------------------------------------------- helpers
def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _put(obj: UniversalObject, key: str, value: str) -> None:
    obj.set_metadata(_entry(key, value), actor=INTAKE_ACTOR)


class InMemoryRepo:
    """Minimal ObjectRepository stand-in (unit layer — ports, not ORM)."""

    def __init__(self) -> None:
        self.store: dict[str, UniversalObject] = {}

    def get_by_id(self, object_id) -> UniversalObject | None:
        return self.store.get(str(object_id))

    def save(self, obj: UniversalObject) -> UniversalObject:
        self.store[str(obj.id)] = obj
        return obj

    def find(self, *, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self.store.values() if o.object_type is object_type]


class FakeStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.saves: list[str] = []

    def save(self, key: str, content: bytes) -> None:
        self.saves.append(key)
        self.blobs[key] = bytes(content)

    def read(self, key: str) -> bytes:
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


def mk_session(repo: InMemoryRepo, *, status: str = "queued", enumerated: bool = True) -> UniversalObject:
    session = UniversalObject.create(
        object_type=ObjectType.INTAKE_SESSION,
        title="q",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry(KEY_SESSION_ID, SID),
                _entry(KEY_INTAKE_STATUS, status),
                _entry(KEY_PROGRESS, json_encode({"enumerated": enumerated})),
                _entry("intake.source", json_encode({"kind": "folder", "path": "/nope", "display": "/nope"})),
            )
        ),
    )
    # The runner resolves items by session_id; the session id IS its object id.
    session_id = str(session.id)
    _put(session, KEY_SESSION_ID, session_id)
    repo.save(session)
    return session


def mk_item(
    repo: InMemoryRepo,
    session: UniversalObject,
    rel: str,
    *,
    status: str = "pending",
    extension: str = "txt",
    staged: bool = True,
    blob: bytes = b"hello",
    attempts: int = 0,
    descriptor: dict | None = None,
    extracted_blob: bytes | None = None,
    storage: FakeStorage | None = None,
    history: list[dict] | None = None,
) -> UniversalObject:
    item = UniversalObject.create(
        object_type=ObjectType.INTAKE_ITEM,
        title=rel.rsplit("/", 1)[-1],
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=()),
    )
    _put(item, KEY_SESSION_ID, str(session.id))
    _put(item, KEY_INTAKE_STATUS, status)
    _put(item, "intake.relative_path", rel)
    _put(item, "intake.original_path", f"/src/{rel}")
    _put(item, "intake.extension", extension)
    _put(item, "intake.size_bytes", str(len(blob)))
    _put(item, KEY_ATTEMPTS, str(attempts))
    if staged:
        key = f"intake/{str(session.id).replace(':', '_')}/{rel}"
        _put(item, "intake.staged_key", key)
        _put(item, "intake.sha256", hashlib.sha256(blob).hexdigest())
        if storage is not None:
            storage.save(key, blob)
    if descriptor is not None:
        _put(item, KEY_EXTRACTION, json_encode(descriptor))
        _put(item, KEY_EXTRACTED_KEY, descriptor.get("text_key") or "")
    if extracted_blob is not None and storage is not None:
        storage.save(extracted_key_for(str(session.id), rel), extracted_blob)
    if history is not None:
        _put(item, KEY_STAGE_HISTORY, json_encode(history))
    repo.save(item)
    return item


def run_drain(repo: InMemoryRepo, storage: FakeStorage, session: UniversalObject) -> IntakeRunner:
    runner = IntakeRunner(
        repo, storage, str(session.id), lambda: "go", build_document_parsers()
    )
    runner.run()
    return runner


def extract_record(seconds: float, at: dt.datetime | None = None) -> dict:
    at = at or dt.datetime(2026, 8, 4, 10, 0, 0, tzinfo=dt.UTC)
    return {
        "stage": "extract",
        "entered_at": at.isoformat(),
        "exited_at": (at + dt.timedelta(seconds=seconds)).isoformat(),
        "result": {},
    }


# --------------------------------------------------------- facts/counters
class TestSummarizeCounters:
    def test_extracting_retrying_needs_ocr_retryable_counters(self) -> None:
        facts = [
            IntakeItemFacts(IntakeItemStatus.PENDING, IntakeStage.ENUMERATE, 1, "txt", None, False, False, None),
            IntakeItemFacts(IntakeItemStatus.EXTRACTING, IntakeStage.EXTRACT, 1, "txt", None, True, True, None),
            IntakeItemFacts(IntakeItemStatus.RETRYING, IntakeStage.EXTRACT, 1, "pdf", None, True, True, None, attempts=2),
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 1, "pdf", "application/pdf", True, True, "extracted", attempts=1, needs_ocr=True),
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 1, "png", "image/png", True, True, "unsupported", attempts=1),
            IntakeItemFacts(IntakeItemStatus.ERROR, IntakeStage.EXTRACT, 1, "pdf", "application/pdf", True, True, None, attempts=1),
            IntakeItemFacts(IntakeItemStatus.ERROR, IntakeStage.EXTRACT, 1, "pdf", "application/pdf", True, True, None, attempts=3),
        ]
        summary = summarize_items(facts, enumerated=True)
        assert summary["extracting"] == 1
        assert summary["retrying"] == 1
        assert summary["needs_ocr_items"] == 1
        assert summary["retryable_items"] == 1  # attempts=1<3; attempts=3 is terminal
        assert summary["unsupported_items"] == 1
        assert summary["extracted_items"] == 1
        assert summary["errors"] == 2
        assert summary["awaiting_review"] == 2

    def test_timing_from_measured_extract_durations(self) -> None:
        facts = [
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 1, "txt", None, True, True, "extracted", extract_seconds=2.0),
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 1, "txt", None, True, True, "extracted", extract_seconds=4.0),
            IntakeItemFacts(IntakeItemStatus.PENDING, IntakeStage.ENUMERATE, 1, "txt", None, False, False, None),
        ]
        timing = extraction_timing(facts)
        assert timing["avg_seconds_per_item"] == 3.0
        assert timing["items_per_minute"] == 20.0

    def test_timing_stays_null_without_samples(self) -> None:
        facts = [
            IntakeItemFacts(IntakeItemStatus.PENDING, IntakeStage.ENUMERATE, 1, "txt", None, False, False, None),
        ]
        timing = extraction_timing(facts)
        assert timing["avg_seconds_per_item"] is None
        assert timing["items_per_minute"] is None


class TestFactsDerivations:
    def test_needs_ocr_honest_derivation(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo)
        base = {"status": "extracted", "sha256": hashlib.sha256(b"hello").hexdigest(), "text_key": "k"}
        ocr = mk_item(repo, session, "a.pdf", extension="pdf", descriptor={**base, "format": "pdf", "character_count": 0})
        fine = mk_item(repo, session, "b.pdf", extension="pdf", descriptor={**base, "format": "pdf", "character_count": 10})
        txt = mk_item(repo, session, "c.txt", extension="txt", descriptor={**base, "format": "text", "character_count": 0})
        assert intake_item_facts(ocr).needs_ocr is True
        assert intake_item_facts(fine).needs_ocr is False
        assert intake_item_facts(txt).needs_ocr is False  # empty txt is empty, not an OCR case

    def test_extract_seconds_parsed_from_last_extract_record(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo)
        item = mk_item(
            repo, session, "a.txt",
            history=[
                extract_record(2.0, dt.datetime(2026, 8, 4, 10, 0, 0, tzinfo=dt.UTC)),
                extract_record(5.5, dt.datetime(2026, 8, 4, 11, 0, 0, tzinfo=dt.UTC)),
            ],
        )
        assert intake_item_facts(item).extract_seconds == 5.5

    def test_extract_seconds_none_without_history_or_on_bad_json(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo)
        item = mk_item(repo, session, "a.txt", history=[])
        assert intake_item_facts(item).extract_seconds is None
        _put(item, KEY_STAGE_HISTORY, "{broken")
        assert intake_item_facts(item).extract_seconds is None


class TestProgressView:
    def test_live_progress_fields_eta_and_remaining(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        queued = mk_item(repo, session, "next/queued.txt")
        done = mk_item(
            repo, session, "done.txt", status="awaiting_review",
            history=[extract_record(2.0)], descriptor={
                "status": "extracted", "sha256": hashlib.sha256(b"hello").hexdigest(),
                "text_key": "k", "format": "text", "character_count": 5,
            },
        )
        failing = mk_item(
            repo, session, "bad.pdf", extension="pdf", status="error", attempts=1
        )
        _put(session, KEY_CURRENT_ITEM, json_encode("next/queued.txt"))
        progress = intake_session_progress_of(session, [queued, done, failing])
        assert progress["current_item"] == "next/queued.txt"
        assert progress["avg_seconds_per_item"] == 2.0
        assert progress["items_per_minute"] == 30.0
        assert progress["retryable_items"] == 1
        # unfinished: 1 queued + 1 retryable error = 2 → eta = 2 × 2s
        assert progress["remaining_items"] == 2
        assert progress["eta_seconds"] == 4
        assert progress["extracted_items"] == 1
        # settled terminal
        _put(session, KEY_CURRENT_ITEM, json_encode(None))
        settled = intake_session_progress_of(session, [done])
        assert settled["current_item"] is None
        assert settled["remaining_items"] == 0
        assert settled["eta_seconds"] == 0


# ------------------------------------------------------ extraction reuse
class TestExtractionReuse:
    def _descriptor_for(self, session_id: str, rel: str, blob: bytes) -> dict:
        return {
            "status": "extracted",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "text_key": extracted_key_for(session_id, rel),
            "format": "pdf",
            "character_count": 10,
            "extracted_at": utcnow_iso(),
        }

    def test_reuse_returns_completed_work_untouched(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        blob = make_pdf_bytes("stable text")
        descriptor = self._descriptor_for(str(session.id), "a.pdf", blob)
        item = mk_item(
            repo, session, "a.pdf", extension="pdf", blob=blob,
            descriptor=descriptor, extracted_blob=b"stable text", storage=storage,
        )
        saves_before = len(storage.saves)
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=str(session.id))
        assert record == {"reused": True, "status": "extracted"}
        assert len(storage.saves) == saves_before  # no text blob rewritten
        # descriptor untouched byte-for-byte (extracted_at identical)
        assert json_decode(item.metadata.get_value(KEY_EXTRACTION), None)["extracted_at"] == descriptor["extracted_at"]

    def test_sha_mismatch_guards_against_stale_descriptors(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        blob = make_pdf_bytes("new content")
        stale_sha = hashlib.sha256(b"different-bytes").hexdigest()
        descriptor = self._descriptor_for(str(session.id), "a.pdf", b"different-bytes")
        item = mk_item(
            repo, session, "a.pdf", extension="pdf", blob=blob,
            descriptor={**descriptor, "sha256": stale_sha},
            extracted_blob=b"old", storage=storage,
        )
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=str(session.id))
        assert record["status"] == "extracted" and record.get("reused") is not True

    def test_partial_state_heals_when_text_blob_missing(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        blob = make_pdf_bytes("healed text")
        descriptor = self._descriptor_for(str(session.id), "a.pdf", blob)
        # Descriptor claims text but the blob is GONE (crash between writes).
        item = mk_item(repo, session, "a.pdf", extension="pdf", blob=blob, descriptor=descriptor, storage=storage)
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=str(session.id))
        assert record["status"] == "extracted" and record.get("reused") is not True
        assert storage.blobs[extracted_key_for(str(session.id), "a.pdf")] == b"healed text" or b"healed text" in storage.blobs[extracted_key_for(str(session.id), "a.pdf")]

    def test_unsupported_descriptor_reused_without_parser(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        blob = b"\x89PNG\r\n\x1a\n" + bytes(16)
        descriptor = {
            "status": "unsupported",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "text_key": None,
            "extracted_at": utcnow_iso(),
        }
        item = mk_item(repo, session, "p.png", extension="png", blob=blob, descriptor=descriptor, storage=storage)
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=str(session.id))
        assert record == {"reused": True, "status": "unsupported"}


# ------------------------------------------------------ runner lifecycle
class TestRunnerQueueLifecycle:
    def test_terminal_retry_at_limit_then_never_restarts(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        corrupt = b"%PDF-1.7\n" + b"%%%%"
        bad = mk_item(repo, session, "bad.pdf", extension="pdf", blob=corrupt, storage=storage)
        for attempt in (1, 2, 3):
            run_drain(repo, storage, session)
            assert int(bad.metadata.get_value(KEY_ATTEMPTS) or "0") == attempt
            assert (bad.metadata.get_value(KEY_INTAKE_STATUS) or "") == "error"
        history_len = len(json_decode(bad.metadata.get_value(KEY_STAGE_HISTORY), []))
        run_drain(repo, storage, session)  # 4th drain: terminally failed
        assert int(bad.metadata.get_value(KEY_ATTEMPTS) or "0") == 3  # not incremented
        assert len(json_decode(bad.metadata.get_value(KEY_STAGE_HISTORY), [])) == history_len  # untouched

    def test_healthy_item_reaches_review_once_while_corrupt_fails(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        ok = mk_item(repo, session, "ok.txt", blob=b"plain text", storage=storage)
        bad = mk_item(repo, session, "bad.pdf", extension="pdf", blob=b"%PDF-1.7\n%%%%", storage=storage)
        run_drain(repo, storage, session)
        assert (ok.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"
        stages = [r["stage"] for r in json_decode(ok.metadata.get_value(KEY_STAGE_HISTORY), [])]
        assert stages == [s.value for s in ITEM_STAGE_SEQUENCE]
        assert (bad.metadata.get_value(KEY_INTAKE_STATUS) or "") == "error"
        # session itself is NOT failed — per-item isolation holds
        assert (session.metadata.get_value(KEY_INTAKE_STATUS) or "") == "completed"

    def test_resume_reuses_finished_extraction_without_restart(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        blob = make_pdf_bytes("resume me")
        text_key = extracted_key_for(str(session.id), "a.pdf")
        descriptor = {
            "status": "extracted",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "text_key": text_key,
            "format": "pdf",
            "character_count": 9,
            "extracted_at": "2026-08-04T10:00:00+00:00",
        }
        # Crash leftover: staged, descriptor+blob already on disk.
        item = mk_item(
            repo, session, "a.pdf", extension="pdf", blob=blob, status="extracting",
            attempts=1, descriptor=descriptor, extracted_blob=b"resume me", storage=storage,
        )
        run_drain(repo, storage, session)
        assert (item.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"
        extract_steps = [
            r for r in json_decode(item.metadata.get_value(KEY_STAGE_HISTORY), [])
            if r["stage"] == "extract"
        ]
        assert extract_steps[-1]["result"] == {"reused": True, "status": "extracted"}
        assert json_decode(item.metadata.get_value(KEY_EXTRACTION), None)["extracted_at"] == "2026-08-04T10:00:00+00:00"

    def test_current_item_is_set_then_cleared_at_completion(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        mk_item(repo, session, "a.txt", storage=storage)
        run_drain(repo, storage, session)
        assert json_decode(session.metadata.get_value(KEY_CURRENT_ITEM), "unset") is None

    def test_retrying_status_visible_during_later_attempts(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        corrupt = b"%PDF-1.7\n%%%%"
        bad = mk_item(repo, session, "bad.pdf", extension="pdf", blob=corrupt, storage=storage)
        run_drain(repo, storage, session)
        seen: list[str] = []

        service = ExtractionService(build_document_parsers())
        real_extract = service.extract_item

        def spy(item, storage_, *, session_id):
            seen.append(item.metadata.get_value(KEY_INTAKE_STATUS) or "")
            return real_extract(item, storage_, session_id=session_id)

        runner = IntakeRunner(repo, storage, str(session.id), lambda: "go", build_document_parsers())
        runner._extraction.extract_item = spy  # type: ignore[method-assign]
        runner.run()
        assert seen and seen[0] == IntakeItemStatus.RETRYING.value
        assert int(bad.metadata.get_value(KEY_ATTEMPTS) or "0") == 2

    def test_needs_work_matrix_includes_crash_leftovers(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        runner = IntakeRunner(repo, storage, str(session.id), lambda: "go", build_document_parsers())
        matrix = {
            "pending": True,
            "staged": True,
            "extracting": True,   # crash leftover — always resumes
            "retrying": True,     # crash leftover — always resumes
            "awaiting_review": False,
        }
        for status, expected in matrix.items():
            item = mk_item(repo, session, f"{status}.txt", status=status, storage=storage)
            assert runner._needs_work(item) is expected, status
        err_open = mk_item(repo, session, "e1.pdf", extension="pdf", status="error", attempts=2, storage=storage)
        err_dead = mk_item(repo, session, "e2.pdf", extension="pdf", status="error", attempts=3, storage=storage)
        assert runner._needs_work(err_open) is True
        assert runner._needs_work(err_dead) is False
        assert (session.metadata.get_value(KEY_INTAKE_STATUS) or "") == "queued"  # drains never ran


class TestControlFinishLine:
    """The completion rollup is a probed boundary like every other one.

    When the only remaining work is the terminal persist itself, control
    accepted during that rollup must still land — the state machine has no
    blind spot at the finish line (deterministic: the probe flips after the
    single run()-start checkpoint).
    """

    def test_pause_flagged_during_completion_still_persists_paused(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        done = mk_item(repo, session, "done.txt", status="awaiting_review", storage=storage)
        calls = {"n": 0}

        def probe() -> str:
            calls["n"] += 1
            return "go" if calls["n"] == 1 else "pause"

        IntakeRunner(repo, storage, str(session.id), probe, build_document_parsers()).run()
        assert (session.metadata.get_value(KEY_INTAKE_STATUS) or "") == "paused"
        # finished work stays finished — never touched, never restarted
        assert (done.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"

    def test_cancel_flagged_during_completion_still_persists_cancelled(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        mk_item(repo, session, "done.txt", status="awaiting_review", storage=storage)
        calls = {"n": 0}

        def probe() -> str:
            calls["n"] += 1
            return "go" if calls["n"] == 1 else "cancel"

        IntakeRunner(repo, storage, str(session.id), probe, build_document_parsers()).run()
        assert (session.metadata.get_value(KEY_INTAKE_STATUS) or "") == "cancelled"
        summary = session.metadata.get_value("intake.summary") or ""
        assert summary.startswith("Cancelled")  # honest abort summary persisted
        assert json_decode(session.metadata.get_value(KEY_CURRENT_ITEM), "unset") is None

    def test_deletion_during_completion_writes_nothing_back(self) -> None:
        repo, storage = InMemoryRepo(), FakeStorage()
        session = mk_session(repo)
        mk_item(repo, session, "gone.txt", status="awaiting_review", storage=storage)
        sid = str(session.id)
        calls = {"n": 0}

        def probe() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return "go"
            repo.store.pop(sid, None)  # deleted underneath the rollout persist
            return "deleted"

        IntakeRunner(repo, storage, sid, probe, build_document_parsers()).run()
        assert repo.store.get(sid) is None  # no resurrection by the terminal save


class _StoppedFactory:
    """repository_factory producing a fresh view over one InMemoryRepo (the
    manager contract), with a no-op cleanup."""

    def __init__(self, repo: InMemoryRepo) -> None:
        self._repo = repo

    def __call__(self):
        return self._repo, lambda: None


class TestWorkerLease:
    def _manager(self, repo: InMemoryRepo, stale: float = 30.0) -> IntakeJobManager:
        manager = IntakeJobManager.__new__(IntakeJobManager)  # no worker thread
        manager._repository_factory = _StoppedFactory(repo)
        manager._storage = FakeStorage()
        manager._parsers = build_document_parsers()
        manager._lease_stale_seconds = stale
        manager._owner = "host:1:ownerA"
        manager._lock = threading.Lock()
        manager._flags = {}
        manager._enqueued = set()
        manager._active_id = None
        manager._shutdown = False
        manager._queue = queue.Queue()
        return manager

    def test_acquire_writes_and_verifies_lease(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        manager = self._manager(repo)
        assert manager.acquire_session(repo, session) is True
        lease = json_decode(session.metadata.get_value(KEY_LEASE), None)
        assert lease["owner"] == "host:1:ownerA"
        assert lease["acquired_at"] and lease["heartbeat_at"]

    def test_fresh_foreign_lease_blocks_duplicate_worker(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        ownerA = self._manager(repo)
        assert ownerA.acquire_session(repo, session) is True
        ownerB = self._manager(repo)
        ownerB._owner = "host:2:ownerB"
        assert ownerB.acquire_session(repo, session) is False
        lease = json_decode(session.metadata.get_value(KEY_LEASE), None)
        assert lease["owner"] == "host:1:ownerA"  # untouched

    def test_stale_lease_is_adopted_with_fresh_ownership_record(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        old = {
            "owner": "host:9:dead",
            "acquired_at": "2026-08-04T09:55:00+00:00",
            "heartbeat_at": "2026-08-04T09:55:01+00:00",
        }
        _put(session, KEY_LEASE, json_encode(old))
        manager = self._manager(repo)
        assert manager.acquire_session(repo, session) is True
        lease = json_decode(session.metadata.get_value(KEY_LEASE), None)
        assert lease["owner"] == "host:1:ownerA"
        # foreign adoption starts a HONEST new ownership window (the dead
        # owner's timestamps never survive on the lease record)
        assert lease["acquired_at"] != old["acquired_at"]
        assert lease["heartbeat_at"] > old["heartbeat_at"]

    def test_own_reacquire_preserves_the_ownership_window(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        manager = self._manager(repo)
        assert manager.acquire_session(repo, session) is True
        first = json_decode(session.metadata.get_value(KEY_LEASE), None)
        import time as _time

        _time.sleep(0.01)
        assert manager.acquire_session(repo, session) is True
        second = json_decode(session.metadata.get_value(KEY_LEASE), None)
        assert second["owner"] == first["owner"]
        assert second["acquired_at"] == first["acquired_at"]  # same owner, same window
        assert second["heartbeat_at"] > first["heartbeat_at"]

    def test_heartbeat_refreshes_only_heartbeat(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        manager = self._manager(repo)
        manager.acquire_session(repo, session)
        before = json_decode(session.metadata.get_value(KEY_LEASE), None)
        import time as _time

        _time.sleep(0.01)
        manager.heartbeat_session(session)
        repo.save(session)
        after = json_decode(session.metadata.get_value(KEY_LEASE), None)
        assert after["owner"] == before["owner"]
        assert after["acquired_at"] == before["acquired_at"]
        assert after["heartbeat_at"] > before["heartbeat_at"]

    def test_release_clears_only_own_lease(self) -> None:
        repo = InMemoryRepo()
        session = mk_session(repo, status="running")
        man_a = self._manager(repo)
        man_b = self._manager(repo)
        man_b._owner = "host:2:ownerB"
        man_a.acquire_session(repo, session)
        man_b.release_session(repo, str(session.id))  # foreign — must not clear
        assert json_decode(session.metadata.get_value(KEY_LEASE), None)["owner"] == "host:1:ownerA"
        man_a.release_session(repo, str(session.id))
        assert json_decode(session.metadata.get_value(KEY_LEASE), "x") is None

    def test_reconcile_skips_fresh_lease_and_adopts_stale(self) -> None:
        repo = InMemoryRepo()
        live = mk_session(repo, status="running")
        manager = self._manager(repo)
        manager.acquire_session(repo, live)
        crashed = mk_session(repo, status="running")
        _put(
            crashed,
            KEY_LEASE,
            json_encode({
                "owner": "host:9:dead",
                "acquired_at": "2026-08-04T08:00:00+00:00",
                "heartbeat_at": "2026-08-04T08:00:05+00:00",
            }),
        )
        # give mk_session a distinct key — both sessions coexist
        assert manager.reconcile_interrupted() == 1
        assert (live.metadata.get_value(KEY_INTAKE_STATUS) or "") == "running"
        assert (crashed.metadata.get_value(KEY_INTAKE_STATUS) or "") == "failed"
        assert json_decode(crashed.metadata.get_value(KEY_LEASE), "x") is None
        assert manager.is_active(str(live.id)) is False  # reconcile ≠ drain


# ---------------------------------------------------------------------------
# Crash containment: when even the persist layer hands back an unrecoverable
# driver error, a drain must fail HONESTLY (failed, resumable) — never wedge
# the session in queued/running on a silently swallowed exception.


class _FlakyRepo:
    """Port-faithful repo wrapper with programmed one-shot driver failures.

    Callers receive detached snapshots (deep copies, like the SQLAlchemy
    adapter's round-trips), so a write that "fails to commit" leaves the
    store at its last committed state — exactly a rolled-back transaction.
    Deterministic fault injection at the port; no wall-clock anywhere.
    """

    def __init__(self, inner: InMemoryRepo) -> None:
        self._inner = inner
        self._fail_get_ids: dict[str, int] = {}
        self._save_predicate = None
        self._fail_saves = 0

    def fail_next_get(self, object_id: str, *, times: int) -> None:
        self._fail_get_ids[object_id] = times

    def fail_saves_where(self, predicate, *, times: int) -> None:
        self._save_predicate = predicate
        self._fail_saves = times

    @staticmethod
    def _driver_locked(verb: str) -> OperationalError:
        return OperationalError(f"{verb} objects", (), Exception("database is locked"))

    def get_by_id(self, object_id):
        key = str(object_id)
        if self._fail_get_ids.get(key, 0) > 0:
            self._fail_get_ids[key] -= 1
            raise self._driver_locked("SELECT")
        obj = self._inner.get_by_id(object_id)
        return copy.deepcopy(obj) if obj is not None else None

    def save(self, obj):
        if (
            self._fail_saves > 0
            and self._save_predicate is not None
            and self._save_predicate(obj)
        ):
            self._fail_saves -= 1
            raise self._driver_locked("UPDATE")
        return self._inner.save(copy.deepcopy(obj))

    def find(self, *, object_type: ObjectType):
        return [copy.deepcopy(o) for o in self._inner.find(object_type=object_type)]


def _headless_manager(repo) -> IntakeJobManager:
    """Manager with NO worker thread — the drain loop is driven synchronously
    (queue primed with the job + the shutdown sentinel), fully deterministic."""

    manager = IntakeJobManager.__new__(IntakeJobManager)
    manager._repository_factory = _StoppedFactory(repo)
    manager._storage = FakeStorage()
    manager._parsers = build_document_parsers()
    manager._lease_stale_seconds = 30.0
    manager._owner = "host:1:ownerA"
    manager._lock = threading.Lock()
    manager._flags = {}
    manager._enqueued = set()
    manager._active_id = None
    manager._shutdown = False
    manager._queue = queue.Queue()
    return manager


class TestCrashContainment:
    """An unexpected escape from a drain is surfaced, never swallowed silent.

    These pins grow the failure mode behind "session did not settle": the
    dispatcher ate every exception after the runner's own guards, so a
    transient lock error that beat even the failure persist wedged the row
    in queued/running until the next process restart. The dispatcher now
    marks such a session FAILED (resumable) instead — the same honest
    outcome a restart-time reconcile would produce, but immediately.
    """

    def test_drain_crash_marks_session_failed_resumable_never_wedged(self) -> None:
        inner = InMemoryRepo()
        session = mk_session(inner)  # queued
        sid = str(session.id)
        repo = _FlakyRepo(inner)
        repo.fail_next_get(sid, times=1)  # the row load itself crashes
        manager = _headless_manager(repo)
        manager._queue.put(sid)
        manager._queue.put(None)
        manager._drain_loop()  # synchronous: crash escape, then containment

        settled = inner.store[sid]
        assert (settled.metadata.get_value(KEY_INTAKE_STATUS) or "") == "failed"
        error = json_decode(settled.metadata.get_value(KEY_ERROR), {})
        assert "crashed" in (error.get("message") or "").lower()
        assert "resume" in (error.get("message") or "").lower()  # honest: resumable
        assert manager.active_session() is None
        assert len(manager._enqueued) == 0  # queue state stays deterministic

    def test_crash_inside_abort_persist_is_contained_the_same_way(self) -> None:
        inner = InMemoryRepo()
        session = mk_session(inner)  # queued
        sid = str(session.id)
        repo = _FlakyRepo(inner)
        # The cooperative-pause persist is the one write that must ALWAYS
        # land; a driver error there used to escape run() and wedge the row.
        repo.fail_saves_where(
            lambda obj: obj.object_type is ObjectType.INTAKE_SESSION
            and (obj.metadata.get_value(KEY_INTAKE_STATUS) or "") == "paused",
            times=1,
        )
        manager = _headless_manager(repo)
        manager._flags[sid] = {"pause": True, "cancel": False, "deleted": False}
        manager._queue.put(sid)
        manager._queue.put(None)
        manager._drain_loop()

        settled = inner.store[sid]
        assert (settled.metadata.get_value(KEY_INTAKE_STATUS) or "") == "failed"
        assert json_decode(settled.metadata.get_value(KEY_LEASE), "x") is None
        assert manager.active_session() is None
